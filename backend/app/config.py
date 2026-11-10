import os
import pathlib

from dotenv import load_dotenv

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent

load_dotenv(BACKEND_DIR / ".env")

def _flag(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}

def _list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]

# Remember to swap host for 0.0.0.0 once we move to a machine that others want to connect to
HOST = os.getenv("AIPL_HOST", "127.0.0.1")
PORT = int(os.getenv("AIPL_PORT", "8001"))

# Only necessary when testing the front-end on its own with npm run dev. On the final version, the frontend is served by the backend.
ALLOWED_ORIGINS = _list("AIPL_ALLOWED_ORIGINS", ["http://localhost:5173", "http://127.0.0.1:5173"])

# Path to frontend. Served at "/" so we dont need a port
FRONTEND_DIST = pathlib.Path(os.getenv("AIPL_FRONTEND_DIST", str(REPO_DIR / "frontend" / "dist")))

DB_PATH = pathlib.Path(os.getenv("AIPL_DB_PATH", str(BACKEND_DIR / "data" / "study.db")))

# --- study behaviour -------------------------------------------------------


# Gating: should a student have to submit an attempt at a lesson before the next one unlocks? Admins are never gated, whatever this says.
GATING_ENABLED = _flag("AIPL_GATING", False)

# How long a login lasts before the person has to log in again.
SESSION_HOURS = int(os.getenv("AIPL_SESSION_HOURS", "12"))

# Prefix for generated participant codes, e.g. KVT-4F7QH2.
CODE_PREFIX = os.getenv("AIPL_CODE_PREFIX", "KVT")

# --- the grader ------------------------------------------------------------
GRADER_TIMEOUT_SECONDS = float(os.getenv("AIPL_GRADER_TIMEOUT", "10"))
GRADER_CPU_SECONDS = int(os.getenv("AIPL_GRADER_CPU_SECONDS", "5"))
GRADER_MEMORY_MB = int(os.getenv("AIPL_GRADER_MEMORY_MB", "2048"))
GRADER_STDOUT_LIMIT = int(os.getenv("AIPL_GRADER_STDOUT_LIMIT", "20000"))

# Where student code runs: "local" (a child process next to the backend - development only) or "docker" (a throwaway, locked-down container per submission)
GRADER_SANDBOX = os.getenv("AIPL_GRADER_SANDBOX", "local").strip().lower()

# docker mode only. The image is built with: bash deploy/run.sh grader build
GRADER_IMAGE = os.getenv("AIPL_GRADER_IMAGE", "aipl-grader:latest")
GRADER_DOCKER = os.getenv("AIPL_GRADER_DOCKER", "docker")
GRADER_MAX_PARALLEL = int(os.getenv("AIPL_GRADER_MAX_PARALLEL", "4"))
GRADER_PIDS_LIMIT = int(os.getenv("AIPL_GRADER_PIDS_LIMIT", "64"))
GRADER_SCRATCH_MB = int(os.getenv("AIPL_GRADER_SCRATCH_MB", "64"))
GRADER_CPUS = os.getenv("AIPL_GRADER_CPUS", "").strip()


# --- model server ----------------------------------------------------------

#endpoint, placeholder for now. remember to include the /v1 part
LLM_BASE_URL = os.getenv("AIPL_LLM_BASE_URL", "http://127.0.0.1:8000/v1")

LLM_MODEL = os.getenv("AIPL_LLM_MODEL", "ministral")

LLM_API_KEY = os.getenv("AIPL_LLM_API_KEY", "not-needed")

LLM_TIMEOUT_SECONDS = float(os.getenv("AIPL_LLM_TIMEOUT", "60"))

# --- feedback ----------------------------------------------------------------
FEEDBACK_MODE = os.getenv("AIPL_FEEDBACK_MODE", "llm").strip().lower()

FEEDBACK_PROMPT_PATH = pathlib.Path(
    os.getenv("AIPL_FEEDBACK_PROMPT", str(BACKEND_DIR / "prompts" / "feedback_system.md"))
)

FEEDBACK_TEMPERATURE = float(os.getenv("AIPL_FEEDBACK_TEMPERATURE", "0.2"))
FEEDBACK_MAX_TOKENS = int(os.getenv("AIPL_FEEDBACK_MAX_TOKENS", "700"))
FEEDBACK_TIMEOUT_SECONDS = float(os.getenv("AIPL_FEEDBACK_TIMEOUT", "30"))

# --- conditions and chat -----------------------------------------------------

# The two study conditions. They differ only in WHEN the student can talk to the model:
#   restricted   - only after submitting an attempt and rating their confidence
#   unrestricted - at any time while working on the task
CONDITIONS = ("restricted", "unrestricted")

# Students with no condition (and admins testing) behave as this one.
DEFAULT_CONDITION = os.getenv("AIPL_DEFAULT_CONDITION", "unrestricted").strip().lower()

# How many messages a student can send per attempt, the same in both conditions.
# The self-assessment is not one of them, and neither is a message the model could not answer.
CHAT_MAX_STUDENT_MESSAGES = int(os.getenv("AIPL_CHAT_MAX_MESSAGES", "5"))

# Longest message a student can send, in characters.
CHAT_MAX_MESSAGE_CHARS = int(os.getenv("AIPL_CHAT_MAX_CHARS", "1000"))

# Added after the feedback prompt for every reply in the conversation.
CHAT_PROMPT_PATH = pathlib.Path(
    os.getenv("AIPL_CHAT_PROMPT", str(BACKEND_DIR / "prompts" / "chat_followup.md"))
)

# Added as well while an unrestricted student chats before submitting (no verdict yet).
CHAT_PRESUBMISSION_PROMPT_PATH = pathlib.Path(
    os.getenv("AIPL_CHAT_PRESUBMISSION_PROMPT", str(BACKEND_DIR / "prompts" / "chat_presubmission.md"))
)

CHAT_TEMPERATURE = float(os.getenv("AIPL_CHAT_TEMPERATURE", "0.3"))
CHAT_MAX_TOKENS = int(os.getenv("AIPL_CHAT_MAX_TOKENS", "400"))
