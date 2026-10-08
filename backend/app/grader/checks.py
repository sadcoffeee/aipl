from typing import Any

STRUCTURE = "structure"
BEHAVIOUR = "behaviour"

COMMON_FIELDS = {"id", "type", "required", "message", "hint"}
STRUCTURE_FIELDS = {"scope", "forbid"}

# type -> (family, required parameters, optional parameters)
SPEC: dict[str, tuple[str, set[str], set[str]]] = {
    # structure checks read the code
    "uses_operator": (STRUCTURE, {"operator"}, set()),

    "calls_function": (STRUCTURE, {"name"}, set()),

    "uses_subscript": (STRUCTURE, set(), {"on"}),

    "defines_variable": (STRUCTURE, {"name"}, set()),

    "uses_loop": (STRUCTURE, set(), {"kind"}),

    # behaviour checks run the code
    "variable_matches_reference": (BEHAVIOUR, {"variable"}, {"tolerance"}),

    "value_matches_reference": (BEHAVIOUR, {"variable"}, {"tolerance"}),

    "variable_equals": (BEHAVIOUR, {"variable", "value"}, {"tolerance"}),

    "variable_type": (BEHAVIOUR, {"variable", "valueType"}, set()),

    "stdout_matches_reference": (BEHAVIOUR, set(), {"numericTolerance"}),

    "stdout_contains": (BEHAVIOUR, {"text"}, {"caseSensitive"}),
}

KNOWN_OPERATORS = {
    ">", ">=", "<", "<=", "==", "!=", "in", "not in", "is", "is not", "+", "-", "*", "/", "//", "%", "**", "@", "and", "or", "not",
}

KNOWN_TYPES = {
    "int", "float", "number", "str", "bool", "list", "tuple", "dict", "ndarray", "array",
}


class CheckError(ValueError):
    """A check in a lesson file is malformed."""


def family(check: dict[str, Any]) -> str:
    return SPEC[check["type"]][0]


def validate(check: dict[str, Any]) -> None:
    """Fail loudly at startup on a malformed check, naming what is wrong."""
    if "id" not in check:
        raise CheckError(f"check without an 'id': {check}")
    check_id = check["id"]
    if check.get("type") not in SPEC:
        raise CheckError(
            f"check '{check_id}': unknown type '{check.get('type')}'. "
            f"Known types: {', '.join(sorted(SPEC))}"
        )

    kind, required, optional = SPEC[check["type"]]
    allowed = COMMON_FIELDS | required | optional
    if kind == STRUCTURE:
        allowed |= STRUCTURE_FIELDS

    missing = required - check.keys()
    if missing:
        raise CheckError(f"check '{check_id}' ({check['type']}) needs: {', '.join(sorted(missing))}")
    unknown = check.keys() - allowed
    if unknown:
        raise CheckError(
            f"check '{check_id}' ({check['type']}) does not take: {', '.join(sorted(unknown))}"
        )

    if check["type"] == "uses_operator":
        operators = check["operator"] if isinstance(check["operator"], list) else [check["operator"]]
        bad = [op for op in operators if op not in KNOWN_OPERATORS]
        if bad:
            raise CheckError(f"check '{check_id}': unknown operator(s) {bad}")
    if check["type"] == "variable_type" and check["valueType"] not in KNOWN_TYPES:
        raise CheckError(
            f"check '{check_id}': unknown valueType '{check['valueType']}'. "
            f"Known: {', '.join(sorted(KNOWN_TYPES))}"
        )
    if check["type"] == "uses_loop" and check.get("kind") not in (None, "for", "while", "comprehension"):
        raise CheckError(f"check '{check_id}': kind must be for, while or comprehension")
    if kind == STRUCTURE and check.get("scope", "all") not in ("all", "gaps"):
        raise CheckError(f"check '{check_id}': scope must be 'all' or 'gaps'")