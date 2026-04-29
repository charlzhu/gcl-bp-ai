from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_PAGE_PATH = PROJECT_ROOT / "frontend/src/views/logistics-data-qa/LogisticsDataQaPage.vue"
API_TS_PATH = PROJECT_ROOT / "frontend/src/api/logistics.ts"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_data_qa_frontend_acceptance_check_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_DATA_QA_FRONTEND_ACCEPTANCE_CHECK.md"


def _write_json(path: Path, payload: Any) -> None:
    """写出 JSON 文件。

    参数：
        path: 输出路径。
        payload: JSON 对象。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _contains(text: str, *tokens: str) -> bool:
    """判断文本是否包含所有 token。"""

    return all(token in text for token in tokens)


def _build_report() -> dict[str, Any]:
    """执行物流 data-qa 前端联调静态验收。

    返回：
        前端状态覆盖报告。

    业务逻辑：
        本脚本不新增页面，只检查当前正式页是否具备 A/B/C、空结果、错误、加载和高级信息展示能力。
    """

    page = FRONTEND_PAGE_PATH.read_text(encoding="utf-8")
    api = API_TS_PATH.read_text(encoding="utf-8")
    checks = [
        {
            "scenario": "成功态",
            "passed": _contains(page, "isTurnSuccess", "chat-table-card", "getTurnColumns", "getTurnRows")
            and _contains(page, "answer_summary", "query_plan", "data_scope"),
            "evidence": "成功态展示 answer_summary、结果表格、数据范围和 query_plan。",
        },
        {
            "scenario": "追问态",
            "passed": _contains(page, "isTurnClarification", "clarification_questions", "chat-question-list"),
            "evidence": "追问态展示后端 clarification_questions，不在前端硬编码追问。",
        },
        {
            "scenario": "拒答态",
            "passed": _contains(page, "isTurnUnsupported", "getTurnUnsupportedReason", "chat-unsupported-tips"),
            "evidence": "拒答态展示 unsupported_reason/status.message/answer_summary 和可改问方向。",
        },
        {
            "scenario": "空结果态",
            "passed": _contains(page, "isTurnEmpty", "chat-empty-tips", "未查到结果"),
            "evidence": "OK 但 rows 为空时展示空结果说明。",
        },
        {
            "scenario": "错误态",
            "passed": _contains(page, "catch (error", "requestError", "查询失败，请稍后重试"),
            "evidence": "接口异常写入消息流并展示友好提示，不暴露堆栈。",
        },
        {
            "scenario": "加载态",
            "passed": _contains(page, "loading", "chat-bubble--loading", "正在查询"),
            "evidence": "请求过程中展示 loading 气泡。",
        },
        {
            "scenario": "边界输入态",
            "passed": _contains(page, "请输入业务问题", "maxlength=\"200\"", "show-word-limit", "Shift + Enter"),
            "evidence": "空输入会提示补充问题，输入框限制 200 字并保留换行说明。",
        },
        {
            "scenario": "接口契约",
            "passed": _contains(api, "/logistics/data-qa/query", "LogisticsDataQaStatus", "unsupported_reason"),
            "evidence": "前端 API 类型保留 status、query_plan 和 unsupported_reason。",
        },
        {
            "scenario": "底部输入固定与对话滚动",
            "passed": _contains(page, ".chat-main", "overflow: hidden", ".chat-thread", "overflow-y: auto", ".chat-composer"),
            "evidence": "对话区滚动、输入区在页面底部随主容器固定。",
        },
    ]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "frontend_page": str(FRONTEND_PAGE_PATH),
        "api_contract": str(API_TS_PATH),
        "summary": {
            "total_checks": len(checks),
            "passed_checks": sum(1 for item in checks if item["passed"]),
            "failed_checks": sum(1 for item in checks if not item["passed"]),
            "blocking_issue": any(not item["passed"] for item in checks),
        },
        "checks": checks,
    }


def _render_doc(report: dict[str, Any]) -> str:
    """渲染前端联调检查文档。"""

    summary = report["summary"]
    lines = [
        "# 物流 data-qa 前后端联调闭环检查",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、检查结论",
        "",
        f"- 检查项：`{summary['total_checks']}`",
        f"- 通过：`{summary['passed_checks']}`",
        f"- 失败：`{summary['failed_checks']}`",
        f"- 是否存在阻断问题：`{summary['blocking_issue']}`",
        "",
        "## 二、检查明细",
        "",
        "| 场景 | 是否通过 | 证据 |",
        "| --- | --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| {item['scenario']} | {item['passed']} | {item['evidence']} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    """命令行入口：执行前端联调静态检查。"""

    report = _build_report()
    _write_json(REPORT_PATH, report)
    DOC_PATH.write_text(_render_doc(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
