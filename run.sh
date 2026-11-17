#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "[1/3] Creating Python virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate
echo "[2/3] Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "[3/3] Starting Pre-Sales AI Command Center on http://127.0.0.1:8080 ..."
exec uvicorn backend.main:app --host "${APP_HOST:-127.0.0.1}" --port "${APP_PORT:-8080}"
