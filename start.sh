#!/bin/bash
set -a
source "$(dirname "$0")/.env"
set +a

source "$(dirname "$0")/.venv/bin/activate"

echo "Finanztracker läuft auf http://localhost:8080"
uvicorn backend.main:app --reload --port 8080
