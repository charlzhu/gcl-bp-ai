from __future__ import annotations

import json
import argparse
from collections import Counter

from plan_bom_runtime import TMP_DIR, build_runtime_session, build_standardized_outputs, import_source_zip, write_markdown


def parse_args() -> argparse.Namespace:
    """解析脚本参数。

    返回：
        argparse.Namespace，包含可选的 BOM 源数据 zip 路径。
    """

    parser = argparse.ArgumentParser(description="治理并导入计划 BOM 源数据")
    parser.add_argument("--source-zip", default=None, help="BOM 源数据 zip 路径；未传时读取项目内默认路径")
    return parser.parse_args()


def main() -> None:
    """治理并导入 BOM 源数据。

    返回：
        无返回值。脚本会输出 JSON 和 Markdown 报告。
    """

    args = parse_args()
    summary = import_source_zip(source_zip=args.source_zip, reset=True)
    session = build_runtime_session(reset=False)
    standardized = build_standardized_outputs(session)
    status_counter = Counter(item["status"] for item in summary["reports"])
    report = {
        **summary,
        "standardized": standardized,
        "status_distribution": dict(status_counter),
    }
    (TMP_DIR / "plan_bom_data_quality_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "## 数据源",
        f"- ZIP：`{summary['source_zip']}`",
        f"- 有效 BOM Excel 文件数：`{summary['file_count']}`",
        f"- 成功导入：`{summary['success_count']}`",
        f"- 失败导入：`{summary['failed_count']}`",
        f"- 解析订单头：`{summary['parsed_orders_count']}`",
        f"- 解析材料行：`{summary['parsed_materials_count']}`",
        f"- warning：`{summary['warning_count']}`",
        f"- error：`{summary['error_count']}`",
        "",
        "## 标准化输出",
        f"- 标准化材料：`{standardized['standardized_data_path']}`",
        f"- 订单索引：`{standardized['order_index_path']}`",
        "- 材料别名配置：`backend/app/domains/plan_bom/config/material_aliases.json`",
        "",
        "## 数据质量结论",
        "- 已过滤 `__MACOSX` 和 `._*` 噪音文件。",
        "- 已复用现有 `PlanBomExcelImportService` 解析 Excel，不依赖乱码文件名作为唯一事实来源。",
        "- 失败批次保留在 JSON 报告中；成功批次已进入本地运行库供回归复用。",
    ]
    write_markdown(TMP_DIR.parents[1] / "docs" / "PLAN_BOM_DATA_QUALITY_REPORT.md", "PLAN_BOM_DATA_QUALITY_REPORT", lines)


if __name__ == "__main__":
    main()
