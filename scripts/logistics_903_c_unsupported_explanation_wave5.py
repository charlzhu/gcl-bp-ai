from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.logistics_903_c_unsupported_explanation_wave2 import evaluate


REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_c_unsupported_explanation_wave5_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_C_UNSUPPORTED_EXPLANATION_WAVE5.md"


def _write_json(path: Path, payload: Any) -> None:
    """写出 JSON 文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _render_doc(report: dict[str, Any]) -> str:
    """渲染 C 类拒答解释 Wave5 复检文档。

    参数：
        report: C 类拒答解释复检结构化报告。

    返回：
        Markdown 文档内容。
    """

    summary = report["summary"]
    lines = [
        "# 903 C 类拒答解释 Wave5 复检",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、结论",
        "",
        f"- 是否真实调用 LLM：`{report['use_live_llm']}`",
        f"- C 类复检总数：`{summary['total_c_questions']}`",
        f"- 拒答边界通过：`{summary['boundary_passed']}`",
        f"- 拒答边界失败：`{summary['boundary_failed']}`",
        f"- 具备业务解释与改问建议：`{summary['explanation_available']}`",
        f"- unsupported 类别分布：`{summary['category_breakdown']}`",
        f"- provider mode 分布：`{summary['provider_mode_breakdown']}`",
        "",
        "## 二、治理原则",
        "",
        "- C 类最终裁决仍由规则层和 response policy 锁定。",
        "- LLM 只允许生成业务可理解解释和改问方向，不允许改判成 success。",
        "- 本轮默认 dry-run/off，不依赖 live LLM 作为基础回归条件。",
        "",
        "## 三、失败项",
        "",
    ]
    if report["failed_items"]:
        for item in report["failed_items"]:
            lines.append(f"- {item['question_id']} | {item['failure_reason']} | {item['question']}")
    else:
        lines.append("- 当前无 C 边界失败项。")
    return "\n".join(lines) + "\n"


def main() -> None:
    """命令行入口：执行 C=69 Wave5 拒答解释复检。"""

    parser = argparse.ArgumentParser(description="903 C 类拒答解释 Wave5 复检")
    parser.add_argument("--with-live-llm", action="store_true", help="启用真实 LLM 生成拒答解释。")
    parser.add_argument("--limit", type=int, default=0, help="限制复检题数；0 表示全量 C 类。")
    args = parser.parse_args()
    report = evaluate(use_live_llm=bool(args.with_live_llm), limit=args.limit)
    _write_json(REPORT_PATH, report)
    DOC_PATH.write_text(_render_doc(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
