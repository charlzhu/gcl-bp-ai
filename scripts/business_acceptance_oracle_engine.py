#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "tmp" / "business_acceptance_oracle"
ORACLE_DIR = PROJECT_ROOT / "tests" / "business_acceptance" / "oracle"
if str(ORACLE_DIR) not in sys.path:
    sys.path.insert(0, str(ORACLE_DIR))

from engine import convert_normalized_cases


def write_json(path: Path, payload: Any) -> None:
    """写入 JSON 文件。

    参数：
        path：输出文件路径。
        payload：可 JSON 序列化的数据。
    返回值：无。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_markdown(path: Path, title: str, lines: list[str]) -> None:
    """写入 Markdown 报告。

    参数：
        path：输出文件路径。
        title：报告标题。
        lines：正文行。
    返回值：无。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([f"# {title}", "", *lines]).rstrip() + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    """读取 JSON 文件。

    参数：
        path：JSON 文件路径。
    返回值：
        JSON 对象字典。
    """

    return json.loads(path.read_text(encoding="utf-8"))


def build_self_test_normalized_cases() -> dict[str, Any]:
    """构建 Oracle Engine 自测用 normalized cases。

    参数：无。
    返回值：
        最小 normalized_cases 结构。

    业务逻辑：
        自测只覆盖路由和状态转换，不依赖真实业务文件、数据库或 Web E2E。
    """

    return {
        "generated_at": "self-test",
        "source_file": "self-test",
        "total_cases": 5,
        "items": [
            {
                "case_id": "BA-0001",
                "question": "2025年各承运商运量分别是多少？",
                "domain": "logistics",
                "question_type": "grouping",
                "oracle_status": "NEED_ORACLE",
            },
            {
                "case_id": "BA-0002",
                "question": "2026年物流总运费是多少？",
                "domain": "logistics",
                "question_type": "aggregate",
                "oracle_status": "NEED_ORACLE",
            },
            {
                "case_id": "BA-0003",
                "question": "各承运商运量分别是多少？",
                "domain": "logistics",
                "question_type": "grouping",
                "oracle_status": "NEED_ORACLE",
            },
            {
                "case_id": "BA-0004",
                "question": "2026年物流情况怎么样？",
                "domain": "logistics",
                "question_type": "aggregate",
                "oracle_status": "NEED_ORACLE",
            },
            {
                "case_id": "BA-0005",
                "question": "A123订单用了哪些BOM物料？",
                "domain": "bom",
                "question_type": "bom_lookup",
                "oracle_status": "NEED_ORACLE",
            },
        ],
    }


def build_oracle_report(oracle_cases: dict[str, Any], oracle_path: Path) -> list[str]:
    """生成 Oracle Engine 路由报告正文。

    参数：
        oracle_cases：Oracle Engine 输出对象。
        oracle_path：oracle_cases.json 输出路径。
    返回值：
        Markdown 正文行。
    """

    status_lines = [
        f"- {status}: `{count}`" for status, count in oracle_cases.get("oracle_status_distribution", {}).items()
    ] or ["- 无"]
    route_lines = [
        f"- {source}: `{count}`" for source, count in oracle_cases.get("source_route_distribution", {}).items()
    ] or ["- 无"]
    missing_counter: Counter[str] = Counter()
    for case in oracle_cases.get("items", []):
        for slot in (case.get("oracle_engine") or {}).get("missing_slots") or []:
            missing_counter[str(slot)] += 1
    missing_lines = [f"- {slot}: `{count}`" for slot, count in missing_counter.items()] or ["- 无"]

    sample_rows = [
        "| Case ID | Domain | Oracle Status | Routes | Metrics | Question |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case in oracle_cases.get("items", [])[:80]:
        engine_meta = case.get("oracle_engine") or {}
        routes = ",".join(
            f"{route.get('year')}:{route.get('source')}" for route in engine_meta.get("source_routes") or []
        )
        metrics = ",".join(engine_meta.get("metrics") or [])
        question = str(case.get("question") or "").replace("|", "｜")
        sample_rows.append(
            f"| {case.get('case_id')} | {case.get('domain')} | {case.get('oracle_status')} | "
            f"{routes or '-'} | {metrics or '-'} | {question} |"
        )

    return [
        f"- Oracle Engine 版本：`{oracle_cases.get('oracle_engine_version')}`",
        f"- 输出产物：`{oracle_path}`",
        f"- 总 case 数：`{oracle_cases.get('total_cases')}`",
        "",
        "## Oracle Status Distribution",
        *status_lines,
        "",
        "## Source Route Distribution",
        *route_lines,
        "",
        "## Missing Slots",
        *missing_lines,
        "",
        "## Sample Cases",
        *sample_rows,
        "",
        "## Notes",
        "- P2.1 只建设物流 Oracle Engine 基础接口和数据源路由。",
        "- 当前不计算复杂业务指标，不访问数据库，不执行 Web E2E。",
        "- BOM case 保持导入阶段状态，本轮不处理 BOM Oracle。",
    ]


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    参数：无。
    返回值：argparse 参数解析器。
    """

    parser = argparse.ArgumentParser(description="转换 business_acceptance normalized_cases 的物流 Oracle Engine 状态")
    parser.add_argument("--normalized-file", type=Path, help="normalized_cases.json 文件路径")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Oracle Engine 产物输出目录")
    parser.add_argument("--self-test", action="store_true", help="使用内置 normalized cases 执行轻量自测")
    return parser


def main() -> int:
    """命令行入口。

    参数：通过 argparse 读取。
    返回值：0 表示执行成功。
    """

    args = build_parser().parse_args()
    if args.self_test:
        normalized_cases = build_self_test_normalized_cases()
    else:
        if args.normalized_file is None:
            raise SystemExit("必须提供 --normalized-file，或使用 --self-test 运行内置自测。")
        normalized_cases = load_json(args.normalized_file)

    output_dir: Path = args.output_dir
    oracle_path = output_dir / "oracle_cases.json"
    report_path = output_dir / "oracle_engine_report.md"
    oracle_cases = convert_normalized_cases(normalized_cases)
    write_json(oracle_path, oracle_cases)
    write_markdown(report_path, "ORACLE_ENGINE_REPORT", build_oracle_report(oracle_cases, oracle_path))

    print("business_acceptance oracle engine finished")
    print(f"oracle_cases: {oracle_path}")
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

