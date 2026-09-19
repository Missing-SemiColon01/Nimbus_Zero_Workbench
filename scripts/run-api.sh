#!/usr/bin/env bash
set -euo pipefail

# Docker Compose supplies OLLAMA_BASE_URL itself.  When starting the API
# directly, load the repository's local-only settings so Ollama is addressed
# through localhost rather than the Compose-only "ollama" hostname.
if [[ -f .env.local ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.local
  set +a
fi

exec uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000