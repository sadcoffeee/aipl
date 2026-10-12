from typing import Any

from . import content, db


def needs_self_assessment(lesson: dict[str, Any]) -> bool:
    return lesson["type"] != "instruction" or bool(lesson.get("selfAssessment"))


def attempts_by_lesson(
    user_id: str, lessons_by_id: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT s.lesson_id,
                      a.id IS NOT NULL AS assessed,
                      e.solved
               FROM submissions s
               LEFT JOIN self_assessments a ON a.submission_id = s.id
               -- the most recent evaluation of each submission
               LEFT JOIN evaluations e ON e.id = (
                   SELECT id FROM evaluations
                   WHERE submission_id = s.id
                   ORDER BY created_at DESC LIMIT 1
               )
               WHERE s.user_id = ?""",
            (user_id,),
        ).fetchall()

    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        lesson = lessons_by_id.get(row["lesson_id"])
        if lesson is None:
            continue  # a lesson that has since been removed from the course
        if needs_self_assessment(lesson) and not row["assessed"]:
            continue  # not finished yet, so its verdict is still secret
        entry = result.setdefault(row["lesson_id"], {"attempts": 0, "solved": False})
        entry["attempts"] += 1
        if lesson["type"] == "instruction" or row["solved"] == 1:
            entry["solved"] = True
    return result


def build_course(
    collections: list[dict[str, Any]],
    lessons_by_id: dict[str, dict[str, Any]],
    attempts: dict[str, dict[str, Any]],
    gating: bool,
) -> dict[str, Any]:

    def attempted(lesson_id: str) -> bool:
        return attempts.get(lesson_id, {}).get("attempts", 0) > 0

    # Walk the whole course in order to decide what is unlocked.
    unlocked: set[str] = set()
    previous_attempted = True  # the very first lesson is always open
    for collection in collections:
        for lesson_id in collection["lessons"]:
            if not gating or previous_attempted:
                unlocked.add(lesson_id)
            previous_attempted = attempted(lesson_id)

    out = []
    for collection in collections:
        lessons = []
        for lesson_id in collection["lessons"]:
            state = attempts.get(lesson_id, {"attempts": 0, "solved": False})
            if lesson_id not in unlocked:
                status = "locked"
            elif state["solved"]:
                status = "completed"
            elif state["attempts"]:
                status = "attempted"
            else:
                status = "available"
            lessons.append(
                {
                    **content.summary(lessons_by_id[lesson_id]),
                    "status": status,
                    "attempts": state["attempts"],
                }
            )

        statuses = [lesson["status"] for lesson in lessons]
        completed = statuses.count("completed")
        attempted_only = statuses.count("attempted")

        if statuses[0] == "locked":
            collection_state = "locked"
        elif completed == len(statuses):
            collection_state = "completed"
        elif completed or attempted_only:
            collection_state = "in_progress"
        else:
            collection_state = "not_started"

        resume = None
        if collection_state != "locked":
            resume = (
                next((l["id"] for l in lessons if l["status"] == "available"), None)
                or next((l["id"] for l in lessons if l["status"] == "attempted"), None)
                or lessons[0]["id"]
            )

        out.append(
            {
                "id": collection["id"],
                "title": collection["title"],
                "description": collection.get("description"),
                "state": collection_state,
                "progress": {
                    "completed": completed,
                    "attempted": attempted_only,
                    "total": len(lessons),
                },
                "resumeLessonId": resume,
                "lessons": lessons,
            }
        )
    return {"collections": out}


def locked_lesson_ids(course: dict[str, Any]) -> set[str]:
    return {
        lesson["id"]
        for collection in course["collections"]
        for lesson in collection["lessons"]
        if lesson["status"] == "locked"
    }