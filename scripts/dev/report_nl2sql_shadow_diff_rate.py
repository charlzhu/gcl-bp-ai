#!/usr/bin/env python
"""NL2SQL Shadow 对比差异率日报——定时扫描告警 JSONL 并输出报表。

用法：
    python scripts/dev/report_nl2sql_shadow_diff_rate.py
    python scripts/dev/report_nl2sql_shadow_diff_rate.py --period 24h

环境变量：
    NL2SQL_SHADOW_ALERT_LOG_PATH: 告警 JSONL 文件路径（默认 ai/outbox/nl2sql-shadow-compare-alerts.jsonl）

多域支持：
    报表按 domain 字段（logistics / business_analysis / plan_bom）分别统计差异率。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


_DEFAULT_ALERT_LOG_PATH = "ai/outbox/nl2sql-shadow-compare-alerts.jsonl"


def _resolve_log_path() -> str:
    return os.getenv("NL2SQL_SHADOW_ALERT_LOG_PATH", _DEFAULT_ALERT_LOG_PATH)


def main() -> int:
    """解析参数，扫描告警文件，输出差异率日报。"""
    parser = argparse.ArgumentParser(description="NL2SQL Shadow 对比差异率日报")
    parser.add_argument(
        "--period",
        default="24h",
        help="统计周期（24h, 7d, 30d），默认 24h",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出报表")
    args = parser.parse_args()

    log_path = Path(_resolve_log_path())
    if not log_path.exists():
        report: dict = {
            "total_shadow": 0,
            "total_alerts": 0,
            "diff_ratio": 0.0,
            "period": args.period,
            "by_flag": {},
            "by_domain": {},
            "message": "告警日志文件不存在，当前周期内无差异对比记录。",
        }
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"# NL2SQL Shadow 差异率日报\n\n周期: {args.period}\n状态: 无记录（告警日志文件不存在）")
        return 0

    # 解析周期
    period_map = {"24h": 1, "7d": 7, "30d": 30}
    days = period_map.get(args.period, 1)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    total = 0
    alerts = 0
    by_flag: dict[str, int] = {}
    by_domain: dict[str, dict[str, int]] = {}

    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts_str = record.get("ts", "")
            try:
                ts = datetime.fromisoformat(ts_str)
                # 统一为 offset-aware（JSONL 中的 ts 可能是起止时间，需兼容）
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            if ts < cutoff:  # 超出周期
                continue

            total += 1
            domain = record.get("domain", "logistics")
            mf = record.get("mismatch_flags", [])
            if mf:
                alerts += 1
                for flag in mf:
                    by_flag[flag] = by_flag.get(flag, 0) + 1

            # 按域累计
            if domain not in by_domain:
                by_domain[domain] = {"total": 0, "alerts": 0}
            by_domain[domain]["total"] += 1
            if mf:
                by_domain[domain]["alerts"] += 1

    diff_ratio = (alerts / total * 100) if total > 0 else 0.0

    report = {
        "total_shadow": total,
        "total_alerts": alerts,
        "diff_ratio": round(diff_ratio, 2),
        "period": args.period,
        "by_flag": dict(sorted(by_flag.items(), key=lambda x: -x[1])),
        "by_domain": {d: v for d, v in sorted(by_domain.items())},
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"# NL2SQL Shadow 差异率日报\n")
        print(f"周期: {args.period}")
        print(f"总 shadow 次数: {total}")
        print(f"差异告警次数: {alerts}")
        print(f"差异率: {diff_ratio:.2f}%")
        if by_flag:
            print(f"\n按差异类型:")
            for flag, count in sorted(by_flag.items(), key=lambda x: -x[1]):
                print(f"  {flag}: {count}")
        if by_domain:
            print(f"\n按业务域:")
            for domain, stats in sorted(by_domain.items()):
                dr = round(stats["alerts"] / stats["total"] * 100, 2) if stats["total"] > 0 else 0.0
                print(f"  {domain}: {stats['total']} 次 shadow, {stats['alerts']} 次差异, 差异率 {dr}%")
        print()
        if total == 0:
            print("当前周期内无 NL2SQL shadow 对比记录。")
        elif diff_ratio == 0:
            print("当前周期内所有 shadow 结果与正式 QA 完全匹配。")
        elif diff_ratio < 5:
            print(f"差异率 {diff_ratio:.2f}%：较低差异，可接受。建议持续观察。")
        elif diff_ratio < 20:
            print(f"⚠️ 差异率 {diff_ratio:.2f}%：中等差异，建议排查 root cause。")
        else:
            print(f"🔴 差异率 {diff_ratio:.2f}%：高差异！需要即时介入。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
