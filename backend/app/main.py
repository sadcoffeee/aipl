from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import auth, config, content, db, llm, grader


@asynccontextmanager
async def lifespan(_: FastAPI):
    #Runs once when the server starts: create tables and read the content files
    db.init_db()
    with db.connect() as conn:
        auth.purge_expired_sessions(conn)
    reload_content()
    yield


app = FastAPI(
    title="AI-assisted programming learning - study backend", lifespan=lifespan
)

# The Vite dev server runs on a different port than this API, so the browser treats it as a different origin and blocks requests unless we allow it here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Content is read once at startup. Restart the server, or call the reload endpoint, after editing the files.
LESSONS: list[dict[str, Any]] = []
LESSONS_BY_ID: dict[str, dict[str, Any]] = {}
HINTS: dict[str, dict[str, Any]] = {}


def reload_content() -> None:
    global LESSONS, LESSONS_BY_ID, HINTS
    HINTS = content.load_hints()
    LESSONS = content.load_all(HINTS)
    LESSONS_BY_ID = {lesson["id"]: lesson for lesson in LESSONS}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# --------------------------------------------------------------------------
# Request shapes. FastAPI validates incoming JSON against these, so a malformed request gets a clear 422 instead of a crash deeper in the code.
# --------------------------------------------------------------------------


class StudentLoginIn(BaseModel):
    code: str


class AdminLoginIn(BaseModel):
    username: str
    password: str


class SubmissionIn(BaseModel):
    lessonId: str
    # Completion tasks send written code; Parson's problems send slot -> option ids.
    code: str | None = None
    placements: dict[str, str | None] | None = None
    startedAt: str | None = None
    durationMs: int | None = None


class SelfAssessmentIn(BaseModel):
    confidence: int = Field(ge=1, le=5)
    notes: str | None = None


class EventIn(BaseModel):
    lessonId: str | None = None
    type: str
    payload: dict[str, Any] | None = None


class CreateParticipantsIn(BaseModel):
    count: int = Field(default=1, ge=1, le=200)
    condition: str | None = None
    label: str | None = None


class UpdateParticipantIn(BaseModel):
    condition: str | None = None
    label: str | None = None
    active: bool | None = None


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------


@app.post("/api/auth/login/student")
def login_student(body: StudentLoginIn) -> dict[str, Any]:
    code = auth.normalise_code(body.code)
    with db.connect() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE role = 'student' AND code = ?", (code,)
        ).fetchone()
        if user is None:
            raise HTTPException(status_code=401, detail="Unknown code")
        if not user["active"]:
            raise HTTPException(status_code=403, detail="This code has been disabled")
        session = auth.create_session(conn, user["id"])
    return {**session, "user": auth.public_user(dict(user))}


@app.post("/api/auth/login/admin")
def login_admin(body: AdminLoginIn) -> dict[str, Any]:
    with db.connect() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE role = 'admin' AND username = ?", (body.username,)
        ).fetchone()
        stored = user["password_hash"] if user else None
        if not auth.verify_password(body.password, stored) or user is None:
            raise HTTPException(status_code=401, detail="Wrong username or password")
        if not user["active"]:
            raise HTTPException(status_code=403, detail="This account is disabled")
        session = auth.create_session(conn, user["id"])
    return {**session, "user": auth.public_user(dict(user))}


@app.get("/api/auth/me")
def whoami(user: dict[str, Any] = Depends(auth.current_user)) -> dict[str, Any]:
    return auth.public_user(user)


@app.post("/api/auth/logout")
def logout(user: dict[str, Any] = Depends(auth.current_user)) -> dict[str, Any]:
    with db.connect() as conn:
        auth.delete_session(conn, user["session_token"])
    return {"ok": True}


# --------------------------------------------------------------------------
# Lessons
# --------------------------------------------------------------------------


def locked_lesson_ids(user: dict[str, Any]) -> set[str]:
    if not config.GATING_ENABLED or user["role"] == "admin":
        return set()

    with db.connect() as conn:
        rows = conn.execute("SELECT DISTINCT lesson_id FROM submissions WHERE user_id = ?", (user["id"],),).fetchall()
    attempted = {row["lesson_id"] for row in rows}

    locked: set[str] = set()
    blocked = False
    for lesson in LESSONS:  # already in course order
        if blocked:
            locked.add(lesson["id"])
            continue
        if lesson["type"] != "instruction" and lesson["id"] not in attempted:
            blocked = True
    return locked


@app.get("/api/lessons")
def list_lessons(user: dict[str, Any] = Depends(auth.current_user)) -> list[dict[str, Any]]:
    locked = locked_lesson_ids(user)
    return [
        {**content.summary(lesson), "locked": lesson["id"] in locked}
        for lesson in LESSONS
    ]


@app.get("/api/lessons/{lesson_id}")
def get_lesson(
    lesson_id: str, user: dict[str, Any] = Depends(auth.current_user)
) -> dict[str, Any]:
    lesson = LESSONS_BY_ID.get(lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Unknown lesson")
    if lesson_id in locked_lesson_ids(user):
        raise HTTPException(status_code=403, detail="This lesson is not unlocked yet")
    # Strips the "private" key - answer keys never reach the browser.
    return content.public_view(lesson)


@app.get("/api/lessons/{lesson_id}/hints")
def get_lesson_hints(
    lesson_id: str, user: dict[str, Any] = Depends(auth.current_user)
) -> dict[str, list[dict[str, Any]]]:
    # The reference entries available at this point in the course.
    lesson = LESSONS_BY_ID.get(lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Unknown lesson")
    return content.hints_for_lesson(
        lesson, LESSONS, HINTS, include_all=user["role"] == "admin"
    )


@app.post("/api/admin/reload-content")
def admin_reload_content(_: dict[str, Any] = Depends(auth.require_admin)) -> dict[str, Any]:
    # Convenience during authoring: re-reads the content files without a restart
    reload_content()
    return {"lessons": len(LESSONS), "hints": len(HINTS)}


# --------------------------------------------------------------------------
# Submissions and self-assessment
# --------------------------------------------------------------------------


@app.post("/api/submissions")
def create_submission(
    body: SubmissionIn, user: dict[str, Any] = Depends(auth.current_user)
) -> dict[str, Any]:
    lesson = LESSONS_BY_ID.get(body.lessonId)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Unknown lesson")

    with db.connect() as conn:
        attempt_no = conn.execute(
            "SELECT COUNT(*) AS n FROM submissions WHERE user_id = ? AND lesson_id = ?",
            (user["id"], body.lessonId),
        ).fetchone()["n"] + 1

        payload: dict[str, Any] = {}
        if body.code is not None:
            payload["code"] = body.code
        if body.placements is not None:
            payload["placements"] = body.placements

        submission_id = new_id("s")
        conn.execute(
            """INSERT INTO submissions
               (id, user_id, lesson_id, lesson_type, lesson_version, lesson_hash,
                attempt_no, payload_json, started_at, submitted_at, duration_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                submission_id,
                user["id"],
                body.lessonId,
                lesson["type"],
                lesson.get("version", 1),
                lesson.get("contentHash"),
                attempt_no,
                json.dumps(payload),
                body.startedAt,
                now(),
                body.durationMs,
            ),
        )

    # grader runs now but does not send the vercict back, so student can rate their confidence before the result becomes available to them. 
    store_evaluation(submission_id, grader.grade(lesson, payload))

    return {
        "submissionId": submission_id,
        "attemptNo": attempt_no,
        "nextStep": "self-assessment",
    }

def store_evaluation(submission_id: str, evaluation: dict[str, Any] | None) -> None:
    if evaluation is None:
        return
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO evaluations
               (id, submission_id, grader_version, status, solved, result_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                new_id("e"),
                submission_id,
                evaluation["graderVersion"],
                evaluation["status"],
                None if evaluation["solved"] is None else int(evaluation["solved"]),
                json.dumps(evaluation),
                now(),
            ),
        )


def latest_evaluation(conn, submission_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """SELECT result_json FROM evaluations WHERE submission_id = ?
           ORDER BY created_at DESC LIMIT 1""",
        (submission_id,),
    ).fetchone()
    return json.loads(row["result_json"]) if row else None


@app.post("/api/submissions/{submission_id}/self-assessment")
def create_self_assessment(
    submission_id: str,
    body: SelfAssessmentIn,
    user: dict[str, Any] = Depends(auth.current_user),
) -> dict[str, Any]:
    with db.connect() as conn:
        submission = conn.execute(
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        if submission is None:
            raise HTTPException(status_code=404, detail="Unknown submission")
        # A submission belongs to the person who made it
        if submission["user_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Not your submission")
        existing = conn.execute(
            "SELECT id FROM self_assessments WHERE submission_id = ?", (submission_id,)
        ).fetchone()
        if existing is not None:
            raise HTTPException(
                status_code=409, detail="This submission already has a self-assessment"
            )
        conn.execute(
            """INSERT INTO self_assessments
               (id, submission_id, confidence, notes, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (new_id("a"), submission_id, body.confidence, body.notes, now()),
        )

        evaluation = latest_evaluation(conn, submission_id)
        feedback_body = rule_based_feedback(evaluation, body)

        conn.execute(
            """INSERT INTO feedback (id, submission_id, source, body_json, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                new_id("f"),
                submission_id,
                feedback_body["source"],
                json.dumps(feedback_body),
                now(),
            ),
        )
    return feedback_body


SUMMARIES = {
    "passed": "Your solution works.",
    "failed": "Your code runs, but the result is not right yet.",
    "incomplete": "Some of the task was left unfinished.",
    "syntax_error": "Python could not read the code, so it did not run.",
    "runtime_error": "The code started running but stopped with an error.",
    "timeout": "The code took too long to finish. Is there a loop that never ends?",
    "grader_error": "Something went wrong on our side while checking this — it is not your mistake.",
}


def rule_based_feedback(
    evaluation: dict[str, Any] | None, assessment: SelfAssessmentIn
) -> dict[str, Any]:
    if evaluation is None:
        return {
            "source": "rules", "solved": None,
            "summary": "Your answer has been recorded.",
            "points": [], "revisitLessonId": None,
        }

    status = evaluation["status"]
    points: list[dict[str, Any]] = []

    error = evaluation.get("error")
    if status in ("syntax_error", "runtime_error") and error:
        points.append({
            "line": error.get("line"),
            "text": f"{error['type']}: {error['message']}",
            "hintId": None,
        })

    if status == "incomplete":
        empty = [g["index"] for g in evaluation.get("gaps") or [] if g["empty"]]
        empty += evaluation.get("emptySlots") or []
        if empty:
            points.append({
                "line": None,
                "text": "Not filled in yet: " + ", ".join(f"gap {i}" if isinstance(i, int) else f"box {i}" for i in empty),
                "hintId": None,
            })

    # Failed checks, required ones first, using the author's own wording.
    failed = [c for c in evaluation.get("checks", []) if c["passed"] is False]
    failed.sort(key=lambda c: not c["required"])
    for check in failed:
        if check.get("message"):
            points.append({"line": None, "text": check["message"], "hintId": check.get("hint")})

    # Parson's: name the misconception a chosen distractor suggests.
    for slot in evaluation.get("slots") or []:
        if not slot["correct"] and slot.get("note"):
            points.append({"line": None, "text": slot["note"], "hintId": None})
        elif slot.get("misplaced"):
            points.append({"line": None, "text": "A correct line is in the wrong place.", "hintId": None})

    # Calibration: how the confidence rating compares with the result.
    solved = evaluation["solved"]
    if solved is not None:
        confident = assessment.confidence >= 4
        if solved and not confident:
            remark = "You were unsure, but it works. Well done!"
        elif not solved and confident:
            remark = "You felt sure about this one. It is worth looking again at what you expected to happen."
        else:
            remark = None
        if remark:
            points.append({"line": None, "text": remark, "hintId": None})
    
    return {
        "source": "rules",
        "solved": solved,
        "summary": SUMMARIES.get(status, "Your answer has been recorded."),
        "points": points,
        "revisitLessonId": None,
    }

@app.get("/api/me/submissions")
def my_submissions(user: dict[str, Any] = Depends(auth.current_user)) -> list[dict[str, Any]]:
    rows = submissions_for(user["id"])
    for row in rows:
        if row["confidence"] is None:
            row["status"] = row["solved"] = None
    return rows

def submissions_for(user_id: str) -> list[dict[str, Any]]:
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT s.id, s.lesson_id, s.lesson_type, s.lesson_version, s.attempt_no,
                      s.submitted_at, s.duration_ms, a.confidence, a.notes,
                      e.status, e.solved
               FROM submissions s
               LEFT JOIN self_assessments a ON a.submission_id = s.id
               LEFT JOIN evaluations e ON e.id = (
               SELECT id FROM evaluations
               WHERE submission_id = s.id
               ORDER BY created_at DESC LIMIT 1
               )
               WHERE s.user_id = ?
               ORDER BY s.submitted_at""",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


# --------------------------------------------------------------------------
# Event log
# --------------------------------------------------------------------------


@app.post("/api/events")
def create_event(
    body: EventIn, user: dict[str, Any] = Depends(auth.current_user)
) -> dict[str, Any]:
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO events (user_id, lesson_id, type, payload_json, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                user["id"],
                body.lessonId,
                body.type,
                json.dumps(body.payload) if body.payload else None,
                now(),
            ),
        )
    return {"ok": True}


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------


@app.post("/api/admin/participants")
def create_participants(
    body: CreateParticipantsIn, _: dict[str, Any] = Depends(auth.require_admin)
) -> list[dict[str, Any]]:
    #Create participant codes, ready to be distributed to users
    created: list[dict[str, Any]] = []
    with db.connect() as conn:
        for _index in range(body.count):
            # Retry on the astronomically unlikely collision rather than crash.
            for _attempt in range(10):
                code = auth.generate_code()
                taken = conn.execute(
                    "SELECT 1 FROM users WHERE code = ?", (code,)
                ).fetchone()
                if taken is None:
                    break
            else:
                raise HTTPException(status_code=500, detail="Could not generate a code")

            user_id = new_id("u")
            conn.execute(
                """INSERT INTO users (id, role, code, condition, label, active, created_at)
                   VALUES (?, 'student', ?, ?, ?, 1, ?)""",
                (user_id, code, body.condition, body.label, now()),
            )
            created.append({"id": user_id, "code": code, "condition": body.condition})
    return created


@app.get("/api/admin/participants")
def list_participants(_: dict[str, Any] = Depends(auth.require_admin)) -> list[dict[str, Any]]:
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT u.id, u.code, u.condition, u.label, u.active, u.created_at,
                      COUNT(s.id) AS submission_count,
                      MAX(s.submitted_at) AS last_submission
               FROM users u
               LEFT JOIN submissions s ON s.user_id = u.id
               WHERE u.role = 'student'
               GROUP BY u.id
               ORDER BY u.created_at DESC""",
        ).fetchall()
    return [dict(row) for row in rows]

@app.get("/api/admin/submissions/{submission_id}")
def admin_submission_detail(
    submission_id: str, _: dict[str, Any] = Depends(auth.require_admin)
) -> dict[str, Any]:
    """Everything about one submission: the code, every evaluation, feedback."""
    with db.connect() as conn:
        submission = conn.execute(
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        if submission is None:
            raise HTTPException(status_code=404, detail="Unknown submission")
        evaluations = conn.execute(
            "SELECT * FROM evaluations WHERE submission_id = ? ORDER BY created_at",
            (submission_id,),
        ).fetchall()
        feedback = conn.execute(
            "SELECT * FROM feedback WHERE submission_id = ? ORDER BY created_at",
            (submission_id,),
        ).fetchall()
    return {
        "submission": {**dict(submission), "payload": json.loads(submission["payload_json"])},
        "evaluations": [
            {**dict(row), "result": json.loads(row["result_json"])} for row in evaluations
        ],
        "feedback": [{**dict(row), "body": json.loads(row["body_json"])} for row in feedback],
    }


@app.patch("/api/admin/participants/{user_id}")
def update_participant(
    user_id: str,
    body: UpdateParticipantIn,
    _: dict[str, Any] = Depends(auth.require_admin),
) -> dict[str, Any]:
    fields: list[str] = []
    values: list[Any] = []
    if body.condition is not None:
        fields.append("condition = ?")
        values.append(body.condition or None)
    if body.label is not None:
        fields.append("label = ?")
        values.append(body.label)
    if body.active is not None:
        fields.append("active = ?")
        values.append(1 if body.active else 0)
    if not fields:
        raise HTTPException(status_code=400, detail="Nothing to update")

    with db.connect() as conn:
        cursor = conn.execute(
            f"UPDATE users SET {', '.join(fields)} WHERE id = ? AND role = 'student'",
            (*values, user_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Unknown participant")
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return auth.public_user(dict(row))


@app.get("/api/admin/participants/{user_id}/submissions")
def participant_submissions(
    user_id: str, _: dict[str, Any] = Depends(auth.require_admin)
) -> list[dict[str, Any]]:
    return submissions_for(user_id)


@app.get("/api/admin/export")
def export_everything(_: dict[str, Any] = Depends(auth.require_admin)) -> dict[str, Any]:
    # Whole database as JSON, for analysis. Password hashes are left out
    with db.connect() as conn:
        def rows(query: str) -> list[dict[str, Any]]:
            return [dict(row) for row in conn.execute(query).fetchall()]

        return {
            "exportedAt": now(),
            "users": rows(
                """SELECT id, role, code, username, condition, label, active, created_at
                   FROM users"""
            ),
            "submissions": rows("SELECT * FROM submissions"),
            "selfAssessments": rows("SELECT * FROM self_assessments"),
            "evaluations": rows("SELECT * FROM evaluations"),
            "feedback": rows("SELECT * FROM feedback"),
            "events": rows("SELECT * FROM events"),
        }


@app.get("/api/health")
def health() -> dict[str, Any]:
    # Unauthenticated on purpose; it is how I check the server is up
    return {"ok": True, "lessons": len(LESSONS), "hints": len(HINTS)}

@app.get("/api/admin/llm-check")
def admin_llm_check(_: dict[str, Any] = Depends(auth.require_admin)) -> dict[str, Any]:
    """Browser check to see if the backend can reach the LLM server."""
    return llm.check_connection()


# --------------------------------------------------------------------------
# The pre-built frontend is served from the dist folder. When running locally, the Vite dev server runs on a different port and serves the frontend instead
# --------------------------------------------------------------------------

if config.FRONTEND_DIST.is_dir():
    app.mount(
        "/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="frontend"
    )