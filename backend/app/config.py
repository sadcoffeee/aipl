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

# --- model server ----------------------------------------------------------

#endpoint, placeholder for now. remember to include the /v1 part
LLM_BASE_URL = os.getenv("AIPL_LLM_BASE_URL", "http://127.0.0.1:8000/v1")

LLM_MODEL = os.getenv("AIPL_LLM_MODEL", "")

LLM_API_KEY = os.getenv("AIPL_LLM_API_KEY", "not-needed")

LLM_TIMEOUT_SECONDS = float(os.getenv("AIPL_LLM_TIMEOUT", "60"))