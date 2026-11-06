from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import time

from . import config
from .grader import runner

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]

# Every probe tries something student code must not be able to do. True in the result = it got through.
ESCAPE_PROBES = r'''
import json, os, socket
found = {}

def attempt(name, action):
    try:
        action()
        found[name] = True
    except Exception as exc:
        found[name] = False

def connect_out():
    socket.create_connection(("1.1.1.1", 53), timeout=2).close()

def reach_backend():
    socket.create_connection(("127.0.0.1", 8001), timeout=2).close()

def read_backend_files():
    open(BACKEND + "/app/config.py").read()

def write_outside():
    open("/etc/aipl-probe", "w").write("x")

def see_docker_socket():
    if not os.path.exists("/var/run/docker.sock"):
        raise FileNotFoundError

def see_models():
    os.listdir("/models")

attempt("network: connect to the internet", connect_out)
attempt("network: connect to the backend on :8001", reach_backend)
attempt("files: read the backend's source code", read_backend_files)
attempt("files: write outside the scratch folder", write_outside)
attempt("files: see the Docker socket", see_docker_socket)
attempt("files: list the model weights in /models", see_models)
found["runs as root"] = os.getuid() == 0
print(json.dumps(found))
'''


def _status(ok: bool) -> str:
    return "  ok  " if ok else " FAIL "


def main() -> int:
    print(f"Sandbox mode : {config.GRADER_SANDBOX}")
    if config.GRADER_SANDBOX == "docker":
        print(f"Image        : {config.GRADER_IMAGE}")
    print()
    problems = 0

    # 1 - an ordinary program, with the guard on, exactly like real grading.
    with tempfile.TemporaryDirectory() as tmp:
        dataset = pathlib.Path(tmp) / "probe_data.txt"
        dataset.write_text("1 2 3\n", encoding="utf-8")
        started = time.perf_counter()
        outcome = runner.run(
            student="import numpy as np\nvalues = np.loadtxt('probe_data.txt')\nprint('sum', values.sum())",
            reference=None, checks=[], datasets=[dataset],
        )
        elapsed = time.perf_counter() - started
    if outcome.get("crashed") or outcome.get("timeout"):
        print(f"[{_status(False)}] a simple program could not run at all:")
        print("        " + (outcome.get("stderr") or "timed out").strip().replace("\n", "\n        "))
        print("\nNothing else can be checked until this works. Things to check:")
        print("  - is the image built?            bash deploy/run.sh grader build")
        print("  - can this container use Docker?  docker ps")
        return 1
    student = outcome["student"]
    ok = student["error"] is None and student["stdout"].strip() == "sum 6.0"
    problems += not ok
    print(f"[{_status(ok)}] simple program ran in {elapsed:.1f}s (dataset readable, numpy available)")
    if not ok:
        print(f"        got stdout={student['stdout']!r} error={student['error']}")

    # 2 - escape attempts with the audit hook OFF, so this tests the sandbox and nothing else.
    outcome = runner.run(
        student=f"BACKEND = {str(BACKEND_DIR)!r}\n" + ESCAPE_PROBES,
        reference=None, checks=[], datasets=[], guard=False,
    )
    try:
        found = json.loads(outcome["student"]["stdout"].strip().splitlines()[-1])
    except (KeyError, IndexError, ValueError, TypeError):
        print(f"[{_status(False)}] the escape probe did not report back: {outcome}")
        return 1
    print("\nWith the grader's audit hook switched off, student code could...")
    for name, got_through in found.items():
        problems += got_through
        print(f"[{_status(not got_through)}] {name}: {'YES' if got_through else 'no'}")

    # 3 - runaway programs.
    print()
    for label, program in (
        ("busy loop is stopped", "while True:\n    pass"),
        ("sleeping program is stopped", "import time\ntime.sleep(3600)"),
    ):
        started = time.perf_counter()
        outcome = runner.run(student=program, reference=None, checks=[], datasets=[])
        elapsed = time.perf_counter() - started
        stopped = bool(outcome.get("timeout") or outcome.get("crashed") or (outcome.get("student") or {}).get("error"))
        problems += not stopped
        print(f"[{_status(stopped)}] {label} (after {elapsed:.1f}s)")

    if config.GRADER_SANDBOX == "docker":
        # Rootless Docker silently drops limits it can't enforce, with only a warning on stderr. Show those warnings.
        limits = subprocess.run(
            [config.GRADER_DOCKER, "run", "--rm", "--pull", "never", "--network", "none",
             "--memory", f"{config.GRADER_MEMORY_MB}m", "--pids-limit", str(config.GRADER_PIDS_LIMIT),
             *(["--cpus", config.GRADER_CPUS] if config.GRADER_CPUS else []),
             config.GRADER_IMAGE, "python", "-c", "pass"],
            capture_output=True, text=True, check=False,
        )
        warnings = [line for line in limits.stderr.splitlines() if line.strip()]
        enforced = limits.returncode == 0 and not warnings
        problems += not enforced
        print(f"[{_status(enforced)}] Docker enforces the container's memory/process limits")
        for line in warnings:
            print(f"        {line}")

        time.sleep(2)  # docker kill + --rm take a moment
        leftovers = subprocess.run(
            [config.GRADER_DOCKER, "ps", "-a", "-q", "--filter", "label=aipl.grader"],
            capture_output=True, text=True, check=False,
        ).stdout.split()
        problems += bool(leftovers)
        print(f"[{_status(not leftovers)}] no grader containers left behind ({len(leftovers)} found)")

    print()
    if config.GRADER_SANDBOX != "docker":
        print("Mode is not 'docker', so the YES lines above are expected: student code runs with the backend's own")
        print("access. Set AIPL_GRADER_SANDBOX=docker in backend/.env before real participants use the server.")
        return 1
    print("All good: the sandbox is ready for participants." if not problems else f"{problems} problem(s) - see FAIL above.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
