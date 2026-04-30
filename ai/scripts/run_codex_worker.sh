#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

if [ "$#" -lt 3 ]; then
  echo "用法: $0 <role_file> <task_file> <report_file>"
  exit 1
fi

ROLE_FILE="$1"
TASK_FILE="$2"
REPORT_FILE="$3"

mkdir -p "$(dirname "$REPORT_FILE")"

if [ ! -f "$ROLE_FILE" ]; then
  echo "Role file not found: $ROLE_FILE"
  exit 2
fi

if [ ! -f "$TASK_FILE" ]; then
  echo "Task file not found: $TASK_FILE"
  exit 3
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "codex command not found. 请确认 Codex CLI 已安装并可在终端执行。" | tee "$REPORT_FILE"
  exit 4
fi

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/codex-worker-prompt.XXXXXX")"
TMP_PROMPT="$TMP_DIR/prompt.md"
trap 'rm -rf "$TMP_DIR"' EXIT

{
  echo "# 角色说明"
  cat "$ROLE_FILE"
  echo ""
  echo "# AI 公司规则"
  find ai/company -maxdepth 1 -type f -name '*.md' | sort | while read -r f; do echo "\n## $f"; cat "$f"; done
  echo ""
  echo "# AI 项目上下文"
  find ai/context -maxdepth 1 -type f -name '*.md' | sort | while read -r f; do echo "\n## $f"; cat "$f"; done
  echo ""
  echo "# AI 记忆"
  find ai/memory -maxdepth 1 -type f -name '*.md' | sort | while read -r f; do echo "\n## $f"; cat "$f"; done
  echo ""
  echo "# 项目事实源"
  for f in AGENTS.md README_WORKSPACE.md docs/CURRENT_STATUS.md docs/HANDOFF.md docs/NEXT_TASK.md docs/BUSINESS_RULES.md docs/KNOWN_ISSUES.md; do
    if [ -f "$f" ]; then
      echo "\n## $f"
      cat "$f"
    fi
  done
  echo ""
  echo "# 当前任务"
  cat "$TASK_FILE"
} > "$TMP_PROMPT"

{
  echo "# Codex Worker Report"
  echo ""
  echo "- Role: $ROLE_FILE"
  echo "- Task: $TASK_FILE"
  echo "- Prompt copy: $TMP_PROMPT"
  echo ""
} > "$REPORT_FILE"

CODEX_CMD="${CODEX_CMD:-codex exec}"
CODEX_EXTRA_ARGS="${CODEX_EXTRA_ARGS:-}"

echo "Running: $CODEX_CMD $CODEX_EXTRA_ARGS < $TMP_PROMPT" | tee -a "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

set +e
bash -lc "$CODEX_CMD $CODEX_EXTRA_ARGS < '$TMP_PROMPT'" >> "$REPORT_FILE" 2>&1
EXIT_CODE=$?
set -e

echo "" >> "$REPORT_FILE"
echo "Codex worker exit code: $EXIT_CODE" >> "$REPORT_FILE"

# 默认保留 prompt 副本，方便复盘。可手动清理 /tmp/codex-worker-prompt.*.md。
exit "$EXIT_CODE"
