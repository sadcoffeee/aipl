import builtins
import io
import json
import math
import os
import random
import sys
import traceback
import types

try:
    import numpy as np
except ImportError:
    np = None


# --------------------------------------------------------------------------
# Guard rails
# --------------------------------------------------------------------------

# Events that are refused outright
BLOCKED_EVENTS = {
    "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
    "os.kill", "os.killpg", "os.chdir", "subprocess.Popen", "pty.spawn",
    "socket.connect", "socket.bind", "socket.sendto", "socket.getaddrinfo",
    "socket.gethostbyname", "urllib.Request", "http.client.connect",
    "ctypes.dlopen", "ctypes.dlsym", "ctypes.call_function", "webbrowser.open",
    "os.symlink", "os.link", "os.chown", "os.chmod",
}

# Events that change something on disk: allowed only inside the task folder.
MODIFY_EVENTS = {
    "os.remove", "os.rmdir", "os.rename", "os.mkdir", "os.truncate", "os.utime",
    "shutil.rmtree", "shutil.copyfile", "shutil.move",
}

# Events that only look: allowed wherever reading is. 
LIST_EVENTS = {"os.listdir", "os.scandir", "glob.glob"}


def _norm(path) -> str:
    # Pure string work on purpose: no filesystem calls inside the hook, so the hook cannot trigger further audit events while it runs.
    return os.path.normcase(os.path.normpath(os.path.abspath(os.fsdecode(path))))


def _inside(path: str, roots: list[str]) -> bool:
    return any(path == root or path.startswith(root + os.sep) for root in roots)


def _install_guard(workdir: str) -> None:
    work = [_norm(workdir)]
    # Reading is also allowed from Python's own installation, so that import pandas and friends can load their files.
    readable = work + sorted(
        {_norm(p) for p in (sys.prefix, sys.base_prefix, sys.exec_prefix,
                            sys.base_exec_prefix, *sys.path) if p}
    ) + [_norm(os.devnull)]

    def hook(event: str, args: tuple) -> None:
        if event in BLOCKED_EVENTS or event.startswith("os.exec") or event.startswith("os.spawn"):
            raise PermissionError(f"blocked by the grader: {event}")

        if event == "open":
            path, mode, flags = (list(args) + [None, None, None])[:3]
            if path is None or isinstance(path, int):
                return  # an already-open file descriptor
            writing = False
            if isinstance(mode, str):
                writing = any(ch in mode for ch in "wax+")
            if isinstance(flags, int):
                writing = writing or bool(
                    flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
                )
            target = _norm(path)
            roots = work if writing else readable
            if not _inside(target, roots):
                raise PermissionError(f"blocked by the grader: cannot open {os.fsdecode(path)}")
            return

        if event == "sqlite3.connect":
            # sqlite opens files from C, not through Python's open(), so it needs its own rule
            database = args[0] if args else None
            if database not in (":memory:", "", None) and not _inside(_norm(database), work):
                raise PermissionError("blocked by the grader: sqlite3 outside the task folder")
            return

        if event in MODIFY_EVENTS or event in LIST_EVENTS:
            roots = work if event in MODIFY_EVENTS else readable
            for value in args:
                if isinstance(value, (str, bytes, os.PathLike)):
                    if not _inside(_norm(value), roots):
                        raise PermissionError(f"blocked by the grader: {event} outside the task folder")

    sys.addaudithook(hook)  # cannot be removed once added


def _apply_limits(limits: dict) -> None:
    """CPU time, memory and file size caps. POSIX only; skipped on Windows."""
    try:
        import resource
    except ImportError:
        return
    cpu = int(limits.get("cpuSeconds", 5))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
    file_bytes = int(limits.get("fileMB", 20)) * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_bytes, file_bytes))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    memory = int(limits.get("memoryMB", 0)) * 1024 * 1024
    if memory:
        try:
            resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        except (ValueError, OSError):
            pass


def _seed() -> None:
    """Same randomness for reference and student, so random tasks compare."""
    random.seed(0)
    if np is not None:
        np.random.seed(0)


# --------------------------------------------------------------------------
# Running code
# --------------------------------------------------------------------------


class _CappedText(io.StringIO):
    """Captures printed output, but stops growing past a limit."""

    def __init__(self, limit: int) -> None:
        super().__init__()
        self.limit = limit
        self.truncated = False

    def write(self, text: str) -> int:
        room = self.limit - self.tell()
        if room <= 0:
            self.truncated = True
            return len(text)
        if len(text) > room:
            self.truncated = True
            super().write(text[:room])
            return len(text)
        return super().write(text)


def _describe_error(exc: BaseException, filename: str) -> dict:
    line = None
    if isinstance(exc, SyntaxError) and exc.filename == filename:
        line = exc.lineno
    for frame, lineno in traceback.walk_tb(exc.__traceback__):
        if frame.f_code.co_filename == filename:
            line = lineno  # keep the deepest frame that is the student's
    message = str(exc)
    return {
        "type": type(exc).__name__,
        "message": message[:500],
        "line": line,
    }


def _execute(code: str, filename: str, stdout_limit: int) -> dict:
    namespace: dict = {"__name__": "__main__", "__builtins__": builtins}
    out = _CappedText(stdout_limit)
    err = _CappedText(4000)
    saved = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    error = None
    try:
        compiled = compile(code, filename, "exec")
        _seed()
        exec(compiled, namespace)
    except SystemExit:
        pass  # exit() just ends the program; not an error
    except BaseException as exc:
        error = _describe_error(exc, filename)
    finally:
        sys.stdout, sys.stderr = saved
    return {
        "namespace": namespace,
        "stdout": out.getvalue(),
        "stdoutTruncated": out.truncated,
        "stderr": err.getvalue(),
        "error": error,
    }


# --------------------------------------------------------------------------
# Comparing values
# --------------------------------------------------------------------------


def _is_bool(value) -> bool:
    return isinstance(value, bool) or (np is not None and isinstance(value, np.bool_))


def _is_number(value) -> bool:
    if _is_bool(value):
        return False
    if isinstance(value, (int, float)):
        return True
    return np is not None and isinstance(value, np.number)


def _shape_of(value) -> str:
    if np is not None and isinstance(value, np.ndarray):
        return f"array of shape {value.shape}"
    if isinstance(value, (list, tuple, dict, str)):
        return f"{type(value).__name__} of length {len(value)}"
    return type(value).__name__


def compare(got, expected, tolerance: float) -> tuple[bool, str]:
    """Is `got` the same value as `expected`? Returns (equal, why-not)."""
    # Arrays (or an array compared with a list): same shape, then values.
    if np is not None and (isinstance(got, np.ndarray) or isinstance(expected, np.ndarray)):
        try:
            got_arr, exp_arr = np.asarray(got), np.asarray(expected)
        except Exception:
            return False, f"got a {_shape_of(got)}, which is not array-like"
        if got_arr.shape != exp_arr.shape:
            return False, f"shape differs: got {got_arr.shape}, expected {exp_arr.shape}"
        try:
            if got_arr.dtype.kind in "fc" or exp_arr.dtype.kind in "fc":
                same = bool(np.allclose(got_arr, exp_arr, rtol=tolerance, atol=tolerance, equal_nan=True))
            else:
                same = bool(np.array_equal(got_arr, exp_arr))
        except TypeError:
            return False, f"got a {got_arr.dtype} array, expected {exp_arr.dtype}"
        return same, "values match" if same else "same shape, but the values differ"

    if _is_bool(got) or _is_bool(expected):
        if not (_is_bool(got) and _is_bool(expected)):
            return False, f"expected True/False, got a {_shape_of(got)}"
        same = bool(got) == bool(expected)
        return same, "matches" if same else "the opposite truth value"

    if _is_number(got) and _is_number(expected):
        same = math.isclose(float(got), float(expected), rel_tol=tolerance, abs_tol=tolerance)
        return same, "matches" if same else "the number differs"

    if isinstance(got, (list, tuple)) and isinstance(expected, (list, tuple)):
        if len(got) != len(expected):
            return False, f"length differs: got {len(got)}, expected {len(expected)}"
        for index, (a, b) in enumerate(zip(got, expected)):
            same, why = compare(a, b, tolerance)
            if not same:
                return False, f"element {index} differs ({why})"
        return True, "matches"

    if isinstance(got, dict) and isinstance(expected, dict):
        if set(got) != set(expected):
            return False, "different keys"
        for key in expected:
            same, why = compare(got[key], expected[key], tolerance)
            if not same:
                return False, f"value for {key!r} differs ({why})"
        return True, "matches"

    if type(got) is not type(expected) and not (isinstance(got, str) and isinstance(expected, str)):
        return False, f"got a {type(got).__name__}, expected a {type(expected).__name__}"
    try:
        same = bool(got == expected)
    except Exception:
        same = False
    return same, "matches" if same else "the value differs"


def _candidates(namespace: dict):
    """Variables a student could plausibly have meant as an answer."""
    for name, value in namespace.items():
        if name.startswith("_"):
            continue
        if isinstance(value, (types.ModuleType, types.FunctionType, type)):
            continue
        if callable(value) and not (np is not None and isinstance(value, np.ndarray)):
            continue
        yield name, value


VALUE_TYPES = {
    "int": lambda v: (isinstance(v, int) or (np is not None and isinstance(v, np.integer))) and not _is_bool(v),
    "float": lambda v: isinstance(v, float) or (np is not None and isinstance(v, np.floating)),
    "number": _is_number,
    "str": lambda v: isinstance(v, str),
    "bool": _is_bool,
    "list": lambda v: isinstance(v, list),
    "tuple": lambda v: isinstance(v, tuple),
    "dict": lambda v: isinstance(v, dict),
    "ndarray": lambda v: np is not None and isinstance(v, np.ndarray),
    "array": lambda v: isinstance(v, (list, tuple)) or (np is not None and isinstance(v, np.ndarray)),
}


def _tokens(text: str) -> list[str]:
    return text.split()


def _tokens_match(got: str, expected: str, tolerance: float) -> bool:
    try:
        return math.isclose(float(got), float(expected), rel_tol=tolerance, abs_tol=tolerance)
    except ValueError:
        return got == expected


# --------------------------------------------------------------------------
# Behaviour checks - one function per type in checks.py
# --------------------------------------------------------------------------


class AuthoringError(Exception):
    """The check cannot be evaluated because the lesson itself is wrong."""


def _need_reference(reference, name=None):
    if reference is None:
        raise AuthoringError("this check needs a reference solution, and the lesson has none")
    if name is not None and name not in reference["namespace"]:
        raise AuthoringError(f"the reference solution does not define `{name}`")


def check_variable_matches_reference(check, student, reference):
    name = check["variable"]
    _need_reference(reference, name)
    if name not in student["namespace"]:
        return False, f"`{name}` is not defined"
    return compare(student["namespace"][name], reference["namespace"][name], check.get("tolerance", 1e-6))


def check_value_matches_reference(check, student, reference):
    name = check["variable"]
    _need_reference(reference, name)
    expected = reference["namespace"][name]
    for candidate, value in _candidates(student["namespace"]):
        if compare(value, expected, check.get("tolerance", 1e-6))[0]:
            return True, f"found in `{candidate}`"
    return False, "no variable holds the expected value"


def check_variable_equals(check, student, reference):
    name = check["variable"]
    if name not in student["namespace"]:
        return False, f"`{name}` is not defined"
    return compare(student["namespace"][name], check["value"], check.get("tolerance", 1e-6))


def check_variable_type(check, student, reference):
    name = check["variable"]
    if name not in student["namespace"]:
        return False, f"`{name}` is not defined"
    value = student["namespace"][name]
    ok = VALUE_TYPES[check["valueType"]](value)
    return ok, f"is a {_shape_of(value)}"


def check_stdout_matches_reference(check, student, reference):
    _need_reference(reference)
    got, expected = _tokens(student["stdout"]), _tokens(reference["stdout"])
    if not expected and not got:
        return True, "neither printed anything"
    if not got:
        return False, "nothing was printed"
    if len(got) != len(expected):
        return False, f"printed {len(got)} item(s), expected {len(expected)}"
    tolerance = check.get("numericTolerance", 1e-6)
    for index, (a, b) in enumerate(zip(got, expected)):
        if not _tokens_match(a, b, tolerance):
            return False, f"printed item {index + 1} differs"
    return True, "output matches"


def check_stdout_contains(check, student, reference):
    text, out = check["text"], student["stdout"]
    if not check.get("caseSensitive", False):
        text, out = text.lower(), out.lower()
    return (text in out), ("found" if text in out else "not found in the output")


BEHAVIOUR_CHECKS = {
    "variable_matches_reference": check_variable_matches_reference,
    "value_matches_reference": check_value_matches_reference,
    "variable_equals": check_variable_equals,
    "variable_type": check_variable_type,
    "stdout_matches_reference": check_stdout_matches_reference,
    "stdout_contains": check_stdout_contains,
}


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main() -> None:
    real_stdout = sys.stdout
    job = json.loads(sys.stdin.read())
    nonce = job["nonce"]

    _apply_limits(job.get("limits", {}))
    _install_guard(os.getcwd())

    limit = int(job.get("stdoutLimit", 20000))
    result: dict = {"reference": None, "student": None, "checks": [], "authoringError": None}

    reference = None
    if job.get("reference") is not None:
        reference = _execute(job["reference"], "<reference>", limit)
        result["reference"] = {"error": reference["error"]}
        if reference["error"]:
            result["authoringError"] = (
                "the reference solution itself fails: "
                f"{reference['error']['type']}: {reference['error']['message']}"
            )

    student = _execute(job["student"], "<student>", limit)
    result["student"] = {
        "stdout": student["stdout"],
        "stdoutTruncated": student["stdoutTruncated"],
        "stderr": student["stderr"][-2000:],
        "error": student["error"],
    }

    # Checks only make sense on a program that ran to the end.
    if student["error"] is None and result["authoringError"] is None:
        for check in job.get("checks", []):
            try:
                passed, detail = BEHAVIOUR_CHECKS[check["type"]](check, student, reference)
                result["checks"].append({"id": check["id"], "passed": bool(passed), "detail": detail})
            except AuthoringError as exc:
                result["checks"].append({"id": check["id"], "passed": None, "detail": str(exc)})
                result["authoringError"] = f"check '{check['id']}': {exc}"
            except Exception as exc:
                result["checks"].append(
                    {"id": check["id"], "passed": False, "detail": f"could not compare ({type(exc).__name__})"}
                )

    real_stdout.write(nonce + json.dumps(result) + "\n")
    real_stdout.flush()


if __name__ == "__main__":
    main()