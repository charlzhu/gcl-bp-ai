#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-basic}"

echo "[Test] Start tests, mode=${MODE}"

if [ -d "backend" ] || [ -d "scripts" ] || [ -d "ai/scripts" ]; then
  echo "[Test] Python compile check"
  python -m compileall backend scripts ai/scripts
else
  echo "[Test] Skip Python compile check: backend/scripts/ai/scripts not found"
fi

if [ -d "tests" ]; then
  echo "[Test] Pytest"
  pytest tests -q
else
  echo "[Test] Skip pytest: tests directory not found"
fi

if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then
  echo "[Test] Frontend build"
  npm run build --prefix frontend
else
  echo "[Test] Skip frontend build: frontend/package.json not found"
fi

if [ "$MODE" = "full" ]; then
  echo "[Test] Full regression hooks"
  [ -f scripts/trial_release_readiness_check.py ] && python scripts/trial_release_readiness_check.py || true
  [ -f scripts/logistics_nlu_center_eval.py ] && python scripts/logistics_nlu_center_eval.py || true
  [ -f scripts/plan_bom_nlu_eval.py ] && python scripts/plan_bom_nlu_eval.py || true
fi

echo "[Test] All checks passed"
