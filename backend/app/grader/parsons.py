from typing import Any


def grade(lesson: dict[str, Any], placements: dict[str, str | None]) -> dict[str, Any]:
    private = lesson.get("private", {})
    solution = private.get("solution", {})
    alternatives = solution if isinstance(solution, list) else [solution]
    notes = private.get("distractorNotes", {})

    slot_ids = [
        line["id"] for line in lesson["content"]["lines"] if line.get("kind") == "slot"
    ]
    used_somewhere = {option for alt in alternatives for option in alt.values()}

    # Diagnose against whichever correct arrangement the student is closest to.
    best = max(
        alternatives,
        key=lambda alt: sum(placements.get(slot) == alt.get(slot) for slot in slot_ids),
    )

    slots = []
    for slot in slot_ids:
        chosen = placements.get(slot)
        correct = chosen is not None and chosen == best.get(slot)
        slots.append(
            {
                "slot": slot,
                "chosen": chosen,
                "correct": correct,
                "misplaced": bool(chosen) and not correct and chosen in best.values(),
                "distractor": bool(chosen) and chosen not in used_somewhere,
                "note": notes.get(chosen) if chosen else None,
            }
        )

    empty = [s["slot"] for s in slots if s["chosen"] is None]
    solved = any(all(placements.get(slot) == alt.get(slot) for slot in slot_ids) for alt in alternatives)

    if empty:
        status = "incomplete"
    else:
        status = "passed" if solved else "failed"

    return {
        "status": status,
        "solved": status == "passed",
        "error": None,
        "slots": slots,
        "emptySlots": empty,
        "checks": [],
    }