#!/usr/bin/env bash
# Démarre le développement sans Docker : API (8000) + interface (5173). Depuis n'importe quel dossier.
set -euo pipefail
RACINE="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$RACINE/2-backend"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt pytest ruff
PYTHONPATH=.:../3-connecteurs-deploiement/connecteurs .venv/bin/uvicorn app.main:app --reload --port 8000 &
API=$!
trap 'kill $API 2>/dev/null' EXIT
cd "$RACINE/1-frontend"
npm install --no-audit --no-fund
npm run dev
