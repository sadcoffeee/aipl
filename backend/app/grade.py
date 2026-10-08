""" The way to grade directly from command-line

    python -m app.grade --all
    Runs every lesson, grades its own reference solution, and report any failures.

    
    python -m app.grade l020-parsons-mean --place s1=o3 s2=o2
    Grade a Parson's lesson with the given placements (slot=option)
    
    python -m app.grade l030-completion-addition --gaps "a + b" "c"
    Grade a completion lesson with the given answers for each gap, in order

"""

import argparse
import json
import pathlib
import sys
from typing import Any

from . import content, grader
from .grader import gaps

MARK = {True: "✓", False: "X", None: "?"}


def _lessons() -> dict[str, dict[str, Any]]:
    hints = content.load_hints()
    return {lesson["id"]: lesson for lesson in content.load_all(hints)}


def _reference_payload(lesson: dict[str, Any]) -> dict[str, Any] | None:
    if lesson["type"] == "completion":
        program = grader.reference_program(lesson)
        return {"code": program} if program is not None else None
    if lesson["type"] == "parsons":
        solution = lesson.get("private", {}).get("solution")
        if isinstance(solution, list):
            solution = solution[0]
        return {"placements": solution} if solution else None
    return None


def _print(lesson: dict[str, Any], evaluation: dict[str, Any], verbose: bool) -> None:
    print(f"{lesson['id']}: {evaluation['status'].upper()}  (solved={evaluation['solved']}, "
          f"{evaluation['durationMs']} ms)")
    if evaluation.get("error"):
        error = evaluation["error"]
        where = f" on line {error['line']}" if error.get("line") else ""
        print(f"  error{where}: {error['type']}: {error['message']}")
    for gap in evaluation.get("gaps") or []:
        if verbose or gap["empty"]:
            shown = gap["content"] if gap["content"].strip() else "(empty)"
            print(f"  gap {gap['index']}: {shown}")
    for check in evaluation.get("checks", []):
        if verbose or check["passed"] is not True:
            tag = "required" if check["required"] else "diagnostic"
            print(f"  {MARK[check['passed']]} {check['id']:<24} {check['family']:<10} {tag:<10} {check['detail']}")
            if check["passed"] is False and check.get("message") and verbose:
                print(f"      message: {check['message']}")
    for slot in evaluation.get("slots") or []:
        if verbose or not slot["correct"]:
            state = ("correct" if slot["correct"] else "misplaced" if slot["misplaced"]
                     else "distractor" if slot["distractor"] else "empty" if not slot["chosen"] else "wrong")
            print(f"  {MARK[slot['correct']]} {slot['slot']:<6} {str(slot['chosen']):<6} {state}"
                  + (f" — {slot['note']}" if slot.get("note") else ""))
    if verbose and evaluation.get("stdout"):
        print("  printed:")
        for line in evaluation["stdout"].rstrip().splitlines()[:10]:
            print(f"    {line}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Try the grader on a lesson.")
    parser.add_argument("lesson", nargs="?", help="lesson id")
    parser.add_argument("--all", action="store_true", help="self-check every lesson")
    parser.add_argument("--gaps", nargs="+", metavar="ANSWER", help="answers for each gap, in order")
    parser.add_argument("--file", type=pathlib.Path, help="a whole program to grade")
    parser.add_argument("--place", nargs="+", metavar="SLOT=OPTION", help="Parson's placements")
    parser.add_argument("--json", action="store_true", help="print the raw evaluation")
    args = parser.parse_args()

    try:
        lessons = _lessons()
    except content.ContentError as exc:
        print(f"Content error: {exc}")
        return 1

    if args.all:
        failures = 0
        for lesson in lessons.values():
            payload = _reference_payload(lesson)
            if payload is None:
                continue
            evaluation = grader.grade(lesson, payload)
            ok = evaluation["status"] == "passed"
            failures += not ok
            if ok:
                print(f"✓ {lesson['id']}: reference passes its own checks")
            else:
                _print(lesson, evaluation, verbose=False)
        print(f"\n{'All lessons OK.' if not failures else f'{failures} lesson(s) need attention.'}")
        return 1 if failures else 0

    if not args.lesson:
        parser.print_help()
        return 1
    lesson = lessons.get(args.lesson)
    if lesson is None:
        print(f"No lesson '{args.lesson}'. Known: {', '.join(lessons)}")
        return 1

    if args.gaps:
        payload = {"code": gaps.fill(lesson["content"]["starterCode"], args.gaps)}
    elif args.file:
        payload = {"code": args.file.read_text(encoding="utf-8")}
    elif args.place:
        payload = {"placements": dict(item.split("=", 1) for item in args.place)}
    else:
        payload = _reference_payload(lesson)
        if payload is None:
            print("This lesson has nothing to grade.")
            return 1
        print("(grading the lesson's own reference solution)\n")

    evaluation = grader.grade(lesson, payload)
    if evaluation is None:
        print("This lesson has nothing to grade.")
        return 1
    if args.json:
        print(json.dumps(evaluation, indent=2, ensure_ascii=False))
    else:
        _print(lesson, evaluation, verbose=True)
    return 0 if evaluation["status"] == "passed" else 2


if __name__ == "__main__":
    sys.exit(main())