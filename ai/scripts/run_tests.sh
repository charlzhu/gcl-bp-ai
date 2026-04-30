#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

REPORT_DIR="${1:-ai/reports/manual}"
TEST_MODE="${2:-${TEST_MODE:-smoke}}"

mkdir -p "$REPORT_DIR"

LOG_FILE="$REPORT_DIR/test.log"
: > "$LOG_FILE"

echo "== Test Runner ==" | tee -a "$LOG_FILE"
echo "Root: $ROOT_DIR" | tee -a "$LOG_FILE"
echo "Mode: $TEST_MODE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

EXIT_CODE=0

run_step() {
  local title="$1"
  local cmd="$2"
  local required="${3:-required}"

  echo "" | tee -a "$LOG_FILE"
  echo "== $title ==" | tee -a "$LOG_FILE"
  echo "$cmd" | tee -a "$LOG_FILE"

  bash -lc "$cmd" >> "$LOG_FILE" 2>&1
  local code=$?

  if [ "$code" -ne 0 ]; then
    echo "FAILED: $title, exit=$code" | tee -a "$LOG_FILE"

    if [ "$required" = "required" ]; then
      EXIT_CODE=$code
    else
      echo "NON-BLOCKING FAILURE: $title" | tee -a "$LOG_FILE"
    fi
  else
    echo "PASSED: $title" | tee -a "$LOG_FILE"
  fi
}

echo "== Environment Info ==" | tee -a "$LOG_FILE"
python --version >> "$LOG_FILE" 2>&1 || true
node --version >> "$LOG_FILE" 2>&1 || true
npm --version >> "$LOG_FILE" 2>&1 || true

if [ "$TEST_MODE" = "smoke" ]; then
  echo "" | tee -a "$LOG_FILE"
  echo "== Running smoke checks only ==" | tee -a "$LOG_FILE"

  # 1. Python 语法编译检查：不执行业务逻辑，只检查语法错误
  if [ -d "backend" ]; then
    run_step "Backend Python compile check" "python -m compileall -q backend"
  fi

  # 2. 可选：如果存在 scripts 或 core Python 目录，也做语法检查
  if [ -d "scripts" ]; then
    run_step "Scripts Python compile check" "python -m compileall -q scripts" "optional"
  fi

  # 3. 前端构建检查：如果 frontend/package.json 存在，则跑 build
  if [ -f "frontend/package.json" ]; then
    run_step "Frontend build" "npm run build --prefix frontend"
  elif [ -f "package.json" ]; then
    run_step "Root frontend build if present" "npm run build --if-present" "optional"
  fi

  # 4. 如果你后续沉淀了稳定 smoke pytest，可以放到 backend/tests/smoke
  if [ -d "backend/tests/smoke" ]; then
    run_step "Backend smoke pytest" "PYTHONPATH=. python -m pytest backend/tests/smoke -q"
  else
    echo "" | tee -a "$LOG_FILE"
    echo "No backend/tests/smoke directory found. Skipped backend smoke pytest." | tee -a "$LOG_FILE"
  fi

elif [ "$TEST_MODE" = "full" ]; then
  echo "" | tee -a "$LOG_FILE"
  echo "== Running full checks ==" | tee -a "$LOG_FILE"

  # 1. Python 语法检查
  if [ -d "backend" ]; then
    run_step "Backend Python compile check" "python -m compileall -q backend"
  fi

  # 2. 后端全量 pytest
  if [ -d "backend/tests" ]; then
    run_step "Backend full pytest" "PYTHONPATH=. python -m pytest backend/tests -q"
  else
    echo "No backend/tests directory found. Skipped backend full pytest." | tee -a "$LOG_FILE"
  fi

  # 3. 前端构建
  if [ -f "frontend/package.json" ]; then
    run_step "Frontend build" "npm run build --prefix frontend"
  elif [ -f "package.json" ]; then
    run_step "Root frontend build if present" "npm run build --if-present" "optional"
  fi

  # 4. 前端测试，如果 package.json 中定义了 test，则尝试执行
  if [ -f "frontend/package.json" ]; then
    run_step "Frontend test if present" "npm test --prefix frontend --if-present" "optional"
  elif [ -f "package.json" ]; then
    run_step "Root npm test if present" "npm test --if-present" "optional"
  fi

else
  echo "ERROR: Unknown TEST_MODE: $TEST_MODE" | tee -a "$LOG_FILE"
  echo "Allowed modes: smoke, full" | tee -a "$LOG_FILE"
  exit 9
fi

echo "" | tee -a "$LOG_FILE"
echo "== Test Runner Finished, exit=$EXIT_CODE ==" | tee -a "$LOG_FILE"

exit "$EXIT_CODE"
