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

from . import auth, chat, config, content, db, llm, grader, progress, feedback
from .grader import gaps as gap_tools


@asynccontextmanager
async def lifespan(_: FastAPI):
    #Runs once when the server starts: create tables and read the content files
    db.init_db()
    if config.GRADER_SANDBOX != "docker":
        print(
            f"WARNING: the grader runs student code with AIPL_GRADER_SANDBOX={config.GRADER_SANDBOX}, not in a container. "
            "Fine for development; set AIPL_GRADER_SANDBOX=docker if real participants are using this server.",
            flush=True,
        )
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
COLLECTIONS: list[dict[str, Any]] = []
HINTS: dict[str, dict[str, Any]] = {}


def reload_content() -> None:
    global LESSONS, LESSONS_BY_ID, COLLECTIONS, HINTS
    HINTS = content.load_hints()
    LESSONS, COLLECTIONS = content.load_course(HINTS)
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


class ChatMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=config.CHAT_MAX_MESSAGE_CHARS)
    # The student's work as it is right now. Only used before submitting, when there is
    # no submission to read it from. Same shapes as SubmissionIn.
    code: str | None = None
    placements: dict[str, str | None] | None = None


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


def clean_condition(value: str | None) -> str | None:
    """'' or None means no condition; anything else must be one of the known ones."""
    if not value:
        return None
    if value not in config.CONDITIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown condition {value!r}; use one of {', '.join(config.CONDITIONS)}",
        )
    return value


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


def course_for(user: dict[str, Any]) -> dict[str, Any]:
    return progress.build_course(
        COLLECTIONS,
        LESSONS_BY_ID,
        progress.attempts_by_lesson(user["id"], LESSONS_BY_ID),
        gating=config.GATING_ENABLED and user["role"] != "admin",
    )    

def locked_lesson_ids(user: dict[str, Any]) -> set[str]:
    return progress.locked_lesson_ids(course_for(user))

@app.get("/api/course")
def get_course(user: dict[str, Any] = Depends(auth.current_user)) -> dict[str, Any]:
    return course_for(user)

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
    return {"lessons": len(LESSONS), "collections": len(COLLECTIONS), "hints": len(HINTS)}


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
    if body.lessonId in locked_lesson_ids(user):
        raise HTTPException(status_code=403, detail="This lesson is not unlocked yet")    

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
        # A chat from before submitting (unrestricted only) now belongs to this attempt.
        chat.link_to_submission(conn, user["id"], body.lessonId, submission_id)

    # grader runs now but does not send the vercict back, so student can rate their confidence before the result becomes available to them. 
    store_evaluation(submission_id, grader.grade(lesson, payload))

    return {
        "submissionId": submission_id,
        "attemptNo": attempt_no,
        "nextStep": "self-assessment" if progress.needs_self_assessment(lesson) else "done",
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
    # Transaction 1: record the self-assessment, gather what feedback needs.
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
    
    lesson = LESSONS_BY_ID.get(submission["lesson_id"])
    if lesson is None:  # removed from the course since it was submitted
        feedback_body, calls = feedback.rule_based(evaluation, body.confidence), []
    else:
        feedback_body, calls = feedback.produce(
            lesson=lesson,
            payload=json.loads(submission["payload_json"]),
            evaluation=evaluation,
            confidence=body.confidence,
            notes=body.notes,
            attempt_no=submission["attempt_no"],
            ctx=feedback.context_for(lesson, LESSONS, HINTS),
        )

    # Transaction 2: store the feedback, every model call, and put both the self-assessment and the feedback into the conversation for this attempt.
    with db.connect() as conn:
        conversation_id = chat.conversation_for_submission(
            conn, user, submission["lesson_id"], submission_id
        )
        chat.add_message(
            conn, conversation_id, "student", "self_assessment",
            {"confidence": body.confidence, "notes": body.notes}, submission_id=submission_id,
        )
        chat.add_message(
            conn, conversation_id, "assistant", "feedback", feedback_body, submission_id=submission_id,
        )
        chat.store_calls(conn, calls, "feedback", submission_id, conversation_id)
        conn.execute(
            """INSERT INTO feedback (id, submission_id, source, body_json, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                new_id("f"),
                submission_id,
                feedback_body["source"],
                json.dumps(feedback_body, ensure_ascii=False),
                now(),
            ),
        )
        conversation = chat.view(conn, conversation_id)
    # Same shape as before, so the current frontend keeps working; the conversation rides along.
    return {**feedback_body, "conversationId": conversation_id, "conversation": conversation}


# --------------------------------------------------------------------------
# Conversations
# --------------------------------------------------------------------------


def own_conversation(conn, conversation_id: str, user: dict[str, Any]):
    row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown conversation")
    if row["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not your conversation")
    return row


@app.get("/api/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str, user: dict[str, Any] = Depends(auth.current_user)
) -> dict[str, Any]:
    with db.connect() as conn:
        own_conversation(conn, conversation_id, user)
        return chat.view(conn, conversation_id)


@app.get("/api/lessons/{lesson_id}/conversation")
def latest_conversation(
    lesson_id: str, user: dict[str, Any] = Depends(auth.current_user)
) -> dict[str, Any] | None:
    """The student's most recent conversation about a lesson, or null. For showing old feedback."""
    with db.connect() as conn:
        row = conn.execute(
            """SELECT id FROM conversations WHERE user_id = ? AND lesson_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (user["id"], lesson_id),
        ).fetchone()
        return chat.view(conn, row["id"]) if row else None


@app.post("/api/lessons/{lesson_id}/resume")
def resume_lesson(lesson_id: str, user: dict[str, Any] = Depends(auth.current_user)) -> dict[str, Any]:
    """What a task should show when it opens. One of:
    fresh        never attempted: a blank task
    in_progress  an unrestricted chat that has not been submitted yet
    assessing    submitted, but the self-assessment was never given: ask for it now
    reviewing    the latest attempt with its feedback, read-only
    """
    lesson = LESSONS_BY_ID.get(lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Unknown lesson")
    if lesson_id in locked_lesson_ids(user):
        raise HTTPException(status_code=403, detail="This lesson is not unlocked yet")
    fresh = {"state": "fresh", "submission": None, "conversation": None}
    if lesson["type"] not in ("completion", "parsons"):
        return fresh

    with db.connect() as conn:
        # Only possible in the unrestricted condition
        in_progress = chat.open_unsubmitted(conn, user["id"], lesson_id)
        if in_progress is not None:
            return {"state": "in_progress", "submission": None,
                    "conversation": chat.view(conn, in_progress["id"])}

        row = conn.execute(
            """SELECT * FROM submissions WHERE user_id = ? AND lesson_id = ?
               ORDER BY submitted_at DESC LIMIT 1""",
            (user["id"], lesson_id),
        ).fetchone()
        if row is None:
            return fresh

        payload = json.loads(row["payload_json"])
        submission: dict[str, Any] = {"id": row["id"], "attemptNo": row["attempt_no"], "payload": payload}
        if lesson["type"] == "completion":
            # What went into each gap, so the editor can be rebuilt with its gaps intact.
            # None if the code no longer fits the scaffold (e.g. the lesson was edited since).
            submission["gapContents"] = gap_tools.extract(
                lesson["content"]["starterCode"], payload.get("code") or ""
            )

        assessed = conn.execute(
            "SELECT 1 FROM self_assessments WHERE submission_id = ?", (row["id"],)
        ).fetchone()
        if assessed is None:
            return {"state": "assessing", "submission": submission, "conversation": None}

        conversation = conn.execute(
            "SELECT id, closed_at FROM conversations WHERE submission_id = ? ORDER BY created_at DESC LIMIT 1",
            (row["id"],),
        ).fetchone()
        if conversation is not None and conversation["closed_at"] is None:
            conn.execute("UPDATE conversations SET closed_at = ? WHERE id = ?", (now(), conversation["id"]))
        conn.execute(
            """INSERT INTO events (user_id, lesson_id, type, payload_json, created_at)
               VALUES (?, ?, 'feedback_revisited', ?, ?)""",
            (user["id"], lesson_id,
             json.dumps({"submissionId": row["id"],
                         "conversationId": conversation["id"] if conversation else None}),
             now()),
        )
        return {
            "state": "reviewing",
            "submission": submission,
            # None only for attempts made before conversations existed
            "conversation": chat.view(conn, conversation["id"]) if conversation else None,
        }


@app.post("/api/lessons/{lesson_id}/conversations")
def start_conversation(
    lesson_id: str, user: dict[str, Any] = Depends(auth.current_user)
) -> dict[str, Any]:
    """Start (or pick up again) the chat for the attempt in progress. Unrestricted condition only."""
    lesson = LESSONS_BY_ID.get(lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Unknown lesson")
    if lesson["type"] not in ("completion", "parsons"):
        raise HTTPException(status_code=400, detail="This lesson has no task to talk about")
    if lesson_id in locked_lesson_ids(user):
        raise HTTPException(status_code=403, detail="This lesson is not unlocked yet")
    if chat.effective_condition(user) != "unrestricted":
        raise HTTPException(status_code=403, detail="Chat opens after feedback in this condition")
    with db.connect() as conn:
        conversation_id = chat.start_or_resume(conn, user, lesson_id)
        return chat.view(conn, conversation_id)


@app.post("/api/conversations/{conversation_id}/messages")
def send_chat_message(
    conversation_id: str,
    body: ChatMessageIn,
    user: dict[str, Any] = Depends(auth.current_user),
) -> dict[str, Any]:
    """A student message, and the model's answer. Returns the whole conversation."""
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Empty message")

    # Transaction 1: check the student may send it, record it, gather what the model needs.
    # The message is stored as counted straight away, so two quick sends cannot both slip under the cap; it stops counting if no usable answer comes back.
    with db.connect() as conn:
        conversation = own_conversation(conn, conversation_id, user)
        current = chat.view(conn, conversation_id)
        if current["closed"]:
            raise HTTPException(status_code=409, detail="This conversation is closed")
        if current["remainingMessages"] <= 0:
            raise HTTPException(status_code=409, detail="No messages left for this attempt")
        if not current["canReply"]:
            raise HTTPException(status_code=409, detail="Replies are not open yet")

        submission_id = conversation["submission_id"]
        before_submission = submission_id is None
        snapshot: dict[str, Any] = {}
        if before_submission:
            if body.code is not None:
                snapshot["code"] = body.code
            if body.placements is not None:
                snapshot["placements"] = body.placements

        student_message_id = chat.add_message(
            conn, conversation_id, "student", "chat",
            {"text": text, "snapshot": snapshot} if before_submission else {"text": text},
            submission_id=submission_id, counted=True,
        )

        submission = conn.execute(
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone() if submission_id else None
        evaluation = latest_evaluation(conn, submission_id) if submission_id else None
        assessment = conn.execute(
            "SELECT * FROM self_assessments WHERE submission_id = ?", (submission_id,)
        ).fetchone() if submission_id else None

    messages = current["messages"]
    feedback_body = next((m["body"] for m in reversed(messages) if m["kind"] == "feedback"), None)
    lesson = LESSONS_BY_ID.get(conversation["lesson_id"])

    reply: str | None = None
    calls: list[dict[str, Any]] = []
    fallback = chat.UNAVAILABLE
    model_on = (
        config.FEEDBACK_MODE == "llm"
        and bool(config.LLM_MODEL)
        and lesson is not None
        and lesson["type"] in ("completion", "parsons")
    )

    if model_on and before_submission:
        # Still working: the model sees the task and the work so far, but no verdict.
        ctx = feedback.context_for(lesson, LESSONS, HINTS)
        system, prompt_version = chat.load_prompt(before_submission=True)
        context = chat.presubmission_context(lesson, snapshot, ctx)
        prompt = chat.build_messages(system, context, None, chat.history_pairs(messages), text)
        reply, calls = chat.write_reply(prompt, chat.presubmission_secrets(lesson, snapshot), prompt_version, ctx)

    elif (
        model_on
        and submission is not None
        and assessment is not None
        and feedback_body is not None
        and evaluation is not None
        and evaluation["status"] != "grader_error"
    ):
        # After feedback: the full context with the verdict. A chat from before submitting goes into that context as a section.
        payload = json.loads(submission["payload_json"])
        before, after = chat.split_at_feedback(messages)
        ctx = feedback.context_for(lesson, LESSONS, HINTS)
        context = feedback.build_user_message(
            lesson, payload, evaluation, assessment["confidence"], assessment["notes"],
            submission["attempt_no"], ctx, closing=None,
        ) + chat.earlier_chat_section(chat.history_pairs(before))
        system, prompt_version = chat.load_prompt()
        prompt = chat.build_messages(system, context, feedback_body, chat.history_pairs(after), text)
        reply, calls = chat.write_reply(
            prompt, feedback.secrets_for(lesson, payload, evaluation), prompt_version, ctx
        )

    # The model answered, but every answer broke a rule: say so without saying which.
    if reply is None and calls and calls[-1]["outcome"] != "error":
        fallback = chat.CANNOT_ANSWER

    # Transaction 2: store the answer (or the fixed message) and the calls behind it.
    with db.connect() as conn:
        if reply is not None:
            chat.add_message(conn, conversation_id, "assistant", "chat", {"text": reply},
                             submission_id=submission_id)
        else:
            conn.execute("UPDATE messages SET counted = 0 WHERE id = ?", (student_message_id,))
            chat.add_message(conn, conversation_id, "assistant", "fallback", {"text": fallback},
                             submission_id=submission_id)
        chat.store_calls(conn, calls, "chat", submission_id, conversation_id)
        return chat.view(conn, conversation_id)

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
    condition = clean_condition(body.condition)
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
                (user_id, code, condition, body.label, now()),
            )
            created.append({"id": user_id, "code": code, "condition": condition})
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
    """Everything about one submission: code, evaluations, feedback, model calls."""
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
        feedback_rows = conn.execute(
            "SELECT * FROM feedback WHERE submission_id = ? ORDER BY created_at",
            (submission_id,),
        ).fetchall()
        call_rows = conn.execute(
            "SELECT * FROM llm_calls WHERE submission_id = ? ORDER BY created_at",
            (submission_id,),
        ).fetchall()
        conversation_rows = conn.execute(
            "SELECT id FROM conversations WHERE submission_id = ? ORDER BY created_at",
            (submission_id,),
        ).fetchall()
        conversations = [chat.view(conn, row["id"]) for row in conversation_rows]
    return {
        "submission": {**dict(submission), "payload": json.loads(submission["payload_json"])},
        "evaluations": [
            {**dict(row), "result": json.loads(row["result_json"])} for row in evaluations
        ],
        "feedback": [{**dict(row), "body": json.loads(row["body_json"])} for row in feedback_rows],
        "llmCalls": [
            {**dict(row), "messages": json.loads(row["messages_json"])} for row in call_rows
        ],
        "conversations": conversations,
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
        values.append(clean_condition(body.condition))
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

@app.get("/api/admin/feedback")
def review_feedback(
    limit: int = 50,
    source: str | None = None,
    _: dict[str, Any] = Depends(auth.require_admin),
) -> list[dict[str, Any]]:
    query = """
        SELECT f.created_at, f.source, f.body_json,
               s.id AS submission_id, s.lesson_id, s.attempt_no, s.payload_json,
               a.confidence, a.notes,
               (SELECT status FROM evaluations e WHERE e.submission_id = s.id
                ORDER BY e.created_at DESC LIMIT 1) AS status,
               (SELECT group_concat(outcome, ', ') FROM llm_calls l
                WHERE l.submission_id = s.id) AS model_outcomes,
               (SELECT sum(latency_ms) FROM llm_calls l
                WHERE l.submission_id = s.id) AS model_ms
        FROM feedback f
        JOIN submissions s ON s.id = f.submission_id
        LEFT JOIN self_assessments a ON a.submission_id = s.id
    """
    params: list[Any] = []
    if source:
        query += " WHERE f.source = ?"
        params.append(source)
    query += " ORDER BY f.created_at DESC LIMIT ?"
    params.append(max(1, min(limit, 500)))

    with db.connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        {
            "createdAt": row["created_at"],
            "submissionId": row["submission_id"],
            "lessonId": row["lesson_id"],
            "attemptNo": row["attempt_no"],
            "submitted": json.loads(row["payload_json"]),
            "status": row["status"],
            "confidence": row["confidence"],
            "notes": row["notes"],
            "feedback": json.loads(row["body_json"]),
            "modelOutcomes": row["model_outcomes"],
            "modelMs": row["model_ms"],
        }
        for row in rows
    ]



@app.get("/api/admin/export")
def export_everything(
    codes: str | None = None, _: dict[str, Any] = Depends(auth.require_admin)
) -> dict[str, Any]:
    """The database as JSON, for analysis. Password hashes are left out.

    With ?codes=KVT-AAAAAA,KVT-BBBBBB only those participants and everything that
    belongs to them; without it, everything (admins included).
    """
    wanted = sorted({c.strip() for c in codes.split(",") if c.strip()}) if codes else None

    with db.connect() as conn:
        def rows(query: str, params: list[Any] | tuple[Any, ...] = ()) -> list[dict[str, Any]]:
            return [dict(row) for row in conn.execute(query, params).fetchall()]

        user_columns = "id, role, code, username, condition, label, active, created_at"

        if wanted is None:
            return {
                "exportedAt": now(),
                "codes": None,
                "users": rows(f"SELECT {user_columns} FROM users"),
                "submissions": rows("SELECT * FROM submissions"),
                "selfAssessments": rows("SELECT * FROM self_assessments"),
                "evaluations": rows("SELECT * FROM evaluations"),
                "feedback": rows("SELECT * FROM feedback"),
                "llmCalls": rows("SELECT * FROM llm_calls"),
                "conversations": rows("SELECT * FROM conversations"),
                "messages": rows("SELECT * FROM messages ORDER BY conversation_id, seq"),
                "events": rows("SELECT * FROM events"),
            }

        marks = ", ".join("?" for _ in wanted)
        users = rows(f"SELECT {user_columns} FROM users WHERE code IN ({marks})", wanted)
        unknown = sorted(set(wanted) - {user["code"] for user in users})
        if unknown:
            raise HTTPException(status_code=404, detail=f"Unknown codes: {', '.join(unknown)}")

        # Every other table hangs off a user, a submission or a conversation.
        ids = [user["id"] for user in users]
        by_user = f"user_id IN ({', '.join('?' for _ in ids)})"
        by_submission = f"submission_id IN (SELECT id FROM submissions WHERE {by_user})"
        by_conversation = f"conversation_id IN (SELECT id FROM conversations WHERE {by_user})"
        return {
            "exportedAt": now(),
            "codes": wanted,
            "users": users,
            "submissions": rows(f"SELECT * FROM submissions WHERE {by_user} ORDER BY submitted_at", ids),
            "selfAssessments": rows(f"SELECT * FROM self_assessments WHERE {by_submission}", ids),
            "evaluations": rows(f"SELECT * FROM evaluations WHERE {by_submission}", ids),
            "feedback": rows(f"SELECT * FROM feedback WHERE {by_submission}", ids),
            # Chat calls before submitting have only a conversation, not a submission.
            "llmCalls": rows(
                f"SELECT * FROM llm_calls WHERE {by_submission} OR {by_conversation} ORDER BY created_at",
                ids + ids,
            ),
            "conversations": rows(f"SELECT * FROM conversations WHERE {by_user} ORDER BY created_at", ids),
            "messages": rows(
                f"SELECT * FROM messages WHERE {by_conversation} ORDER BY conversation_id, seq", ids
            ),
            "events": rows(f"SELECT * FROM events WHERE {by_user} ORDER BY id", ids),
        }


@app.get("/api/health")
def health() -> dict[str, Any]:
    # Unauthenticated on purpose; it is how I check the server is up
    return {"ok": True, "lessons": len(LESSONS), "hints": len(HINTS), "grader": config.GRADER_SANDBOX}

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