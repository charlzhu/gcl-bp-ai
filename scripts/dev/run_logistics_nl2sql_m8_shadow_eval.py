from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 固定脚本入口：允许本地手动触发 M8 shadow-only 样例评估，避免临时 heredoc 命令。
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.domains.logistics.services.nl2sql.m8_shadow_eval import (  # noqa: E402
    DEFAULT_M8_ARTIFACT_DIR,
    render_safe_m8_summary_json,
    run_logistics_nl2sql_m8_shadow_eval,
)


def main() -> int:
    """解析 CLI 参数并执行 M8 shadow-only 评估。"""

    parser = argparse.ArgumentParser(description="Run logistics NL2SQL M8 shadow-only sample evaluation")
    parser.add_argument(
        "--artifact-dir",
        default=str(DEFAULT_M8_ARTIFACT_DIR),
        help="directory for sanitized M8 JSONL/Markdown artifacts",
    )
    args = parser.parse_args()

    result = run_logistics_nl2sql_m8_shadow_eval(artifact_dir=Path(args.artifact_dir))
    # 只输出脱敏摘要：不打印 SQL、参数、host/user/password/DSN。
    print(render_safe_m8_summary_json(result))
    return 0 if result.shadow_only and not result.live_smoke_executed else 2


if __name__ == "__main__":
    raise SystemExit(main())
