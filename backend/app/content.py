from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any

from .grader import checks as check_spec
from .grader import gaps

CONTENT_DIR = pathlib.Path(__file__).resolve().parents[1] / "content"
LESSON_DIR = CONTENT_DIR / "lessons"
HINTS_FILE = CONTENT_DIR / "hints.json"
COLLECTIONS_FILE = CONTENT_DIR / "collections.json"
DATASET_DIR = CONTENT_DIR / "datasets"

NEEDS_REFERENCE = {"variable_matches_reference", "value_matches_reference", "stdout_matches_reference",}
REQUIRED_FIELDS = ("id", "title", "type")
KNOWN_TYPES = ("instruction", "completion", "parsons")


class ContentError(Exception):
    """Raised when a content file is malformed. Fail loudly at startup."""


# --- hints -----------------------------------------------------------------


def load_hints() -> dict[str, dict[str, Any]]:
    if not HINTS_FILE.exists():
        return {}
    with HINTS_FILE.open(encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ContentError(f"hints.json: invalid JSON — {exc}") from exc

    entries: dict[str, dict[str, Any]] = {}
    for entry in data.get("entries", []):
        if "id" not in entry or "title" not in entry:
            raise ContentError("hints.json: every entry needs an 'id' and a 'title'")
        if entry["id"] in entries:
            raise ContentError(f"hints.json: duplicate entry id '{entry['id']}'")
        entries[entry["id"]] = entry
    return entries


# --- lessons ---------------------------------------------------------------


def _validate(lesson: dict[str, Any], path: pathlib.Path, hints: dict[str, Any]) -> None:
    for field in REQUIRED_FIELDS:
        if field not in lesson:
            raise ContentError(f"{path.name}: missing required field '{field}'")

    if "order" in lesson:
    # Not harmful by itself, but an author editing it would expect the course to reorder, and it would not, so it's better to say so.
        raise ContentError(
        f"{path.name}: 'order' is no longer used - a lesson's place in the course comes from collections.json. Delete the field."
        )
    
    if lesson["type"] not in KNOWN_TYPES:
        raise ContentError(
            f"{path.name}: unknown type '{lesson['type']}' "
            f"(expected one of {', '.join(KNOWN_TYPES)})"
        )

    unknown_hints = [hint_id for hint_id in lesson.get("unlocks", []) if hint_id not in hints]
    if unknown_hints:
        raise ContentError(
            f"{path.name}: unlocks reference entries missing from hints.json: "
            f"{', '.join(unknown_hints)}"
        )

    missing_data = [name for name in lesson.get("datasets", []) if not (DATASET_DIR / name).is_file()]
    if missing_data:
        raise ContentError(
            f"{path.name}: datasets not found in content/datasets/: {', '.join(missing_data)}"
        )

    if lesson["type"] == "parsons":
        content = lesson.get("content", {})
        slot_ids = {
            line["id"] for line in content.get("lines", []) if line.get("kind") == "slot"
        }
        option_ids = {opt["id"] for opt in content.get("options", [])}
        solution = lesson.get("private", {}).get("solution", {})
        # One correct arrangement, or a list of acceptable alternatives.
        for alternative in solution if isinstance(solution, list) else [solution]:
            unknown_slots = set(alternative) - slot_ids
            if unknown_slots:
                raise ContentError(
                    f"{path.name}: solution refers to unknown slot(s) {sorted(unknown_slots)}"
                )
            unknown_options = set(alternative.values()) - option_ids
            if unknown_options:
                raise ContentError(
                    f"{path.name}: solution refers to unknown option(s) {sorted(unknown_options)}"
                )

    if lesson["type"] == "completion":
        _validate_completion(lesson, path, hints)


def _validate_completion(lesson: dict[str, Any], path: pathlib.Path, hints: dict[str, Any]) -> None:
    private = lesson.get("private", {})
    starter = lesson.get("content", {}).get("starterCode", "")

    if "validation" in private:
        raise ContentError(
            f"{path.name}: 'validation' was the old sketch format - replace it with a 'checks' list"
        )

    if "gapSolutions" in private:
        expected = gaps.count(starter)
        if len(private["gapSolutions"]) != expected:
            raise ContentError(
                f"{path.name}: starterCode has {expected} gap(s) but gapSolutions has "
                f"{len(private['gapSolutions'])} answer(s)"
            )
    has_reference = "gapSolutions" in private or "referenceSolution" in private

    seen: set[str] = set()
    for check in private.get("checks", []):
        try:
            check_spec.validate(check)
        except check_spec.CheckError as exc:
            raise ContentError(f"{path.name}: {exc}") from exc
        if check["id"] in seen:
            raise ContentError(f"{path.name}: duplicate check id '{check['id']}'")
        seen.add(check["id"])
        if check["type"] in NEEDS_REFERENCE and not has_reference:
            raise ContentError(
                f"{path.name}: check '{check['id']}' compares with the reference solution, but the lesson has neither gapSolutions nor referenceSolution"            )
        if check.get("hint") and check["hint"] not in hints:

            raise ContentError(
                f"{path.name}: check '{check['id']}' points at hint '{check['hint']}', which is not in hints.json")


def _content_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def load_all(hints: dict[str, Any]) -> list[dict[str, Any]]:
    return load_course(hints)[0]

def load_course(hints: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read every lesson file and collections.json and validate both."""
    lessons: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    unlocked_by: dict[str, str] = {}

    for path in sorted(LESSON_DIR.glob("*.json")):
        raw = path.read_text(encoding="utf-8")
        try:
            lesson = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ContentError(f"{path.name}: invalid JSON - {exc}") from exc
        _validate(lesson, path, hints)
        if lesson["id"] in seen_ids:
            raise ContentError(f"{path.name}: duplicate lesson id '{lesson['id']}'")
        seen_ids.add(lesson["id"])
        lesson.setdefault("version", 1)
        lesson["contentHash"] = _content_hash(raw)
        lessons.append(lesson)

    collections = load_collections({lesson["id"]: lesson for lesson in lessons})
    lessons.sort(key=lambda item: item["position"])

    # A hint should be unlocked by exactly one lesson
    # Unlocking it twice is almost certainly an authoring error, so it gets reported.
    for lesson in lessons:
        for hint_id in lesson.get("unlocks", []):
            if hint_id in unlocked_by:
                raise ContentError(
                    f"hint '{hint_id}' is unlocked by both '{unlocked_by[hint_id]}' "
                    f"and '{lesson['id']}' - it should belong to one lesson"
                )
            unlocked_by[hint_id] = lesson["id"]

    return lessons, collections

def load_collections(lessons_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if not COLLECTIONS_FILE.exists():
        raise ContentError(
            "collections.json is missing - the course needs it to know which lessons exist and in what order"
        )
    try:
        data = json.loads(COLLECTIONS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContentError(f"collections.json: invalid JSON - {exc}") from exc

    collections = data.get("collections", [])
    seen_collections: set[str] = set()
    placed: dict[str, str] = {}
    position = 0
    for collection in collections:
        if "id" not in collection or "title" not in collection:
            raise ContentError("collections.json: every collection needs an 'id' and a 'title'")
        if collection["id"] in seen_collections:
            raise ContentError(f"collections.json: duplicate collection id '{collection['id']}'")
        seen_collections.add(collection["id"])
        if not collection.get("lessons"):
            raise ContentError(f"collections.json: collection '{collection['id']}' has no lessons")

        for lesson_id in collection["lessons"]:
            if lesson_id not in lessons_by_id:
                raise ContentError(
                    f"collections.json: collection '{collection['id']}' lists '{lesson_id}', but no lesson file has that id"
                )
            if lesson_id in placed:
                raise ContentError(
                    f"collections.json: lesson '{lesson_id}' is listed in both '{placed[lesson_id]}' and '{collection['id']}'"
                )
            placed[lesson_id] = collection["id"]
            lessons_by_id[lesson_id]["collectionId"] = collection["id"]
            lessons_by_id[lesson_id]["position"] = position
            position += 1

    unplaced = sorted(set(lessons_by_id) - set(placed))
    if unplaced:
        raise ContentError(
            f"collections.json: these lessons are not in any collection, so no student could reach them: {', '.join(unplaced)}"
        )
    return collections


def public_view(lesson: dict[str, Any]) -> dict[str, Any]:
    # The version of a lesson that is safe to send to the browser.
    return {key: value for key, value in lesson.items() if key != "private"}


def summary(lesson: dict[str, Any]) -> dict[str, Any]:
    # The short form used by the lesson list.
    return {
        "id": lesson["id"],
        "collectionId": lesson["collectionId"],
        "position": lesson["position"],
        "title": lesson["title"],
        "type": lesson["type"],
        "version": lesson.get("version", 1),
        "concepts": lesson.get("concepts", []),
        "estimatedMinutes": lesson.get("estimatedMinutes"),
    }


def hints_for_lesson(
    lesson: dict[str, Any],
    lessons: list[dict[str, Any]],
    hints: dict[str, dict[str, Any]],
    include_all: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    new_ids = list(lesson.get("unlocks", []))
    new = [hints[hint_id] for hint_id in new_ids if hint_id in hints]

    earlier: list[dict[str, Any]] = []
    for other in reversed(lessons):  # walk backwards: most recent first
        if other["position"] >= lesson["position"]:
                        continue
        earlier.extend(
            hints[hint_id] for hint_id in other.get("unlocks", []) if hint_id in hints
        )

    if include_all:
        later: list[dict[str, Any]] = []
        for other in lessons:
            if other["position"] <= lesson["position"]:
                continue
            later.extend(
                hints[hint_id] for hint_id in other.get("unlocks", []) if hint_id in hints
            )
        earlier = earlier + later

    return {"new": new, "earlier": earlier}
