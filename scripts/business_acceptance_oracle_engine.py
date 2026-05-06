#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "tmp" / "business_acceptance_oracle"
ORACLE_DIR = PROJECT_ROOT / "tests" / "business_acceptance" / "oracle"
if str(ORACLE_DIR) not in sys.path:
    sys.path.insert(0, str(ORACLE_DIR))

from engine import convert_normalized_cases
from logistics_excel_loader import LogisticsExcelSourceConfig


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


def build_excel_self_test_normalized_cases() -> dict[str, Any]:
    """构建 Excel Oracle 自测用 normalized cases。

    参数：无。
    返回值：
        最小 normalized_cases 结构。

    业务逻辑：
        自测只覆盖 2023-2025 历史 Excel 月度指标计算，不接 MySQL、BOM 或 Web E2E。
    """

    return {
        "generated_at": "excel-self-test",
        "source_file": "excel-self-test",
        "total_cases": 4,
        "items": [
            {
                "case_id": "BA-EXCEL-0001",
                "question": "2025年3月物流运量是多少？",
                "domain": "logistics",
                "question_type": "aggregate",
                "oracle_status": "NEED_ORACLE",
            },
            {
                "case_id": "BA-EXCEL-0002",
                "question": "2025年3月总运费是多少？",
                "domain": "logistics",
                "question_type": "aggregate",
                "oracle_status": "NEED_ORACLE",
            },
            {
                "case_id": "BA-EXCEL-0003",
                "question": "2025年3月车次是多少？",
                "domain": "logistics",
                "question_type": "aggregate",
                "oracle_status": "NEED_ORACLE",
            },
            {
                "case_id": "BA-EXCEL-0004",
                "question": "2025年3月平均运价是多少？",
                "domain": "logistics",
                "question_type": "aggregate",
                "oracle_status": "NEED_ORACLE",
            },
        ],
    }


def create_excel_fixture(output_dir: Path) -> LogisticsExcelSourceConfig:
    """创建 Excel Oracle 自测 fixture。

    参数：
        output_dir：当前脚本输出目录。
    返回值：
        指向 2023/2024/2025 fixture 的来源配置。

    业务逻辑：
        fixture 使用脱敏小样本，只验证 loader、字段映射和月度求和框架，不替代真实历史 Excel 口径。
    """

    from openpyxl import Workbook

    fixture_dir = output_dir / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    year_files: dict[int, Path] = {}
    for year in (2023, 2024, 2025):
        path = fixture_dir / f"logistics_{year}_fixture.xlsx"
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "物流台账"
        worksheet.append(["发货日期", "日实际发运瓦数", "总费用(元)", "车辆数"])
        worksheet.append([date(year, 3, 5), 1000, 120.50, 1])
        worksheet.append([date(year, 3, 20), 2500, 300.75, 2])
        worksheet.append([date(year, 4, 1), 800, 88.00, 1])
        workbook.save(path)
        year_files[year] = path
    return LogisticsExcelSourceConfig(year_files=year_files)


def build_excel_source_config(args: argparse.Namespace, output_dir: Path) -> LogisticsExcelSourceConfig | None:
    """构建 Excel 来源配置。

    参数：
        args：命令行参数。
        output_dir：输出目录。
    返回值：
        LogisticsExcelSourceConfig；未配置时返回 None。
    """

    if args.with_excel_fixture:
        return create_excel_fixture(output_dir)

    year_files: dict[int, Path] = {}
    for year, path in ((2023, args.excel_2023), (2024, args.excel_2024), (2025, args.excel_2025)):
        if path:
            year_files[year] = path
    return LogisticsExcelSourceConfig(year_files=year_files) if year_files else None


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
    expected_status_lines = [
        f"- {status}: `{count}`"
        for status, count in oracle_cases.get("expected_result_status_distribution", {}).items()
    ] or ["- 无"]
    missing_counter: Counter[str] = Counter()
    for case in oracle_cases.get("items", []):
        for slot in (case.get("oracle_engine") or {}).get("missing_slots") or []:
            missing_counter[str(slot)] += 1
    missing_lines = [f"- {slot}: `{count}`" for slot, count in missing_counter.items()] or ["- 无"]

    sample_rows = [
        "| Case ID | Domain | Oracle Status | Routes | Metrics | Expected Result | Question |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case in oracle_cases.get("items", [])[:80]:
        engine_meta = case.get("oracle_engine") or {}
        routes = ",".join(
            f"{route.get('year')}:{route.get('source')}" for route in engine_meta.get("source_routes") or []
        )
        metrics = ",".join(engine_meta.get("metrics") or [])
        expected = case.get("expected_result") or {}
        expected_summary = "-"
        if expected:
            expected_summary = (
                f"{expected.get('calculation_status')}:"
                f"{expected.get('metric')}={expected.get('value')}{expected.get('unit') or ''}"
            )
        question = str(case.get("question") or "").replace("|", "｜")
        sample_rows.append(
            f"| {case.get('case_id')} | {case.get('domain')} | {case.get('oracle_status')} | "
            f"{routes or '-'} | {metrics or '-'} | {expected_summary} | {question} |"
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
        "## Expected Result Status Distribution",
        *expected_status_lines,
        "",
        "## Missing Slots",
        *missing_lines,
        "",
        "## Sample Cases",
        *sample_rows,
        "",
        "## Notes",
        "- P2.2 在可选 Excel 来源配置下支持 2023-2025 历史 Excel 月度运量、月度运费和车次基础计算。",
        "- 默认不配置 Excel 来源时仍只执行 P2.1 路由准备逻辑。",
        "- 当前不访问 MySQL，不执行 Web E2E。",
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
    parser.add_argument("--with-excel-fixture", action="store_true", help="创建并使用脱敏 Excel fixture 执行 P2.2 自测")
    parser.add_argument("--excel-2023", type=Path, help="2023 年物流 Excel 文件路径")
    parser.add_argument("--excel-2024", type=Path, help="2024 年物流 Excel 文件路径")
    parser.add_argument("--excel-2025", type=Path, help="2025 年物流 Excel 文件路径")
    return parser


def main() -> int:
    """命令行入口。

    参数：通过 argparse 读取。
    返回值：0 表示执行成功。
    """

    args = build_parser().parse_args()
    if args.self_test:
        normalized_cases = (
            build_excel_self_test_normalized_cases() if args.with_excel_fixture else build_self_test_normalized_cases()
        )
    else:
        if args.normalized_file is None:
            raise SystemExit("必须提供 --normalized-file，或使用 --self-test 运行内置自测。")
        normalized_cases = load_json(args.normalized_file)

    output_dir: Path = args.output_dir
    oracle_path = output_dir / "oracle_cases.json"
    report_path = output_dir / "oracle_engine_report.md"
    excel_source_config = build_excel_source_config(args, output_dir)
    oracle_cases = convert_normalized_cases(normalized_cases, excel_source_config=excel_source_config)
    write_json(oracle_path, oracle_cases)
    write_markdown(report_path, "ORACLE_ENGINE_REPORT", build_oracle_report(oracle_cases, oracle_path))

    print("business_acceptance oracle engine finished")
    print(f"oracle_cases: {oracle_path}")
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
