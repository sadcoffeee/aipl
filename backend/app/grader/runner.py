import json
import os
import pathlib
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
from typing import Any

from .. import config

HARNESS = pathlib.Path(__file__).with_name("harness.py")


def _environment(workdir: str) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": workdir,
        "TMPDIR": workdir, "TEMP": workdir, "TMP": workdir,
        "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
        "MPLBACKEND": "Agg",
        "PYTHONIOENCODING": "utf-8",
    }
    # Python on Windows cannot start without SYSTEMROOT
    for key in ("SYSTEMROOT", "SystemRoot"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def _command(workdir: str) -> list[str]:
    return [sys.executable, "-I", str(HARNESS)]


def run(
    student: str,
    reference: str | None,
    checks: list[dict[str, Any]],
    datasets: list[pathlib.Path],
) -> dict[str, Any]:
    """Run student (and reference) code. Never raises for student behaviour. Returns the harness result, or {"timeout": True}, or {"crashed": True, "stderr": ...} if the child died without reporting."""
    nonce = f"@@AIPL-RESULT-{secrets.token_hex(8)}@@"
    job = {
        "nonce": nonce,
        "student": student,
        "reference": reference,
        "checks": checks,
        "stdoutLimit": config.GRADER_STDOUT_LIMIT,
        "limits": {
            "cpuSeconds": config.GRADER_CPU_SECONDS,
            "memoryMB": config.GRADER_MEMORY_MB,
            "fileMB": 20,
        },
    }

    with tempfile.TemporaryDirectory(prefix="aipl-grade-") as workdir:
        for dataset in datasets:
            shutil.copy2(dataset, pathlib.Path(workdir) / dataset.name)

        kwargs: dict[str, Any] = {}
        if os.name == "posix":
            kwargs["start_new_session"] = True

        process = subprocess.Popen(
            _command(workdir),
            cwd=workdir,
            env=_environment(workdir),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **kwargs,
        )
        try:
            out, err = process.communicate(
                json.dumps(job), timeout=config.GRADER_TIMEOUT_SECONDS
            )
        except subprocess.TimeoutExpired:
            _kill(process)
            process.communicate()
            return {"timeout": True}

    # A CPU-limit kill arrives as SIGXCPU / SIGKILL rather than a timeout. Something is going wrong with sigkill not registerring.
    #if process.returncode in (-getattr(signal, "SIGXCPU", 24), -signal.SIGKILL):
    #    return {"timeout": True}

    for line in reversed(out.splitlines()):
        if line.startswith(nonce):
            return json.loads(line[len(nonce):])
    return {"crashed": True, "returncode": process.returncode, "stderr": err[-2000:]}


def _kill(process: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except (ProcessLookupError, PermissionError):
        pass