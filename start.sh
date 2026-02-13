#!/usr/bin/env bash
set -euo pipefail

BACKEND_PORT=8020
BACKEND_DIR="$(cd "$(dirname "$0")/backend" && pwd)"

echo "🚀 Starting Knowledge Base API on port ${BACKEND_PORT}..."
echo "   Swagger UI: http://localhost:${BACKEND_PORT}/docs"
echo ""

cd "${BACKEND_DIR}"
source .venv/bin/activate
exec uvicorn app.main:app --reload --port "${BACKEND_PORT}"
