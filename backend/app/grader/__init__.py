import ast
import pathlib
import time
from typing import Any

from . import checks as check_spec
from . import gaps, parsons, runner, structure

# Bump whenever grading logic changes in a way that could change a verdict. Stored with every evaluation.
GRADER_VERSION = "1"

DATASET_DIR = pathlib.Path(__file__).resolve().parents[2] / "content" / "datasets"


def reference_program(lesson: dict[str, Any]) -> str | None:
    """The full reference solution for a completion lesson, if it has one."""
    private = lesson.get("private", {})
    if "gapSolutions" in private:
        return gaps.fill(lesson["content"]["starterCode"], private["gapSolutions"])
    return private.get("referenceSolution")


def grade(lesson: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any] | None:
    """Evaluate one submission. Returns None for lessons with nothing to grade."""
    started = time.perf_counter()
    if lesson["type"] == "parsons":
        result = parsons.grade(lesson, payload.get("placements") or {})
    elif lesson["type"] == "completion":
        result = _grade_completion(lesson, payload.get("code") or "")
    else:
        return None
    result["graderVersion"] = GRADER_VERSION
    result["durationMs"] = round((time.perf_counter() - started) * 1000)
    return result


def _grade_completion(lesson: dict[str, Any], code: str) -> dict[str, Any]:
    starter = lesson["content"]["starterCode"]
    all_checks = lesson.get("private", {}).get("checks", [])
    result: dict[str, Any] = {
        "status": None, "solved": None, "error": None,
        "gaps": None, "checks": [], "stdout": None,
    }

    # Step 1 - what did the student type into each gap?
    gap_contents = gaps.extract(starter, code) if gaps.count(starter) else None
    if gap_contents is not None:
        result["gaps"] = [
            {"index": i + 1, "content": content, "empty": not content.strip()}
            for i, content in enumerate(gap_contents)
        ]
        if any(g["empty"] for g in result["gaps"]):
            # Left something blank. No point running it; say which.
            result["status"], result["solved"] = "incomplete", False
            return result

    # Step 2 - is it Python at all? ast.parse refuses anything that isn't
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        result["status"], result["solved"] = "syntax_error", False
        result["error"] = {"type": "SyntaxError", "message": exc.msg, "line": exc.lineno}
        return result

    # Step 3 - structure checks: read the tree, no execution.
    structure_checks = [c for c in all_checks if check_spec.family(c) == check_spec.STRUCTURE]
    result["checks"].extend(structure.run(tree, structure_checks, gap_contents))

    # Step 4 - run it (and the reference) in a separate process, and evaluate the behaviour checks there.
    behaviour_checks = [c for c in all_checks if check_spec.family(c) == check_spec.BEHAVIOUR]
    datasets = [DATASET_DIR / name for name in lesson.get("datasets", [])]
    outcome = runner.run(
        student=code,
        reference=reference_program(lesson),
        # The child only needs what it evaluates; messages and hints stay here.
        checks=[{k: v for k, v in c.items() if k not in ("message", "hint")} for c in behaviour_checks],
        datasets=datasets,
    )

    if outcome.get("timeout"):
        result["status"], result["solved"] = "timeout", False
        return result
    if outcome.get("crashed"):
        result["status"] = "grader_error"
        result["error"] = {"type": "GraderCrash", "message": outcome.get("stderr", ""), "line": None}
        return result

    student = outcome["student"]
    result["stdout"] = student["stdout"]

    if outcome.get("authoringError") and (outcome.get("reference") or {}).get("error"):
        # The reference solution crashed: the lesson is broken, not the student.
        result["status"] = "grader_error"
        result["error"] = {"type": "AuthoringError", "message": outcome["authoringError"], "line": None}
        return result

    if student["error"]:
        result["status"], result["solved"] = "runtime_error", False
        result["error"] = student["error"]
        return result

    # Step 5 - attach each behaviour result to its check's metadata.
    by_id = {r["id"]: r for r in outcome["checks"]}
    for check in behaviour_checks:
        evaluated = by_id.get(check["id"], {"passed": None, "detail": "not evaluated"})
        result["checks"].append(
            {
                "id": check["id"],
                "type": check["type"],
                "family": "behaviour",
                "required": check.get("required", True),
                "passed": evaluated["passed"],
                "detail": evaluated["detail"],
                "message": check.get("message"),
                "hint": check.get("hint"),
            }
        )

    if outcome.get("authoringError"):
        result["status"] = "grader_error"
        result["error"] = {"type": "AuthoringError", "message": outcome["authoringError"], "line": None}
        return result

    # Step 6 - the verdict: solved if every *required* check passed. A lesson with no checks at all is solved by running without error.
    required = [c for c in result["checks"] if c["required"]]
    solved = all(c["passed"] for c in required)
    result["status"], result["solved"] = ("passed" if solved else "failed"), solved
    return result