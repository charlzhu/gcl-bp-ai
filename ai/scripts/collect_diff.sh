#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

REPORT_DIR="${1:-ai/reports/manual}"
mkdir -p "$REPORT_DIR"

git status --short > "$REPORT_DIR/git-status.txt" || true
git diff --stat > "$REPORT_DIR/diffstat.txt" || true
git diff > "$REPORT_DIR/diff.patch" || true
git diff --name-only > "$REPORT_DIR/changed-files.txt" || true
git log --oneline -5 > "$REPORT_DIR/recent-commits.txt" 2>/dev/null || true

cat > "$REPORT_DIR/diff-summary.md" <<EOF2
# Diff Summary

## Git Status

\`\`\`text
$(cat "$REPORT_DIR/git-status.txt")
\`\`\`

## Diff Stat

\`\`\`text
$(cat "$REPORT_DIR/diffstat.txt")
\`\`\`

## Changed Files

\`\`\`text
$(cat "$REPORT_DIR/changed-files.txt")
\`\`\`
EOF2

echo "Diff collected into $REPORT_DIR"
