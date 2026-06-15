#!/usr/bin/env bash
# CDL Ticket Engine — local dev helpers
# Usage: ./dev.sh [command]
#   ./dev.sh serve     — start API server (hot-reload, mock mode)
#   ./dev.sh test      — run full test suite
#   ./dev.sh scan FILE — POST a ticket file and pretty-print the result
#   ./dev.sh live FILE — POST with real Claude (requires ANTHROPIC_API_KEY in .env)
#   ./dev.sh shell     — open a Python REPL with the venv active

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv/bin"
ENV_FILE="$ROOT/.env"

# Load .env so subprocesses inherit API keys
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

CMD="${1:-help}"

case "$CMD" in
  serve)
    echo "→ Starting API server on http://localhost:8000 (USE_MOCK=${USE_MOCK})"
    echo "  Docs: http://localhost:8000/docs"
    USE_MOCK="${USE_MOCK:-true}" \
      "$VENV/uvicorn" app.main:app --reload --host 0.0.0.0 --port 8000
    ;;

  test)
    echo "→ Running test suite"
    "$VENV/pytest" tests/ -v "${@:2}"
    ;;

  scan)
    FILE="${2:-}"
    if [[ -z "$FILE" ]]; then echo "Usage: ./dev.sh scan <file.pdf|jpg|png>"; exit 1; fi
    MIME=$(file --mime-type -b "$FILE")
    echo "→ Scanning $FILE ($MIME) in MOCK mode"
    curl -s -X POST http://localhost:8000/api/v1/process \
      -H "x-api-key: ${API_KEY}" \
      -F "file=@${FILE};type=${MIME}" \
      -F "driver_name=Test Driver" \
      | "$VENV/python" -m json.tool
    ;;

  live)
    FILE="${2:-}"
    if [[ -z "$FILE" ]]; then echo "Usage: ./dev.sh live <file.pdf|jpg|png>"; exit 1; fi
    if [[ "${ANTHROPIC_API_KEY:-sk-ant-...}" == "sk-ant-..." ]]; then
      echo "✗ Set ANTHROPIC_API_KEY in .env first"; exit 1
    fi
    MIME=$(file --mime-type -b "$FILE")
    echo "→ Scanning $FILE with live Claude (USE_MOCK=false)"
    USE_MOCK=false curl -s -X POST http://localhost:8000/api/v1/process \
      -H "x-api-key: ${API_KEY}" \
      -F "file=@${FILE};type=${MIME}" \
      -F "driver_name=Test Driver" \
      | "$VENV/python" -m json.tool
    ;;

  shell)
    echo "→ Python REPL (venv active). Ctrl-D to exit."
    "$VENV/python"
    ;;

  help|*)
    cat <<'EOF'
CDL Ticket Engine — dev helper

  ./dev.sh serve          Start API with hot-reload (mock mode by default)
  ./dev.sh test           Run pytest suite
  ./dev.sh scan FILE      POST a ticket to the running server (mock)
  ./dev.sh live FILE      POST with real Claude (needs ANTHROPIC_API_KEY in .env)
  ./dev.sh shell          Open Python REPL with venv loaded

Config: edit .env to toggle USE_MOCK or add your ANTHROPIC_API_KEY
EOF
    ;;
esac
