import ast
from typing import Any, Callable, Iterable

# Operator symbols -> the node class Python uses for them.
OPERATORS: dict[str, type] = {
    ">": ast.Gt, ">=": ast.GtE, "<": ast.Lt, "<=": ast.LtE,
    "==": ast.Eq, "!=": ast.NotEq, "in": ast.In, "not in": ast.NotIn,
    "is": ast.Is, "is not": ast.IsNot,
    "+": ast.Add, "-": ast.Sub, "*": ast.Mult, "/": ast.Div,
    "//": ast.FloorDiv, "%": ast.Mod, "**": ast.Pow, "@": ast.MatMult,
    "and": ast.And, "or": ast.Or, "not": ast.Not,
}


def import_aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                aliases[local] = alias.name if alias.asname else alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return aliases


def dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted_name(node.value)
        return f"{base}.{node.attr}" if base else f".{node.attr}"
    return None


def _resolve(name: str, aliases: dict[str, str]) -> str:
    head, _, rest = name.partition(".")
    real = aliases.get(head)
    if real is None:
        return name
    return f"{real}.{rest}" if rest else real


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


# --- the checks ------------------------------------------------------------


def _uses_operator(nodes, check, aliases):
    wanted = tuple(OPERATORS[op] for op in _as_list(check["operator"]))
    for node in nodes:
        ops: list[ast.AST] = []
        if isinstance(node, ast.Compare):
            ops = list(node.ops)
        elif isinstance(node, (ast.BinOp, ast.AugAssign)):
            ops = [node.op]
        elif isinstance(node, ast.BoolOp):
            ops = [node.op]
        elif isinstance(node, ast.UnaryOp):
            ops = [node.op]
        if any(isinstance(op, wanted) for op in ops):
            return True, f"found on line {getattr(node, 'lineno', '?')}"
    return False, f"no {' / '.join(_as_list(check['operator']))} found"


def _calls_function(nodes, check, aliases):
    wanted = _as_list(check["name"])
    for node in nodes:
        if not isinstance(node, ast.Call):
            continue
        raw = dotted_name(node.func)
        if raw is None:
            continue
        resolved = _resolve(raw, aliases)
        for name in wanted:
            # ".mean" matches any method or function called mean.
            if name.startswith(".") and (raw.endswith(name) or raw == name[1:]):
                return True, f"{raw}() on line {node.lineno}"
            if name in (raw, resolved):
                return True, f"{raw}() on line {node.lineno}"
    return False, f"no call to {' / '.join(wanted)}"


def _uses_subscript(nodes, check, aliases):
    target = check.get("on")
    for node in nodes:
        if isinstance(node, ast.Subscript):
            if target is None or (isinstance(node.value, ast.Name) and node.value.id == target):
                return True, f"found on line {node.lineno}"
    return False, f"no indexing of {target}" if target else "no indexing with [...]"


def _assigned_names(node: ast.AST) -> Iterable[str]:
    if isinstance(node, ast.Name):
        yield node.id
    elif isinstance(node, (ast.Tuple, ast.List)):
        for element in node.elts:
            yield from _assigned_names(element)
    elif isinstance(node, ast.Starred):
        yield from _assigned_names(node.value)


def _defines_variable(nodes, check, aliases):
    for node in nodes:
        targets: list[ast.AST] = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.NamedExpr)):
            targets = [node.target]
        elif isinstance(node, (ast.For, ast.comprehension)):
            targets = [node.target]
        for target in targets:
            if check["name"] in _assigned_names(target):
                return True, f"assigned on line {getattr(node, 'lineno', '?')}"
    return False, f"{check['name']} is never assigned"


LOOP_NODES: dict[str | None, tuple[type, ...]] = {
    "for": (ast.For,),
    "while": (ast.While,),
    "comprehension": (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp),
    None: (ast.For, ast.While),
}


def _uses_loop(nodes, check, aliases):
    kinds = LOOP_NODES[check.get("kind")]
    for node in nodes:
        if isinstance(node, kinds):
            return True, f"found on line {getattr(node, 'lineno', '?')}"
    return False, f"no {check.get('kind') or 'for/while'} loop"


IMPLEMENTATIONS: dict[str, Callable[..., tuple[bool, str]]] = {
    "uses_operator": _uses_operator,
    "calls_function": _calls_function,
    "uses_subscript": _uses_subscript,
    "defines_variable": _defines_variable,
    "uses_loop": _uses_loop,
}


def _parse_fragment(source: str) -> ast.AST | None:
    """A gap's content on its own: usually an expression, sometimes a statement."""
    for mode in ("eval", "exec"):
        try:
            return ast.parse(source.strip(), mode=mode)
        except SyntaxError:
            continue
    return None


def run(
    tree: ast.AST,
    checks: list[dict[str, Any]],
    gap_contents: list[str] | None,
) -> list[dict[str, Any]]:
    aliases = import_aliases(tree)
    whole = list(ast.walk(tree))

    gap_nodes: list[ast.AST] | None = None
    if gap_contents is not None:
        gap_nodes = []
        for content in gap_contents:
            fragment = _parse_fragment(content)
            if fragment is not None:
                gap_nodes.extend(ast.walk(fragment))

    results = []
    for check in checks:
        note = None
        nodes = whole
        if check.get("scope") == "gaps":
            if gap_nodes is None:
                note = "gaps not found in submission; checked whole program"
            else:
                nodes = gap_nodes

        found, detail = IMPLEMENTATIONS[check["type"]](nodes, check, aliases)
        passed = (not found) if check.get("forbid") else found
        if check.get("forbid"):
            detail = f"forbidden construct present ({detail})" if found else "absent, as required"

        results.append(
            {
                "id": check["id"],
                "type": check["type"],
                "family": "structure",
                "required": check.get("required", True),
                "passed": passed,
                "detail": detail + (f" - {note}" if note else ""),
                "message": check.get("message"),
                "hint": check.get("hint"),
            }
        )
    return results