#!/bin/zsh
set -euo pipefail

PROJECT_DIR="${PRISMA_DESK_DIR:-$HOME/prismadesk}"
PORT="${PORT:-5050}"

cd "$PROJECT_DIR"
mkdir -p logs data

if [ ! -d ".venv" ]; then
  /usr/bin/python3 -m venv .venv
fi

".venv/bin/python" -m pip install -r requirements.txt >/dev/null

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
fi

export PORT
exec ".venv/bin/python" app.py
