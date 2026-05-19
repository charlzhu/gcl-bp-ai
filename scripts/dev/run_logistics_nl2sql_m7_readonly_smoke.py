from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 固定脚本入口：允许本地手动触发 M7 只读 shadow smoke，避免临时 heredoc 命令。
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.domains.logistics.services.nl2sql.m7_readonly_smoke import (  # noqa: E402
    run_logistics_nl2sql_m7_readonly_smoke,
)


def main() -> int:
    """解析 CLI 参数并执行 M7 只读中间库 smoke。"""

    parser = argparse.ArgumentParser(description="Run logistics NL2SQL M7 readonly middle-db shadow smoke")
    parser.add_argument("--env-path", default="backend/.env", help="backend/.env path, default: backend/.env")
    parser.add_argument(
        "--artifact-dir",
        default="ai/outbox/kanban/t_1fceb427",
        help="directory for sanitized M7 JSONL/Markdown artifacts",
    )
    parser.add_argument("--trial-limit", type=int, default=5, help="bounded SELECT trial limit, default: 5")
    parser.add_argument("--max-limit", type=int, default=20, help="maximum allowed SELECT LIMIT, default: 20")
    args = parser.parse_args()

    result = run_logistics_nl2sql_m7_readonly_smoke(
        env_path=Path(args.env_path),
        artifact_dir=Path(args.artifact_dir),
        trial_limit=args.trial_limit,
        max_limit=args.max_limit,
    )
    # 只输出脱敏摘要：不打印 SQL、参数、host/user/password/DSN。
    payload = {
        "environment_status": result.environment_status,
        "environment_error_code": result.environment_error_code,
        "live_smoke_executed": result.live_smoke_executed,
        "records_path": str(result.records_path),
        "report_path": str(result.report_path),
        "total": result.report.total,
        "by_status": result.report.by_status,
        "by_stage": result.report.by_stage,
        "success_rate": result.report.success_rate,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if result.environment_status == "available" else 2


if __name__ == "__main__":
    raise SystemExit(main())
