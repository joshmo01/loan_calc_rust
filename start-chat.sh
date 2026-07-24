#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Load .env if present (KEY=value lines, no export required)
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ -z "${CEREBRAS_API_KEY:-}${LLM_API_KEY:-}" ]]; then
  echo "ERROR: Set CEREBRAS_API_KEY first."
  echo "  export CEREBRAS_API_KEY='csk-...'"
  echo "  or copy .env.example → .env and edit it"
  echo ""
  echo "Offline mode (no key): open standalone/loan-calculator-standalone.html"
  exit 1
fi

export LLM_BASE_URL="${LLM_BASE_URL:-https://api.cerebras.ai/v1}"
export LLM_MODEL="${LLM_MODEL:-gemma-4-31b}"
export PORT="${PORT:-8790}"

echo "Starting Loan Chat"
echo "  UI:    http://localhost:${PORT}/"
echo "  model: ${LLM_MODEL}"
echo "  Ctrl+C to stop"
echo ""
exec python3 chat/server.py
