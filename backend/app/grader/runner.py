import base64
import json
import os
import pathlib
import secrets
import signal
import subprocess
import sys
import tempfile
import threading
from typing import Any

from .. import config

HARNESS = pathlib.Path(__file__).with_name("harness.py")

# Where student code runs inside the container. A tmpfs, i.e. it lives in memory and vanishes with the container.
CONTAINER_WORKDIR = "/work"
# The unprivileged user created in backend/sandbox/Dockerfile.
CONTAINER_USER = "10001:10001"
# Starting a container costs about a second on top of the student's own run time, so docker mode gets this much extra before the backend gives up on it.
DOCKER_STARTUP_SLACK_SECONDS = 5

# At most this many submissions are graded at the same time. Others wait their turn (briefly - a run takes about a second). Stops a burst of submits from starting many containers at once.
_slots = threading.BoundedSemaphore(config.GRADER_MAX_PARALLEL)


def _child_environment(workdir: str) -> dict[str, str]:
    """Environment variables the student's Python process sees. Deliberately not the backend's own environment."""
    return {
        "HOME": workdir,
        "TMPDIR": workdir, "TEMP": workdir, "TMP": workdir,
        "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
        "MPLBACKEND": "Agg",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _local_environment(workdir: str) -> dict[str, str]:
    env = _child_environment(workdir)
    env["PATH"] = os.environ.get("PATH", "")
    # Python on Windows cannot start without SYSTEMROOT
    for key in ("SYSTEMROOT", "SystemRoot"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def _docker_command(container_name: str, run_seconds: float) -> list[str]:
    """The `docker run` command for one submission. Every flag here is a wall between student code and everything else."""
    memory = f"{config.GRADER_MEMORY_MB}m"
    command = [
        config.GRADER_DOCKER, "run",
        "--rm",                     # delete the container as soon as it stops
        "-i",                       # keep stdin open
        "--name", container_name,   # so we can find and kill it on a timeout
        "--label", "aipl.grader=1", # so leftovers can be found: docker ps --filter label=aipl.grader
        "--pull", "never",          # never try to download the image; a missing image should fail loudly
        "--network", "none",        # no network at all, not even to the backend or the model server
        "--read-only",              # the whole filesystem is read-only
        "--tmpfs", f"{CONTAINER_WORKDIR}:rw,nosuid,nodev,noexec,size={config.GRADER_SCRATCH_MB}m,mode=1777",  # except a small scratch folder in memory
        "--workdir", CONTAINER_WORKDIR,
        "--user", CONTAINER_USER,   # not root, even inside the container
        "--cap-drop", "ALL",        # no special kernel privileges
        "--security-opt", "no-new-privileges",
        "--pids-limit", str(config.GRADER_PIDS_LIMIT),  # no fork bombs
        "--memory", memory, "--memory-swap", memory,     # hard memory cap, no swapping
        "--log-driver", "none",     # output comes back over the pipe; nothing to keep in Docker's logs
    ]
    if config.GRADER_CPUS:
        command += ["--cpus", config.GRADER_CPUS]
    for key, value in _child_environment(CONTAINER_WORKDIR).items():
        command += ["-e", f"{key}={value}"]
    command += [
        config.GRADER_IMAGE,
        # even if the backend dies mid-run and never cleans up, the container kills itself.
        "timeout", "--signal=KILL", str(int(run_seconds) + 1),
        # The harness is sent as the program text instead of being baked into the image, so the image never needs rebuilding when harness.py changes. -I: ignore PYTHON* variables and don't import from the current folder.
        "python", "-I", "-c", HARNESS.read_text(encoding="utf-8"),
    ]
    return command


def run(
    student: str,
    reference: str | None,
    checks: list[dict[str, Any]],
    datasets: list[pathlib.Path],
    guard: bool = True,
) -> dict[str, Any]:
    """Run student (and reference) code. Never raises for student behaviour. Returns the harness result, or {"timeout": True}, or {"crashed": True, "stderr": ...} if the child died without reporting.

    guard=False skips the audit hook in harness.py. Only app.grader_check uses it, to test the sandbox on its own.
    """
    nonce = f"@@AIPL-RESULT-{secrets.token_hex(8)}@@"
    job = {
        "nonce": nonce,
        "student": student,
        "reference": reference,
        "checks": checks,
        "guard": guard,
        "stdoutLimit": config.GRADER_STDOUT_LIMIT,
        "limits": {
            "cpuSeconds": config.GRADER_CPU_SECONDS,
            "memoryMB": config.GRADER_MEMORY_MB,
            "fileMB": 20,
        },
        # The datasets travel inside the job and the harness writes them into its working folder. In docker mode there is no shared folder to copy them through (and we don't want one).
        "files": {
            dataset.name: base64.b64encode(dataset.read_bytes()).decode("ascii") for dataset in datasets
        },
    }

    with _slots:
        if config.GRADER_SANDBOX == "docker":
            return _run_docker(job, nonce)
        if config.GRADER_SANDBOX == "local":
            return _run_local(job, nonce)
        return {
            "crashed": True,
            "returncode": None,
            "stderr": f"AIPL_GRADER_SANDBOX is '{config.GRADER_SANDBOX}'; it must be 'local' or 'docker'.",
        }


def _run_local(job: dict[str, Any], nonce: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="aipl-grade-") as workdir:
        kwargs: dict[str, Any] = {}
        if os.name == "posix":
            kwargs["start_new_session"] = True

        process = subprocess.Popen(
            [sys.executable, "-I", str(HARNESS)],
            cwd=workdir,
            env=_local_environment(workdir),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **kwargs,
        )
        try:
            out, err = process.communicate(json.dumps(job), timeout=config.GRADER_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            _kill_local(process)
            process.communicate()
            return {"timeout": True}

    # A CPU-limit kill arrives as SIGXCPU / SIGKILL rather than a timeout. Something is going wrong with sigkill not registerring.
    #if process.returncode in (-getattr(signal, "SIGXCPU", 24), -signal.SIGKILL):
    #    return {"timeout": True}

    return _read_result(out, err, nonce, process.returncode)


def _run_docker(job: dict[str, Any], nonce: str) -> dict[str, Any]:
    container_name = f"aipl-grade-{secrets.token_hex(6)}"
    timeout = config.GRADER_TIMEOUT_SECONDS + DOCKER_STARTUP_SLACK_SECONDS
    try:
        process = subprocess.Popen(
            _docker_command(container_name, timeout),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return {
            "crashed": True,
            "returncode": None,
            "stderr": f"AIPL_GRADER_SANDBOX=docker, but the '{config.GRADER_DOCKER}' command was not found. "
                      "Is the Docker CLI installed in the backend's container (see .devcontainer/Dockerfile)?",
        }

    try:
        out, err = process.communicate(json.dumps(job), timeout=timeout)
    except subprocess.TimeoutExpired:
        # Killing the `docker` command does not stop the container, so ask Docker to kill the container itself.
        subprocess.run(
            [config.GRADER_DOCKER, "kill", container_name],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=False,
        )
        process.kill()
        process.communicate()
        return {"timeout": True}

    # Exit code 125 means Docker itself refused (no daemon, missing image, bad flag) - the student's code never ran.
    if process.returncode == 125 and nonce not in out:
        return {"crashed": True, "returncode": 125, "stderr": "Docker could not start the grader container: " + err[-2000:]}
    return _read_result(out, err, nonce, process.returncode)


def _read_result(out: str, err: str, nonce: str, returncode: int | None) -> dict[str, Any]:
    for line in reversed(out.splitlines()):
        if line.startswith(nonce):
            return json.loads(line[len(nonce):])
    return {"crashed": True, "returncode": returncode, "stderr": err[-2000:]}


def _kill_local(process: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except (ProcessLookupError, PermissionError):
        pass
