#!/usr/bin/env python3
"""物流系统数据自动增量同步脚本。

用途：
    供 crontab、定时任务平台或人工命令行调用真实同步服务。

参数说明：
    --start-date: 正式数据起始日期，默认 2026-01-01。
    --updated-since: 手工指定增量起点；指定后优先级高于自动增量。
    --full: 不启用自动增量，按 start-date 做一次基线范围同步。
    --overlap-minutes: 自动增量时向前回看的分钟数。
    --dry-run: 只预演，不写入 ODS/DWD。

返回值：
    标准输出打印同步结果 JSON；同步异常时进程返回非 0。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.domains.logistics.schemas.sync import LogisticsSystemSyncRequest
from backend.app.domains.logistics.services.sync_service import LogisticsSystemSyncService


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="Run logistics system auto incremental sync")
    parser.add_argument("--start-date", default="2026-01-01", help="正式数据起始日期，格式 YYYY-MM-DD")
    parser.add_argument("--updated-since", default=None, help="手工指定增量起点，格式 YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--overlap-minutes", type=int, default=30, help="自动增量回看分钟数")
    parser.add_argument("--batch-size", type=int, default=1000, help="同步分页大小")
    parser.add_argument("--full", action="store_true", help="按 start-date 做基线范围同步，不自动计算增量起点")
    parser.add_argument("--dry-run", action="store_true", help="只预演，不写入 ODS/DWD")
    return parser.parse_args()


def main() -> int:
    """执行同步并输出 JSON 结果。"""
    args = parse_args()
    request = LogisticsSystemSyncRequest(
        start_date=args.start_date,
        updated_since=args.updated_since,
        auto_incremental=not args.full,
        incremental_overlap_minutes=args.overlap_minutes,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )
    result = LogisticsSystemSyncService().sync_formal_data(request)
    print(json.dumps(result.model_dump(), ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
