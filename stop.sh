#!/bin/bash
PIDS=$(lsof -ti tcp:8080)
if [ -z "$PIDS" ]; then
  echo "Finanztracker läuft nicht."
else
  echo "$PIDS" | xargs kill
  echo "Finanztracker gestoppt."
fi
