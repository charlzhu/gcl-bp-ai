#!/usr/bin/env bash
set -u

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

REPORT_DIR="${1:-ai/reports/manual}"
mkdir -p "$REPORT_DIR"

LOG_FILE="$REPORT_DIR/safety-check.log"
: > "$LOG_FILE"

echo "== Safety Check ==" | tee -a "$LOG_FILE"
echo "Root: $ROOT_DIR" | tee -a "$LOG_FILE"

CURRENT_BRANCH="$(git branch --show-current 2>/dev/null || true)"
echo "Current branch: ${CURRENT_BRANCH}" | tee -a "$LOG_FILE"

if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
  echo "WARNING: 当前在 ${CURRENT_BRANCH} 分支。建议切换到 agent/* 分支后再自动修改。" | tee -a "$LOG_FILE"
fi

echo "== Git status ==" | tee -a "$LOG_FILE"
git status --short --untracked-files=all | tee -a "$LOG_FILE"

NON_REPORT_STATUS="$(git status --short --untracked-files=all | grep -vE '^[ MADRCU?!]{2} ai/(reports|tasks/(running|done))/' || true)"
CHANGED_COUNT="$(printf "%s\n" "$NON_REPORT_STATUS" | sed '/^$/d' | wc -l | tr -d ' ')"
echo "Changed files count: ${CHANGED_COUNT}" | tee -a "$LOG_FILE"

if [ "${CHANGED_COUNT:-0}" -gt 30 ]; then
  echo "ERROR: 当前已有超过 30 个非报告未提交改动文件，停止自动化，避免污染现场。" | tee -a "$LOG_FILE"
  exit 2
fi

SENSITIVE_CHANGED="$(printf "%s\n" "$NON_REPORT_STATUS" | grep -E '(^|[[:space:]/])(\.env|\.env\.local|auth\.json)($|[[:space:]])|(\.pem|\.key|secret|token|password|credential|证书|密钥)' || true)"

if [ -n "$SENSITIVE_CHANGED" ]; then
  echo "ERROR: 检测到敏感文件相关改动，停止自动化。" | tee -a "$LOG_FILE"
  echo "$SENSITIVE_CHANGED" | tee -a "$LOG_FILE"
  exit 3
fi

IGNORED_SOURCE_RISK="$(
  git status --ignored --short --untracked-files=all \
    | grep '^!! ' \
    | sed 's/^!! //' \
    | grep -E '^(backend|frontend/src|scripts|ai/scripts|ai/roles|ai/company|docs)/.*\.(py|sh|ts|tsx|vue|md|json|ya?ml)$' \
    | grep -vE '(__pycache__|\.pytest_cache|\.venv|venv|node_modules|dist|coverage|ai/reports|tmp)/' \
    || true
)"

if [ -n "$IGNORED_SOURCE_RISK" ]; then
  echo "WARNING: 检测到疑似被 .gitignore 忽略的源码文件，需在报告中人工确认。" | tee -a "$LOG_FILE"
  echo "$IGNORED_SOURCE_RISK" | tee -a "$LOG_FILE"
fi

echo "Safety check passed." | tee -a "$LOG_FILE"
exit 0
