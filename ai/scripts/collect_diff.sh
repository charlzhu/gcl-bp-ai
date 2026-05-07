#!/usr/bin/env bash
set -euo pipefail

TASK_DIR="${1:?Usage: collect_diff.sh <task_dir>}"
mkdir -p "$TASK_DIR"

if [ ! -d ".git" ]; then
  echo "[Diff][WARN] 当前不是 Git 仓库，无法收集 git diff" | tee "$TASK_DIR/git_status.txt"
  : > "$TASK_DIR/diff_stat.txt"
  : > "$TASK_DIR/diff.patch"
  exit 0
fi

echo "[Diff] Collect git status"
git status --short > "$TASK_DIR/git_status.txt"

echo "[Diff] Collect git diff stat"
git diff --stat > "$TASK_DIR/diff_stat.txt"

echo "[Diff] Collect git diff patch"
git diff > "$TASK_DIR/diff.patch"

echo "[Diff] Done"
