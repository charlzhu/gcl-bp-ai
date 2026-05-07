#!/usr/bin/env bash
set -euo pipefail

echo "[Safety] Start safety check"

if [ ! -d ".git" ]; then
  echo "[Safety][WARN] 当前目录未检测到 .git。若这是解压包环境可以继续；正式执行建议在 Git 仓库中运行。"
else
  CURRENT_BRANCH="$(git branch --show-current || true)"
  echo "[Safety] Current branch: ${CURRENT_BRANCH}"

  if [ -z "$CURRENT_BRANCH" ]; then
    echo "[Safety][ERROR] 无法识别当前分支"
    exit 1
  fi

  if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
    echo "[Safety][ERROR] 禁止在 main/master 分支直接运行 AI 自动构建"
    exit 1
  fi

  if git ls-files | grep -E '(^|/)\.env$' >/dev/null 2>&1; then
    echo "[Safety][ERROR] .env 已被 Git 跟踪，必须先移除"
    exit 1
  fi
fi

if find . -path './.git' -prune -o -name '.env' -print | grep -q .; then
  echo "[Safety][WARN] 检测到 .env 文件。确认未进入 Git 且不要交给 Codex 修改。"
fi

echo "[Safety] Passed"
