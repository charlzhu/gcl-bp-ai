from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.db.session import SessionLocal
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.domains.logistics.services.llm_clarification_assist_service import (
    LogisticsLlmClarificationAssistService,
)


PLAN_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_b_candidate_clarification_review_batches.json"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_b_candidate_review_round1_report.json"
REVIEW_RESULT_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_b_candidate_review_round1_results.json"
)
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_B_CANDIDATE_REVIEW_ROUND1.md"
BATCH_ID = "BCR1"


def _set_batch_context(batch_id: str) -> None:
    """切换 BCR 澄清模板复检批次上下文。

    参数：
        batch_id: BCR 批次编号，例如 BCR1 或 BCR2。

    返回：
        无返回值；函数会更新本脚本后续读写使用的全局路径。

    说明：
        1. 保留原脚本名是为了兼容既有 BCR1 调用；
        2. 后续 BCR2/BCR3/BCR4 复用同一套真实 data-qa 复检逻辑；
        3. 每个批次输出独立结果文件和 Markdown 文档，避免相互覆盖。
    """

    global REPORT_PATH, REVIEW_RESULT_PATH, DOC_PATH, BATCH_ID

    normalized_batch_id = batch_id.strip().upper()
    round_number = normalized_batch_id.replace("BCR", "")
    BATCH_ID = normalized_batch_id
    REPORT_PATH = (
        PROJECT_ROOT
        / f"tmp/logistics_question_bank/logistics_b_candidate_review_round{round_number}_report.json"
    )
    REVIEW_RESULT_PATH = (
        PROJECT_ROOT
        / f"backend/app/domains/logistics/config/logistics_b_candidate_review_round{round_number}_results.json"
    )
    DOC_PATH = PROJECT_ROOT / f"docs/LOGISTICS_B_CANDIDATE_REVIEW_ROUND{round_number}.md"


class NoopQueryLogRepository:
    """无副作用查询日志仓储。

    说明：
        1. BCR 必须真实调用 data-qa 主链路验证澄清边界；
        2. 回归脚本不应污染正式业务查询历史；
        3. 因此统一注入空日志仓储实现。
    """

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        """忽略查询日志写入请求。"""

        _ = db, payload
        return 0


@dataclass
class BCRReviewRecord:
    """BCR 单题澄清模板复检结果。"""

    review_id: str
    question_id: str
    question: str
    review_category: str
    expected_response_status: str
    actual_status_code: str
    actual_intent: str
    actual_needs_clarification: bool
    actual_supported: bool
    actual_query_key: str | None
    rule_clarification_category: str | None
    rule_missing_slots: list[str]
    planned_missing_slots: list[str]
    covered_planned_slots: list[str]
    actual_questions: list[str]
    planned_questions: list[str]
    passed_boundary: bool
    template_update_recommended: bool
    failure_classification: str | None
    failure_reason: str | None
    review_conclusion: str


def _load_json(path: Path) -> Any:
    """读取 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))


def _load_batch_items() -> list[dict[str, Any]]:
    """读取当前 BCR 批次题目。"""

    payload = _load_json(PLAN_PATH)
    items = [item for item in payload["items"] if item["batch_id"] == BATCH_ID]
    items.sort(key=lambda item: item["review_id"])
    return items


def _run_query(service: LogisticsDataQaService, question: str) -> dict[str, Any]:
    """执行单题查询并返回 JSON 响应。"""

    result = service.query(
        LogisticsDataQaQueryRequest(question=question),
        trace_id=f"logistics-b-candidate-review-{BATCH_ID.lower()}",
    )
    return result.model_dump(mode="json")


SLOT_KEYWORDS = {
    "统计时间范围": ["时间", "年份", "月份", "季度", "起止", "范围"],
    "状态枚举口径": ["状态枚举", "状态口径", "SIGNEDFOR", "PREASSIGN", "状态分布"],
    "异常/高成本定义": ["异常", "高成本", "阈值", "超过", "标准", "判断"],
    "输出形态": ["输出", "明细", "汇总", "排名", "表"],
    "是否需要明细": ["明细", "清单", "逐条"],
    "运输方式口径": ["运输方式", "公路", "铁路", "水路", "汽运", "铁运", "多式联运"],
    "指标口径": ["指标", "发运量", "运费", "车次", "件数", "单瓦", "成本"],
    "对账对象": ["对账对象", "一致性对象", "客户名称", "承运商", "车牌", "状态字段", "费用字段", "合同", "招标", "询比价"],
    "差异阈值": ["差异阈值", "异常判定", "完全不一致", "字段缺失", "金额差异", "一对多", "多对一"],
    "比较维度": ["比较维度", "维度", "承运商", "仓库", "状态", "省份", "字段"],
    "车次/车辆数口径": ["车次/车辆数口径", "车次", "车辆数", "唯一车辆", "车型数量", "车辆字段"],
    "车型口径": ["车型口径", "车型", "17.5", "17.5 米", "13 米", "全部车型"],
    "单位口径": ["单位", "MW", "吨", "件", "元", "车"],
    "采购方式口径": ["采购方式", "采购", "自采", "集采"],
    "分组维度": ["维度", "拆分", "按", "区域", "省份", "承运商", "客户"],
    "始发/目的地范围": ["始发", "目的地", "发往", "线路", "城市", "地址"],
    "车型/运输方式限制": ["车型", "车辆", "17.5", "13", "运输方式"],
    "客户/项目名称": ["客户/项目名称", "客户标准名称", "项目名称", "客户名前缀", "简称归并"],
    "是否需要排名": ["是否需要排名", "排名", "TopN", "前几名", "单项结果"],
    "排名指标": ["排名指标", "平均总费用", "市场份额", "超计划比例", "发运量", "单瓦成本"],
    "排名方向": ["排名方向", "从高到低", "从低到高", "最高", "最低", "前 10", "后 10"],
    "TopN 数量": ["TopN 数量", "TopN", "前 10", "前10", "前十大", "后 10", "全部排序"],
}


def _covered_planned_slots(actual_questions: list[str], planned_slots: list[str]) -> list[str]:
    """判断当前追问是否覆盖计划要求的缺口径槽位。

    说明：
        1. BCR 关注的是“缺什么口径是否问清楚”，不是追问文本是否完全一致；
        2. 每个计划槽位维护一组业务关键词，只要当前追问命中任一关键词就视为覆盖；
        3. 未覆盖的槽位会进入后续模板优化清单。
    """

    actual_text = "；".join(actual_questions)
    covered: list[str] = []
    for slot in planned_slots:
        keywords = SLOT_KEYWORDS.get(slot, [slot])
        if any(keyword in actual_text for keyword in keywords):
            covered.append(slot)
    return covered


def _resolve_boundary_failure(response: dict[str, Any]) -> tuple[str | None, str | None]:
    """判断 B_candidate 是否仍稳定保持澄清边界。"""

    query_plan = response.get("query_plan") or {}
    if response.get("needs_clarification") is True and query_plan.get("intent") == "clarification":
        return None, None
    if query_plan.get("query_key"):
        return "边界回退-误答", f"当前误命中 query_key={query_plan.get('query_key')}"
    if query_plan.get("intent") == "unsupported" or response.get("supported") is False:
        return "边界回退-误拒答", "当前误落 unsupported，不符合 B_candidate 澄清边界"
    return "边界回退-未知状态", "当前未稳定返回 needs_clarification=true"


def run_bcr_review(*, with_live_llm: bool = False) -> dict[str, Any]:
    """执行当前 BCR 澄清模板复检。

    参数：
        with_live_llm: 是否启用真实 LLM 澄清辅助。默认关闭，用于稳定复检规则模板是否覆盖缺口径。

    返回：
        BCR 复检报告，包含边界通过数、模板优化建议和失败归因。
    """

    batch_items = _load_batch_items()
    db = SessionLocal()
    clarification_assist_service = LogisticsLlmClarificationAssistService(
        enabled=with_live_llm,
        mode="assist" if with_live_llm else "off",
        sample_rate=1.0 if with_live_llm else 0.0,
        audit_enabled=False,
    )
    service = LogisticsDataQaService(
        db=db,
        query_log_repository=NoopQueryLogRepository(),
        clarification_assist_service=clarification_assist_service,
    )
    records: list[BCRReviewRecord] = []
    failure_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()
    update_counter: Counter[str] = Counter()

    try:
        for item in batch_items:
            try:
                response = _run_query(service, item["question"])
                query_plan = response.get("query_plan") or {}
                status_code = (response.get("status") or {}).get("code", "NO_STATUS")
                failure_classification, failure_reason = _resolve_boundary_failure(response)
                actual_questions = list(response.get("clarification_questions") or [])
                planned_questions = list(item.get("suggested_clarification_questions") or [])
                planned_slots = list(item.get("missing_slots_to_check") or [])
                covered_slots = _covered_planned_slots(actual_questions, planned_slots)
                template_update_recommended = (
                    failure_classification is None
                    and len(covered_slots) < len(planned_slots)
                )
                if template_update_recommended:
                    update_counter[item["review_category"]] += 1
                conclusion = (
                    "边界稳定，建议补充更贴近业务的澄清模板。"
                    if template_update_recommended
                    else "边界稳定，当前追问方向可接受。"
                )
                if failure_classification:
                    conclusion = "边界未通过，必须先修复规则层裁决。"
                record = BCRReviewRecord(
                    review_id=item["review_id"],
                    question_id=item["question_id"],
                    question=item["question"],
                    review_category=item["review_category"],
                    expected_response_status=item["expected_response_status"],
                    actual_status_code=status_code,
                    actual_intent=query_plan.get("intent", ""),
                    actual_needs_clarification=bool(response.get("needs_clarification")),
                    actual_supported=bool(response.get("supported")),
                    actual_query_key=query_plan.get("query_key"),
                    rule_clarification_category=query_plan.get("clarification_category"),
                    rule_missing_slots=list(query_plan.get("clarification_missing_slots") or []),
                    planned_missing_slots=planned_slots,
                    covered_planned_slots=covered_slots,
                    actual_questions=actual_questions,
                    planned_questions=planned_questions,
                    passed_boundary=failure_classification is None,
                    template_update_recommended=template_update_recommended,
                    failure_classification=failure_classification,
                    failure_reason=failure_reason,
                    review_conclusion=conclusion,
                )
            except Exception as exc:  # noqa: BLE001
                record = BCRReviewRecord(
                    review_id=item["review_id"],
                    question_id=item["question_id"],
                    question=item["question"],
                    review_category=item["review_category"],
                    expected_response_status=item["expected_response_status"],
                    actual_status_code="EXCEPTION",
                    actual_intent="exception",
                    actual_needs_clarification=False,
                    actual_supported=False,
                    actual_query_key=None,
                    rule_clarification_category=None,
                    rule_missing_slots=[],
                    planned_missing_slots=list(item.get("missing_slots_to_check") or []),
                    covered_planned_slots=[],
                    actual_questions=[],
                    planned_questions=list(item.get("suggested_clarification_questions") or []),
                    passed_boundary=False,
                    template_update_recommended=False,
                    failure_classification="代码问题",
                    failure_reason=f"执行异常：{exc}",
                    review_conclusion="执行异常，需先排查代码或数据环境。",
                )
            records.append(record)
            category_counter[record.review_category] += 1
            status_counter[record.actual_status_code] += 1
            if record.failure_classification:
                failure_counter[record.failure_classification] += 1
    finally:
        db.close()

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "batch_id": BATCH_ID,
        "review_policy": (
            "规则层锁定澄清边界；默认关闭 live LLM 以稳定复检模板覆盖，"
            "如需抽样评估 LLM 追问候选可使用 --with-live-llm。"
        ),
        "with_live_llm": with_live_llm,
        "summary": {
            "total_questions": len(records),
            "boundary_passed_questions": sum(1 for item in records if item.passed_boundary),
            "boundary_failed_questions": sum(1 for item in records if not item.passed_boundary),
            "template_update_recommended_questions": sum(
                1 for item in records if item.template_update_recommended
            ),
            "category_breakdown": dict(category_counter),
            "status_code_breakdown": dict(status_counter),
            "failure_classification_breakdown": dict(failure_counter),
            "template_update_recommended_breakdown": dict(update_counter),
        },
        "items": [asdict(item) for item in records],
        "failed_items": [asdict(item) for item in records if not item.passed_boundary],
        "template_update_items": [
            asdict(item) for item in records if item.template_update_recommended
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    """渲染当前 BCR 澄清模板复检文档。"""

    summary = report["summary"]
    batch_id = report["batch_id"]
    lines = [
        f"# {batch_id} B_candidate 澄清模板复检",
        "",
        "## 一、结论",
        "",
        (
            f"{batch_id} 共复检 **{summary['total_questions']}** 条 B_candidate，"
            f"澄清边界通过 **{summary['boundary_passed_questions']}** 条，"
            f"失败 **{summary['boundary_failed_questions']}** 条。"
        ),
        f"其中建议优化业务化追问模板 **{summary['template_update_recommended_questions']}** 条。",
        "",
        "## 二、边界规则",
        "",
        "- 每题必须稳定返回 `needs_clarification=true`。",
        "- 不允许误命中 query_key 后变成 success。",
        "- 不允许误落 unsupported。",
        "- LLM 只能做缺口径识别和追问候选生成，不能做最终边界裁决。",
        f"- 本次复检 live LLM 调用：`{'开启' if report.get('with_live_llm') else '关闭'}`；默认关闭以稳定验证规则模板覆盖。",
        "",
        "## 三、复检题型分布",
        "",
    ]
    for key, value in summary["category_breakdown"].items():
        lines.append(f"- `{key}`：`{value}`")
    lines.extend(["", "## 四、失败项", ""])
    if report["failed_items"]:
        for item in report["failed_items"]:
            lines.append(
                f"- {item['review_id']} / {item['question_id']}：{item['failure_classification']}，{item['failure_reason']}"
            )
    else:
        lines.append("- 当前无边界失败项。")
    lines.extend(["", "## 五、建议优化模板的代表题", ""])
    for item in report["template_update_items"][:10]:
        lines.append(
            f"- {item['review_id']} / {item['question_id']}：{item['question']}；建议追问："
            f"{'；'.join(item['planned_questions'][:2])}"
        )
    if not report["template_update_items"]:
        lines.append("- 当前无建议优化项。")
    lines.extend(
        [
            "",
            "## 六、下一步",
            "",
            "- 若边界失败为 0，可继续把模板优化项分批固化到规则层或 LLM 候选追问层。",
            "- 若存在边界失败，必须先修复规则层，不能进入模板美化。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    """执行 BCR B_candidate 澄清模板复检。"""

    parser = argparse.ArgumentParser(description="BCR B_candidate 澄清模板复检")
    parser.add_argument(
        "--batch-id",
        choices=["BCR1", "BCR2", "BCR3", "BCR4"],
        default=BATCH_ID,
        help="要执行的 BCR 澄清模板复检批次。",
    )
    parser.add_argument(
        "--with-live-llm",
        action="store_true",
        help="启用真实 LLM 澄清辅助；默认关闭以稳定复检规则模板覆盖。",
    )
    args = parser.parse_args()
    _set_batch_context(args.batch_id)
    report = run_bcr_review(with_live_llm=args.with_live_llm)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REVIEW_RESULT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC_PATH.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
