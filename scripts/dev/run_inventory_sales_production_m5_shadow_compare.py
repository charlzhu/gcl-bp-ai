from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 固定脚本入口：允许本地手动触发 M5 产销存 shadow-only QueryPlan/SQLPlan 对比，避免临时 heredoc 命令。
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.domains.business_analysis.services.inventory_sales_production.m5_shadow_compare import (  # noqa: E402
    build_default_inventory_sales_production_m5_shadow_samples,
    render_safe_m5_shadow_compare_summary_json,
    run_inventory_sales_production_m5_shadow_compare,
)


def main() -> int:
    """解析 CLI 参数并执行 M5 产销存 shadow-only 离线对比。"""

    parser = argparse.ArgumentParser(description="Run inventory sales production M5 shadow-only QueryPlan/SQLPlan compare")
    parser.add_argument(
        "--artifact-dir",
        default=None,
        help="directory for sanitized M5 JSONL/Markdown artifacts; defaults to current kanban outbox when HERMES_KANBAN_TASK is set",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="optional cap for repeatable focused smoke runs; defaults to all shadow-only samples",
    )
    args = parser.parse_args()

    samples = build_default_inventory_sales_production_m5_shadow_samples(max_samples=args.max_samples)
    result = run_inventory_sales_production_m5_shadow_compare(
        samples=samples,
        artifact_dir=Path(args.artifact_dir) if args.artifact_dir else None,
    )
    # 只输出脱敏摘要：不打印 SQL、问题原文、参数值、host/user/password/DSN。
    print(render_safe_m5_shadow_compare_summary_json(result))
    return 0 if result.shadow_only and not result.formal_qa_executed and not result.live_db_executed else 2


if __name__ == "__main__":
    raise SystemExit(main())
