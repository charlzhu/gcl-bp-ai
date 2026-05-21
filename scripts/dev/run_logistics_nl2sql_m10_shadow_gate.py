#!/usr/bin/env python
"""
物流 NL2SQL M10 shadow gate 评估集运行器。

用法：
    python scripts/dev/run_logistics_nl2sql_m10_shadow_gate.py \\
        --artifact-dir /tmp/m10-shadow-gate

可选参数：
    --sample-limit N    仅跑前 N 个样本（默认全量）
    --silent            不在 stdout 输出详细报告
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保能从项目根 import
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from backend.app.domains.logistics.services.nl2sql.m10_shadow_gate_runner import (
    build_default_logistics_nl2sql_m10_shadow_gate_samples,
    run_logistics_nl2sql_m10_shadow_gate,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run logistics NL2SQL M10 shadow gate evaluation")
    parser.add_argument("--artifact-dir", default=None, help="directory for sanitized JSONL/Markdown artifacts")
    parser.add_argument("--sample-limit", type=int, default=None, help="limit number of samples to run")
    parser.add_argument("--silent", action="store_true", help="suppress detailed stdout output")
    args = parser.parse_args()

    samples = build_default_logistics_nl2sql_m10_shadow_gate_samples()
    if args.sample_limit:
        samples = samples[: args.sample_limit]

    result = run_logistics_nl2sql_m10_shadow_gate(samples=samples, artifact_dir=args.artifact_dir)

    if args.silent:
        summary = {
            "total": result.report.total,
            "status_match_count": result.report.status_match_count,
            "stage_match_count": result.report.stage_match_count,
            "by_expected_status": result.report.by_expected_status,
            "by_actual_status": result.report.by_actual_status,
            "records_path": str(result.records_path) if result.records_path else None,
            "report_path": str(result.report_path) if result.report_path else None,
        }
        print(json.dumps(summary, ensure_ascii=False))
        if result.report.status_match_count < result.report.total:
            sys.exit(1)
        return

    print(f"\n{'='*60}")
    print(f"M10 NL2SQL Shadow Gate Runner")
    print(f"{'='*60}")
    print(f"Total samples: {result.report.total}")
    print(f"Status match: {result.report.status_match_count}/{result.report.total}")
    print(f"Stage match: {result.report.stage_match_count}/{result.report.total}")
    print(f"\nBy expected status: {result.report.by_expected_status}")
    print(f"By actual status: {result.report.by_actual_status}")
    print(f"By category: {result.report.by_category}")
    print()

    for outcome in result.outcomes:
        icon = "✅" if outcome.status_match else "❌"
        print(f"  {icon} {outcome.sample.sample_id}")
        print(f"      expected={outcome.sample.expected_gate_status}, actual={outcome.report.status}")
        print(f"      stage={outcome.report.stage}, errors={outcome.report.error_codes[:3]}")

    if result.records_path:
        print(f"\nRecords: {result.records_path}")
    if result.report_path:
        print(f"Report: {result.report_path}")
    print(f"{'='*60}\n")

    status_match = result.report.status_match_count
    total = result.report.total
    if status_match < total:
        print(f"WARNING: {total - status_match}/{total} samples have status mismatch")
        sys.exit(1)


if __name__ == "__main__":
    main()
