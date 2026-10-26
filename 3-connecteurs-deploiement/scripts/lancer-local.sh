#!/usr/bin/env bash
# Essai complet sans Docker : construit l'interface puis sert tout sur http://localhost:8000
set -euo pipefail
RACINE="$(cd "$(dirname "$0")/../.." && pwd)"
(cd "$RACINE/1-frontend" && npm ci --no-audit --no-fund && npm run build)
cd "$RACINE/2-backend"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt
INTERFACE_DIR="$RACINE/1-frontend/dist" PYTHONPATH=.:../3-connecteurs-deploiement/connecteurs \
  .venv/bin/uvicorn app.main:app --port 8000
