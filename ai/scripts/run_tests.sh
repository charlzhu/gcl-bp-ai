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

if [ "$TEST_MODE" = "auto" ]; then
  echo "== Auto Test Profile ==" | tee -a "$LOG_FILE"
  # 自动模式只选择 smoke/full 档位，不直接执行额外测试，避免测试策略和执行混在一起。
  PROFILE_OUTPUT="$(python ai/scripts/select_test_profile.py 2>>"$LOG_FILE" || true)"
  RESOLVED_MODE="$(printf "%s\n" "$PROFILE_OUTPUT" | sed -n '1p')"
  PROFILE_REASON="$(printf "%s\n" "$PROFILE_OUTPUT" | sed -n '2,$p')"

  if [ "$RESOLVED_MODE" != "smoke" ] && [ "$RESOLVED_MODE" != "full" ]; then
    echo "ERROR: auto 模式未能解析出合法测试档位。" | tee -a "$LOG_FILE"
    echo "$PROFILE_OUTPUT" | tee -a "$LOG_FILE"
    exit 9
  fi

  TEST_MODE="$RESOLVED_MODE"
  echo "Resolved Mode: $TEST_MODE" | tee -a "$LOG_FILE"
  echo "Reason: ${PROFILE_REASON:-无}" | tee -a "$LOG_FILE"
  echo "" | tee -a "$LOG_FILE"
fi

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

elif [ "$TEST_MODE" = "business-import" ]; then
  echo "" | tee -a "$LOG_FILE"
  echo "== Running business acceptance import checks ==" | tee -a "$LOG_FILE"

  # 业务问题集导入框架只检查独立脚本和 tests/business_acceptance，不触碰业务 service。
  run_step "Business acceptance Python compile check" "python -m compileall -q scripts/business_acceptance_importer.py scripts/business_acceptance_import_questions.py tests/business_acceptance"

  # 保留既有样例题验收脚本的轻量语法检查，证明 business_acceptance 不替换 3281 真实网页 E2E 口径。
  run_step "Existing trial_sample scripts compile check" "python -m compileall -q scripts/trial_sample_question_ledger.py scripts/trial_sample_expected_answer_builder.py scripts/trial_sample_frontend_e2e_eval.py scripts/trial_sample_e2e_batch_runner.py scripts/trial_sample_answer_comparator.py" "optional"

  # 使用标准库 unittest，避免为问题导入框架引入新的测试依赖。
  run_step "Business acceptance importer unit tests" "PYTHONPATH=. python -m unittest discover -s tests/business_acceptance -p 'test_*.py'"

  # 自测模式动态生成最小 docx，并产出 raw_questions / normalized_cases / 分类报告。
  run_step "Business acceptance import self test" "python scripts/business_acceptance_import_questions.py --self-test --output-dir '$REPORT_DIR/business_acceptance'"

elif [ "$TEST_MODE" = "business-oracle" ]; then
  echo "" | tee -a "$LOG_FILE"
  echo "== Running business acceptance oracle checks ==" | tee -a "$LOG_FILE"

  # P2.1 只检查 business_acceptance Oracle 工具层，不触碰后端 service、数据库或真实 Web E2E。
  run_step "Business acceptance oracle Python compile check" "python -m compileall -q scripts/business_acceptance_importer.py scripts/business_acceptance_import_questions.py scripts/business_acceptance_oracle_engine.py tests/business_acceptance"

  # 使用 unittest 覆盖物流年份到 Excel/MySQL 的数据源路由，以及 oracle_status 候选转换。
  run_step "Business acceptance oracle unit tests" "PYTHONPATH=. python -m unittest discover -s tests/business_acceptance/oracle -p 'test_*.py'"

  # 自测模式生成 oracle_cases.json 和 oracle_engine_report.md，验证 normalized_cases 后处理链路可运行。
  run_step "Business acceptance oracle self test" "python scripts/business_acceptance_oracle_engine.py --self-test --output-dir '$REPORT_DIR/business_oracle'"

elif [ "$TEST_MODE" = "business-oracle-excel" ]; then
  echo "" | tee -a "$LOG_FILE"
  echo "== Running business acceptance oracle excel checks ==" | tee -a "$LOG_FILE"

  # P2.2 只检查 business_acceptance Oracle Excel 工具层，不触碰后端 service、数据库或真实 Web E2E。
  run_step "Business acceptance oracle excel Python compile check" "python -m compileall -q scripts/business_acceptance_importer.py scripts/business_acceptance_import_questions.py scripts/business_acceptance_oracle_engine.py tests/business_acceptance"

  # 使用 unittest 覆盖 Excel loader、字段映射、月度运量、月度运费和未支持指标状态。
  run_step "Business acceptance oracle excel unit tests" "PYTHONPATH=. python -m unittest discover -s tests/business_acceptance/oracle -p 'test_*.py'"

  # 自测模式生成脱敏 Excel fixture，并产出带 expected_result 的 oracle_cases.json。
  run_step "Business acceptance oracle excel self test" "python scripts/business_acceptance_oracle_engine.py --self-test --with-excel-fixture --output-dir '$REPORT_DIR/business_oracle_excel'"

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
  echo "Allowed modes: smoke, full, auto, business-import, business-oracle, business-oracle-excel" | tee -a "$LOG_FILE"
  exit 9
fi

echo "" | tee -a "$LOG_FILE"
echo "== Test Runner Finished, exit=$EXIT_CODE ==" | tee -a "$LOG_FILE"

exit "$EXIT_CODE"
