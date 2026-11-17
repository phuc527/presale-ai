@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv" (
    echo [1/3] Creating Python virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
echo [2/3] Installing dependencies...
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo [3/3] Starting Pre-Sales AI Command Center on http://127.0.0.1:8080 ...
uvicorn backend.main:app --host 127.0.0.1 --port 8080
