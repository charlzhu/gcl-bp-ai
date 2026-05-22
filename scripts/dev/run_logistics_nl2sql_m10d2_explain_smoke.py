from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 固定脚本入口：允许本地手动触发 M10-D2 EXPLAIN smoke，避免临时 heredoc 命令。
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.domains.logistics.services.nl2sql.m10d2_explain_smoke import (  # noqa: E402
    run_logistics_nl2sql_m10d2_explain_smoke,
)


def main() -> int:
    """解析 CLI 参数并执行 M10-D2 EXPLAIN smoke。"""

    parser = argparse.ArgumentParser(description="Run logistics NL2SQL M10-D2 EXPLAIN middle-db shadow smoke")
    parser.add_argument("--env-path", default="backend/.env", help="backend/.env path, default: backend/.env")
    parser.add_argument(
        "--artifact-dir",
        default="ai/outbox/kanban/t_df3a6b13/m10d2-explain-smoke",
        help="directory for sanitized M10-D2 JSONL/Markdown artifacts",
    )
    args = parser.parse_args()

    result = run_logistics_nl2sql_m10d2_explain_smoke(
        env_path=Path(args.env_path),
        artifact_dir=Path(args.artifact_dir),
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
