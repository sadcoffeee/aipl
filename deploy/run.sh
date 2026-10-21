set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS="$REPO/backend/data"
GPU_UTIL="${AIPL_GPU_UTIL:-0.3}"
MAX_LEN="${AIPL_MAX_MODEL_LEN:-8192}"

mkdir -p "$LOGS"

running() { tmux has-session -t "$1" 2>/dev/null; }

start_model() {
  local path="${1:-}" name="${2:-}"
  if [[ -z "$path" || -z "$name" ]]; then
    echo "usage: bash deploy/run.sh model /models/<folder> <short-name>"
    echo "models available:"; ls /models 2>/dev/null | sed 's/^/  /'
    exit 1
  fi
  [[ -d "$path" ]] || { echo "No such folder: $path"; exit 1; }
  running model && { echo "'model' is already running - bash deploy/run.sh stop model first."; exit 1; }

  tmux new-session -d -s model \
    "vllm serve '$path' --served-model-name '$name' \
       --max-model-len $MAX_LEN --gpu-memory-utilization $GPU_UTIL \
       --host 127.0.0.1 --port 8000 2>&1 | tee '$LOGS/vllm.log'"

  echo "vLLM is starting in tmux session 'model'. Loading weights takes a few minutes."
  echo "  follow it:   bash deploy/run.sh logs model"
  echo "  ready when:  curl -s localhost:8000/v1/models   answers"
  echo "Then put   AIPL_LLM_MODEL=$name   in backend/.env, and restart the app."
}

start_app() {
  [[ -x "$REPO/backend/.venv/bin/uvicorn" ]] || {
    echo "No backend virtualenv yet"; exit 1; }
  [[ -f "$REPO/backend/.env" ]] || {
    echo "No backend/.env yet"; exit 1; }
  [[ -d "$REPO/frontend/dist" ]] || \
    echo "Warning: frontend/dist is missing, so the app will have no pages. Run: cd frontend && npm ci && npm run build"
  running app && { echo "'app' is already running - use: bash deploy/run.sh restart app"; exit 1; }

  tmux new-session -d -s app \
    "cd '$REPO/backend' && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001 2>&1 | tee -a '$LOGS/app.log'"

  sleep 3
  if curl -sf localhost:8001/api/health >/dev/null; then
    echo "Backend is up on port 8001."
  else
    echo "Backend did not answer yet - check: bash deploy/run.sh logs app"
  fi
}

stop() {
  local which="${1:-}"
  case "$which" in
    model|app) running "$which" && tmux kill-session -t "$which" && echo "stopped $which" || echo "$which was not running" ;;
    all)       stop model; stop app ;;
    *)         echo "usage: bash deploy/run.sh stop model|app|all"; exit 1 ;;
  esac
}

status() {
  for session in model app; do
    if running "$session"; then echo "$session: running"; else echo "$session: stopped"; fi
  done
  echo
  if curl -sf localhost:8000/v1/models >/dev/null; then
    served=$(curl -s localhost:8000/v1/models | python3 -c 'import json, sys; print(", ".join(m["id"] for m in json.load(sys.stdin)["data"]))')
    echo "model answers on :8000 - serving: $served"
  else
    echo "model does not answer on :8000 (still loading, or not started)"
  fi
  if curl -sf localhost:8001/api/health >/dev/null; then
    echo "app answers on :8001 - $(curl -s localhost:8001/api/health)"
  else
    echo "app does not answer on :8001"
  fi
}

logs() {
  case "${1:-}" in
    model) tail -n 50 -f "$LOGS/vllm.log" ;;
    app)   tail -n 50 -f "$LOGS/app.log" ;;
    *)     echo "usage: bash deploy/run.sh logs model|app"; exit 1 ;;
  esac
}

case "${1:-}" in
  model)   shift; start_model "$@" ;;
  app)     start_app ;;
  stop)    stop "${2:-}" ;;
  restart) stop "${2:-}"; sleep 1
           case "${2:-}" in app) start_app ;; model) echo "Start it again with: bash deploy/run.sh model <path> <name>" ;; esac ;;
  status)  status ;;
  logs)    logs "${2:-}" ;;
  *)       sed -n '2,10p' "$0"; exit 1 ;;
esac