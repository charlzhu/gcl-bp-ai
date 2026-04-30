#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

REPORT_DIR="${1:-ai/reports/manual}"
mkdir -p "$REPORT_DIR"
LOG_FILE="$REPORT_DIR/safety-check.log"
: > "$LOG_FILE"

log() { echo "$*" | tee -a "$LOG_FILE"; }

log "== Safety Check =="
log "Root: $ROOT_DIR"

CURRENT_BRANCH="$(git branch --show-current 2>/dev/null || true)"
log "Current branch: ${CURRENT_BRANCH:-unknown}"

if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
  log "WARNING: 当前在 ${CURRENT_BRANCH} 分支。建议切换到 agent/* 分支后再自动修改。"
fi

log "== Git status =="
git status --short | tee -a "$LOG_FILE" || true

CHANGED_COUNT="$(git status --short | wc -l | tr -d ' ')"
log "Changed files count: ${CHANGED_COUNT}"

# 如果已有大量未提交改动，继续自动化很容易污染现场。
# ai/reports 产物不计入该判断。
NON_REPORT_CHANGED_COUNT="$(git status --short | grep -vE ' ai/reports/' | wc -l | tr -d ' ')"
log "Non-report changed files count: ${NON_REPORT_CHANGED_COUNT}"

if [ "$NON_REPORT_CHANGED_COUNT" -gt 80 ]; then
  log "ERROR: 当前已有超过 80 个非报告未提交改动文件，停止自动化，避免污染现场。"
  exit 2
fi

SENSITIVE_CHANGED="$(git status --short | grep -E '(\.env|\.pem|\.key|secret|token|password|credential|证书|密钥)' || true)"
if [ -n "$SENSITIVE_CHANGED" ]; then
  log "ERROR: 检测到敏感文件相关改动，停止自动化。"
  log "$SENSITIVE_CHANGED"
  exit 3
fi

log "Safety check passed."
