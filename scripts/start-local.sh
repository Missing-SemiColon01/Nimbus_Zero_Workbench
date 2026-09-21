#!/usr/bin/env bash
# Sovereign AI Workbench - One-Command Local Startup (Linux / macOS)
# Starts FastAPI backend (port 8000) and Vite frontend (port 8443) concurrently.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$ROOT_DIR"

echo "============================================="
echo " Sovereign AI Workbench - Local Full-Stack Startup"
echo "============================================="

# 1. Ensure required data directories exist
mkdir -p data/uploads data/artifacts data/tmp data/tmp/artifact-previews

# 2. Check for environment file
if [ ! -f ".env.local" ] && [ ! -f ".env" ]; then
    if [ -f ".env.local.example" ]; then
        cp .env.local.example .env.local
        echo "Created .env.local from .env.local.example"
    fi
fi

# 3. Locate Python binary
PYTHON_BIN="python3"
if [ -f ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
fi

# Trap signals for graceful shutdown
cleanup() {
    echo ""
    echo "Stopping Sovereign AI Workbench..."
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# 4. Start FastAPI Backend
echo "Starting Sovereign AI Backend on http://localhost:8000 ..."
$PYTHON_BIN -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# 5. Start Vite Frontend
if [ -d "frontend" ]; then
    echo "Starting Vite Frontend on http://localhost:8443 ..."
    (cd frontend && npm run dev) &
    FRONTEND_PID=$!
fi

# Wait for both processes
wait

