import re

GAP_MARKER = re.compile(r"\{\{gap(?::([^}]*))?\}\}")


def _normalise(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def count(starter: str) -> int:
    return len(GAP_MARKER.findall(starter))


def pieces(starter: str) -> list[str]:
    """The fixed text around the gaps: always one more piece than gaps."""
    return GAP_MARKER.split(_normalise(starter))[::2]


def fill(starter: str, answers: list[str]) -> str:
    """Put answers into the gaps, in order. Used to build the reference."""
    fixed = pieces(starter)
    if len(answers) != len(fixed) - 1:
        raise ValueError(f"{len(fixed) - 1} gaps but {len(answers)} answers")
    out = [fixed[0]]
    for answer, piece in zip(answers, fixed[1:]):
        out.extend([answer, piece])
    return "".join(out)


def extract(starter: str, submitted: str) -> list[str] | None:
    """What the student typed into each gap, or None if the scaffold changed"""
    fixed = pieces(starter)
    if len(fixed) < 2:
        return None  # no gaps in this lesson
    pattern = "^" + "(.*?)".join(re.escape(piece) for piece in fixed) + "$"
    match = re.match(pattern, _normalise(submitted), flags=re.DOTALL)
    return list(match.groups()) if match else None