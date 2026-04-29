from __future__ import annotations

import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.services.error_code_registry import LogisticsErrorCodeRegistry
from scripts import logistics_903_b_gap_wave4 as wave4


LEDGER_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
REVIEW_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave5_executable_review_report.json"
CLARIFICATION_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave5_clarification_quality_report.json"
CONFIRMATION_PACKAGE_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave5_business_confirmation_package_v2.json"
CONFIRMATION_SHORTLIST_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave5_business_confirmation_shortlist_v2.json"
MIGRATION_CONFIG_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b_gap_wave5_migration_candidates.json"
A_REGRESSION_QUESTION_SET_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b_gap_wave5_a_regression_questions.json"

REVIEW_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_WAVE5_EXECUTABLE_REVIEW.md"
CLARIFICATION_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_WAVE5_CLARIFICATION_QUALITY.md"
CONFIRMATION_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_WAVE5_BUSINESS_CONFIRMATION_PACKAGE_V2.md"
CONFIRMATION_SHORTLIST_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_WAVE5_BUSINESS_CONFIRMATION_SHORTLIST_V2.md"


@dataclass
class Wave5BRecord:
    """Wave5 B 题最终可执行性复核记录。

    参数：
        question_id: 题号。
        question: 原始问题。
        source_group: 来源分组。
        family: 题族。
        governance_pool: 当前治理池。
        original_status_code: 原题真实链路状态码。
        original_query_key: 原题命中的 query_key。
        followup_question: 模拟用户补槽后的完整问题。
        followup_status_code: 补槽后真实链路状态码。
        followup_query_key: 补槽后命中的 query_key。
        final_bucket: Wave5 分层结果。
        recommended_status: 推荐状态。
        missing_slots: 缺失槽位或口径。
        engineering_fix_point: 可工程化修复点。
        clarification_questions: 业务化追问候选。
        clarification_quality: 追问质量结论。
        gap_type: 缺口类型。
        closure_reason: 迁移、保留 B 或转 C 的原因。
    """

    question_id: str
    question: str
    source_group: str
    family: str
    governance_pool: str
    original_status_code: str
    original_query_key: str | None
    original_row_count: int
    followup_question: str
    followup_status_code: str
    followup_query_key: str | None
    followup_row_count: int
    followup_answerable: bool
    final_bucket: str
    recommended_status: str
    missing_slots: list[str]
    engineering_fix_point: str | None
    clarification_questions: list[str]
    clarification_quality: str
    gap_type: str | None
    closure_reason: str


def _load_json(path: Path) -> Any:
    """读取 JSON 文件。

    参数：
        path: JSON 文件路径。

    返回：
        解析后的 JSON 对象。
    """

    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    """写出 JSON 文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _compact(text: str) -> str:
    """压缩问题文本，便于关键词识别。"""

    return re.sub(r"\s+", "", text or "")


def _contains_any(text: str, keywords: list[str]) -> bool:
    """判断文本是否包含任一关键词。"""

    return any(keyword in text for keyword in keywords)


def _load_current_b_items() -> list[dict[str, Any]]:
    """读取当前 903 总账中的 B=178 题。

    返回：
        当前状态为 B 的全部题。
    """

    payload = _load_json(LEDGER_PATH)
    return [item for item in payload["items"] if item.get("current_status") == "B"]


def _infer_missing_slots(question: str, final_bucket: str) -> list[str]:
    """按语义和题族推断缺失槽位。

    说明：
        这里不按 exact match 识别问题，而是根据时间、指标、主体、评价标准等业务槽位推断缺口；
        LLM 仍只能作为后续表达增强，最终 A/B/C 边界不在这里被改写。
    """

    compact = _compact(question)
    slots: list[str] = []
    if not re.search(r"(20\\d{2}|\\d{2})年|本月|今年|去年|近\\d+天|近\\d+个月|一季度|二季度|三季度|四季度|Q[1-4]", compact):
        slots.append("time_range")
    if _contains_any(compact, ["最近", "趋势", "变化", "变高", "变低"]):
        slots.extend(["time_range", "comparison_baseline"])
    if _contains_any(compact, ["多少", "怎么样", "哪些", "哪个"]) and not _contains_any(compact, ["运费", "费用", "发运量", "运量", "车次", "签收率", "状态", "填充率"]):
        slots.append("metric_definition")
    if _contains_any(compact, ["异常", "最差", "风险", "问题", "合理", "达标", "效率", "原因", "为什么"]):
        slots.extend(["business_definition", "evaluation_standard"])
    if _contains_any(compact, ["客户", "项目", "承运商", "区域", "省", "城市", "基地", "线路"]) and _contains_any(compact, ["排名", "最高", "最低", "最差", "前十"]):
        slots.extend(["ranking_metric", "sort_order", "top_n"])
    if _contains_any(compact, ["仓库", "allocate", "回单", "经纬度", "打卡", "合同", "字段", "空值"]):
        slots.append("data_scope")
    if _contains_any(compact, ["运输方式", "公路", "铁路", "车型", "17.5", "13米"]):
        slots.append("transport_scope")
    if final_bucket == "B-数据口径缺口池":
        slots.append("data_owner_confirmation")
    if final_bucket == "B-业务定义缺口池":
        slots.append("business_owner_confirmation")
    return sorted(set(slots)) or ["metric_definition"]


def _build_business_clarification_questions(question: str, missing_slots: list[str], final_bucket: str) -> list[str]:
    """生成业务化追问候选。

    参数：
        question: 原始问题。
        missing_slots: 缺失槽位列表。
        final_bucket: Wave5 分层结果。

    返回：
        面向业务用户的追问列表。
    """

    questions: list[str] = []
    if "time_range" in missing_slots:
        questions.append("请先确认统计时间范围，例如 2024 年全年、2025 年某个月、2026 年 1-2 月，或近 30 天。")
    if "metric_definition" in missing_slots:
        questions.append("请确认要看的指标口径，例如发运量 MW、总运费、车次、单瓦成本、签收率或任务数量。")
    if "comparison_baseline" in missing_slots:
        questions.append("请确认比较基准，例如环比、同比、与全年均值比较，还是只看 TopN 排名。")
    if "business_definition" in missing_slots or "evaluation_standard" in missing_slots:
        questions.append("请定义判断标准，例如什么算异常、风险、最差、达标或效率高低。")
    if "ranking_metric" in missing_slots:
        questions.append("请确认排名指标和排序方向，例如按总运费、发运量、车次、单瓦成本从高到低排序。")
    if "top_n" in missing_slots:
        questions.append("请确认输出数量，例如 Top5、Top10，还是输出全部并排序。")
    if "transport_scope" in missing_slots:
        questions.append("请确认运输方式或车型口径，例如公路/汽运是否合并、铁路/铁运是否合并，车型按 17.5 米还是 13 米统计。")
    if "data_scope" in missing_slots or "data_owner_confirmation" in missing_slots:
        questions.append("当前问题依赖未固化字段或数据覆盖范围，请先确认数据源是否已具备对应字段和统计口径。")
    if "business_owner_confirmation" in missing_slots:
        questions.append("该问题需要业务 owner 先确认口径后再回答，请确认定义、阈值、归因规则和输出粒度。")
    if not questions:
        questions.append("请补充时间范围、统计指标和输出维度后再查询。")
    if len(questions) < 2 and "metric_definition" in missing_slots:
        questions.append("如果题面里同时出现多个近似指标，请确认最终只看其中一个，还是需要分别输出并对比。")
    if len(questions) < 2 and "time_range" in missing_slots:
        questions.append("如果要看趋势或变化，请确认比较基准是环比、同比，还是与历史均值比较。")
    if final_bucket == "B-长期澄清边界池" and len(questions) < 2:
        questions.append("请说明是否需要按区域、省份、客户、承运商、运输方式或车型继续拆分。")
    return questions[:5]


def _build_followup_question(question: str, missing_slots: list[str]) -> str:
    """生成模拟用户补槽后的完整问题。

    返回：
        用于验证“补槽后续答闭环”的问题。
    """

    compact = _compact(question)
    if "运输方式为铁路" in compact and "2026年2月" in compact:
        return question
    if "最近物流成本" in compact:
        return "请按2025年各月总运费统计物流成本变化。"
    if _contains_any(compact, ["状态", "任务"]):
        return f"{question} 请限定为2026年正式系统数据，按 status 字段统计任务数量。"
    if _contains_any(compact, ["运费", "费用", "成本"]):
        return f"{question} 请限定为2025年全年，按总运费口径统计，只输出结构化汇总。"
    if _contains_any(compact, ["发运量", "运量", "MW"]):
        return f"{question} 请限定为2025年全年，按 MW 发运量口径统计，只输出结构化汇总。"
    if "车次" in compact:
        return f"{question} 请限定为2025年全年，按车次口径统计。"
    return f"{question} 请限定为2025年全年，并明确按可统计的汇总指标输出。"


def _classify_question(question: str, original_result: Any, followup_result: Any, followup_answerable: bool) -> tuple[str, str, str | None, str | None, str]:
    """对 B 题做 Wave5 最终分层。

    返回：
        (final_bucket, recommended_status, gap_type, engineering_fix_point, closure_reason)。
    """

    compact = _compact(question)
    original_status = original_result.status.code if original_result.status else "NO_STATUS"
    if original_status == LogisticsErrorCodeRegistry.UNSUPPORTED_QUESTION and original_result.query_plan.query_key:
        return (
            "B-数据口径缺口池",
            "B",
            "data_scope_gap",
            None,
            "真实链路已命中受控 query_key 但返回不支持，说明当前受数据基线、字段覆盖或已锁定业务时间口径约束，不能靠代码硬迁 A。",
        )
    if wave4._is_answerable(original_result) and not wave4._is_false_generic_answer(question, original_result.query_plan.query_key):
        return (
            "B-可工程化收口池",
            "A",
            None,
            "当前真实链路已稳定可答，仅需迁移复核和行为回归。",
            "原题真实链路已返回 OK 且结果非空，可作为 Wave5 B->A 迁移候选。",
        )
    if _contains_any(compact, ["预测", "预计", "未来", "ETA", "到货时间", "风险评分模型", "设计一个", "治理原则", "原因诊断"]):
        return (
            "B-应转 C 候选池",
            "C_REVIEW",
            "unsupported_boundary",
            None,
            "问题本质偏预测、ETA、开放分析、原因诊断或未建模归因，应复核是否转入 C 类拒答边界。",
        )
    if _contains_any(compact, ["仓库", "allocate", "回单", "经纬度", "打卡", "合同", "supplier_price", "字段", "空值", "缺失", "power字段"]):
        return (
            "B-数据口径缺口池",
            "B",
            "data_scope_gap",
            None,
            "依赖当前一期未固化字段、历史覆盖范围或系统数据源边界，不能靠代码硬迁 A。",
        )
    if _contains_any(compact, ["异常", "最差", "风险", "效率", "合理", "原因", "影响", "为什么", "划算", "趋势", "达标", "平均路程", "变化最大"]):
        return (
            "B-业务定义缺口池",
            "B",
            "business_definition_gap",
            None,
            "缺少异常、风险、好坏、原因、趋势或评价标准定义，必须业务确认后再决定是否迁 A。",
        )
    if followup_answerable:
        return (
            "B-补槽后可答池",
            "B",
            "followup_answerable_gap",
            "补齐时间、指标、维度或输出口径后可进入既有受控 query_key。",
            "用户补充关键槽位后可通过真实链路回答；原题仍需先澄清，不直接迁 A。",
        )
    if original_result.needs_clarification or original_status == LogisticsErrorCodeRegistry.CLARIFICATION_REQUIRED:
        return (
            "B-长期澄清池",
            "B",
            "clarification_boundary",
            None,
            "原题缺少关键槽位或业务口径，应保持业务化澄清边界。",
        )
    return (
        "B-可工程化收口池",
        "B",
        "query_key_gap",
        "需补 slot_extractor / planner / query_key / repository / service 后再复核。",
        "当前不是业务定义或数据口径缺口，但尚未稳定可答，保留为工程化缺口。",
    )


def _evaluate_records() -> list[Wave5BRecord]:
    """对当前 B=178 做真实链路复核、补槽闭环和追问质量评估。"""

    items = _load_current_b_items()
    db, service = wave4._build_service()
    records: list[Wave5BRecord] = []
    try:
        for item in items:
            original = service.query(LogisticsDataQaQueryRequest(question=item["question"]), trace_id="logistics-903-b-wave5-original")
            provisional_slots = _infer_missing_slots(item["question"], "B-长期澄清池")
            followup_question = _build_followup_question(item["question"], provisional_slots)
            followup = service.query(LogisticsDataQaQueryRequest(question=followup_question), trace_id="logistics-903-b-wave5-followup")
            followup_answerable = wave4._is_answerable(followup) and not wave4._is_false_generic_answer(item["question"], followup.query_plan.query_key)
            final_bucket, recommended_status, gap_type, engineering_fix_point, closure_reason = _classify_question(
                item["question"],
                original,
                followup,
                followup_answerable,
            )
            missing_slots = _infer_missing_slots(item["question"], final_bucket)
            clarification_questions = _build_business_clarification_questions(item["question"], missing_slots, final_bucket)
            if final_bucket in {"B-应转 C 候选池", "B-数据口径缺口池", "B-业务定义缺口池"}:
                clarification_quality = "business_confirmation_required"
            elif len(clarification_questions) >= 2 and not all("请补充明确的时间、指标和维度" in q for q in clarification_questions):
                clarification_quality = "acceptable"
            else:
                clarification_quality = "needs_optimization"
            records.append(
                Wave5BRecord(
                    question_id=item["question_id"],
                    question=item["question"],
                    source_group=item["source_group"],
                    family=item["family"],
                    governance_pool=item.get("governance_pool") or "",
                    original_status_code=original.status.code if original.status else "NO_STATUS",
                    original_query_key=original.query_plan.query_key,
                    original_row_count=len(original.result_table.rows),
                    followup_question=followup_question,
                    followup_status_code=followup.status.code if followup.status else "NO_STATUS",
                    followup_query_key=followup.query_plan.query_key,
                    followup_row_count=len(followup.result_table.rows),
                    followup_answerable=followup_answerable,
                    final_bucket=final_bucket,
                    recommended_status=recommended_status,
                    missing_slots=missing_slots,
                    engineering_fix_point=engineering_fix_point,
                    clarification_questions=clarification_questions,
                    clarification_quality=clarification_quality,
                    gap_type=gap_type,
                    closure_reason=closure_reason,
                )
            )
    finally:
        db.close()
    return records


def _build_payloads(records: list[Wave5BRecord]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """组装 Wave5 B 复核、追问质量、确认包和迁移配置。"""

    generated_at = datetime.now().isoformat(timespec="seconds")
    migration_records = [record for record in records if record.recommended_status == "A"]
    confirmation_records = [
        record
        for record in records
        if record.final_bucket in {"B-数据口径缺口池", "B-业务定义缺口池", "B-应转 C 候选池"}
    ]
    review_report = {
        "generated_at": generated_at,
        "source_ledger": str(LEDGER_PATH),
        "summary": {
            "total_b_questions": len(records),
            "migration_candidates": len(migration_records),
            "remain_b": sum(1 for record in records if record.recommended_status == "B"),
            "c_review_candidates": sum(1 for record in records if record.recommended_status == "C_REVIEW"),
            "final_bucket_breakdown": dict(Counter(record.final_bucket for record in records)),
            "gap_type_breakdown": dict(Counter(record.gap_type or "none" for record in records)),
            "original_status_code_breakdown": dict(Counter(record.original_status_code for record in records)),
            "followup_status_code_breakdown": dict(Counter(record.followup_status_code for record in records)),
            "followup_answerable": sum(1 for record in records if record.followup_answerable),
        },
        "items": [asdict(record) for record in records],
    }
    clarification_report = {
        "generated_at": generated_at,
        "source_review_report": str(REVIEW_REPORT_PATH),
        "summary": {
            "total_b_questions": len(records),
            "acceptable_clarification": sum(1 for record in records if record.clarification_quality == "acceptable"),
            "needs_optimization": sum(1 for record in records if record.clarification_quality == "needs_optimization"),
            "business_confirmation_required": sum(1 for record in records if record.clarification_quality == "business_confirmation_required"),
            "missing_slot_breakdown": dict(Counter(slot for record in records for slot in record.missing_slots)),
            "quality_breakdown": dict(Counter(record.clarification_quality for record in records)),
        },
        "items": [
            {
                "question_id": record.question_id,
                "question": record.question,
                "final_bucket": record.final_bucket,
                "missing_slots": record.missing_slots,
                "clarification_questions": record.clarification_questions,
                "clarification_quality": record.clarification_quality,
            }
            for record in records
        ],
    }
    confirmation_items = [
        {
            "question_id": record.question_id,
            "question": record.question,
            "current_classification": "B",
            "wave5_bucket": record.final_bucket,
            "why_not_answerable": record.closure_reason,
            "missing_data_fields": "缺字段、缺历史覆盖、缺系统侧稳定字段或一期数据源不支持。" if record.final_bucket == "B-数据口径缺口池" else "",
            "missing_business_definition": "缺异常、风险、原因、趋势、评价标准或排序口径定义。" if record.final_bucket == "B-业务定义缺口池" else "",
            "business_confirmation_needed": "请确认数据字段/业务定义/拒答边界后，再决定继续保留 B、补数据迁 A、补 query_key 迁 A 或转 C。",
            "after_confirmation_paths": [
                "继续保留 B 并追问",
                "补数据后迁 A",
                "明确无数据支撑后转 C",
                "新增受控 query_key 后迁 A",
            ],
            "suggested_query_key_or_data_work": record.followup_query_key or record.original_query_key or "待业务确认后设计受控 query_key 或数据补齐方案",
        }
        for record in confirmation_records
    ]
    confirmation_package = {
        "generated_at": generated_at,
        "source_review_report": str(REVIEW_REPORT_PATH),
        "summary": {
            "total_confirmation_items": len(confirmation_items),
            "bucket_breakdown": dict(Counter(item["wave5_bucket"] for item in confirmation_items)),
        },
        "items": confirmation_items,
    }
    shortlist = {
        "generated_at": generated_at,
        "source_package": str(CONFIRMATION_PACKAGE_PATH),
        "summary": {
            "total_shortlist_items": min(60, len(confirmation_items)),
            "selection_rule": "优先输出 Wave5 中数据口径、业务定义和疑似 C 边界确认项，便于业务侧集中确认。",
        },
        "items": [
            {
                "question_id": item["question_id"],
                "question": item["question"],
                "wave5_bucket": item["wave5_bucket"],
                "business_confirmation_needed": item["business_confirmation_needed"],
            }
            for item in confirmation_items[:60]
        ],
    }
    migration_config = {
        "generated_at": generated_at,
        "source_review_report": str(REVIEW_REPORT_PATH),
        "migration_rule": "只有原题真实 data-qa 主链路稳定 OK、非澄清、非拒答、结果非空，且不是通用 query_key 误吸收，才允许进入 Wave5 B->A 迁移候选。",
        "items": [
            {
                "migration_id": f"B-GAP-W5-{index:03d}",
                "question_id": record.question_id,
                "question": record.question,
                "source_group": record.source_group,
                "family": record.family,
                "query_key": record.original_query_key,
                "recommended_status": "A",
                "migration_reason": record.closure_reason,
            }
            for index, record in enumerate(migration_records, start=1)
        ],
    }
    return review_report, clarification_report, confirmation_package, shortlist, migration_config


def _render_review_doc(report: dict[str, Any]) -> str:
    """渲染 Wave5 B 最终可执行性复核文档。"""

    summary = report["summary"]
    lines = [
        "# 903 剩余 B Wave5 最终可执行性复核",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、复核结论",
        "",
        f"- 当前 B 题总数：`{summary['total_b_questions']}`",
        f"- B->A 可迁移候选：`{summary['migration_candidates']}`",
        f"- 继续留 B：`{summary['remain_b']}`",
        f"- 应转 C 复核候选：`{summary['c_review_candidates']}`",
        f"- 补槽后真实可答：`{summary['followup_answerable']}`",
        f"- Wave5 分层：`{summary['final_bucket_breakdown']}`",
        f"- 缺口类型：`{summary['gap_type_breakdown']}`",
        "",
        "## 二、执行原则",
        "",
        "- 只允许真实 data-qa 主链路稳定可答的题迁入 A。",
        "- 数据口径缺口和业务定义缺口继续保留 B 或进入业务确认，不硬迁 A。",
        "- LLM 只允许作为追问表达增强，不允许查数、生成 SQL 或改写 A/B/C 边界。",
        "",
    ]
    return "\n".join(lines) + "\n"


def _render_clarification_doc(report: dict[str, Any]) -> str:
    """渲染 Wave5 B 追问质量报告。"""

    summary = report["summary"]
    lines = [
        "# 903 剩余 B Wave5 追问质量复检",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、追问质量统计",
        "",
        f"- B 题总数：`{summary['total_b_questions']}`",
        f"- 可接受业务化追问：`{summary['acceptable_clarification']}`",
        f"- 需要优化追问：`{summary['needs_optimization']}`",
        f"- 需业务/数据确认后再追问：`{summary['business_confirmation_required']}`",
        f"- 缺失槽位分布：`{summary['missing_slot_breakdown']}`",
        "",
        "## 二、追问生成原则",
        "",
        "- 追问基于缺失槽位和业务口径生成，不按题号 exact match。",
        "- 对缺数据或缺业务定义的题，优先给业务确认问题，而不是伪装成可答。",
        "- LLM 后续只能改写追问表达，不能改变最终 B/C 裁决。",
        "",
    ]
    return "\n".join(lines) + "\n"


def _render_confirmation_doc(package: dict[str, Any], title: str) -> str:
    """渲染业务确认包文档。"""

    summary = package["summary"]
    lines = [
        f"# {title}",
        "",
        f"生成时间：{package['generated_at']}",
        "",
        "## 一、确认范围",
        "",
        f"- 确认项总数：`{summary.get('total_confirmation_items', summary.get('total_shortlist_items', 0))}`",
        f"- 分布：`{summary.get('bucket_breakdown', {})}`",
        "",
        "## 二、确认清单",
        "",
        "| 题号 | 分层 | 需要确认的问题 | 原题 |",
        "| --- | --- | --- | --- |",
    ]
    for item in package["items"]:
        lines.append(
            f"| {item['question_id']} | {item.get('wave5_bucket', '')} | {item['business_confirmation_needed']} | {item['question']} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    """命令行入口：执行 Wave5 B=178 最终复核、追问质量评估和业务确认包生成。"""

    records = _evaluate_records()
    review_report, clarification_report, confirmation_package, shortlist, migration_config = _build_payloads(records)
    a_regression_set = {
        "generated_at": review_report["generated_at"],
        "source_migration_config": str(MIGRATION_CONFIG_PATH),
        "summary": {
            "total_questions": len(migration_config["items"]),
            "expected_status_code": LogisticsErrorCodeRegistry.OK,
        },
        "items": [
            {
                "question_id": item["question_id"],
                "question": item["question"],
                "source_group": item["source_group"],
                "family": item["family"],
                "expected_query_key": item["query_key"],
                "expected_status_code": LogisticsErrorCodeRegistry.OK,
            }
            for item in migration_config["items"]
        ],
    }
    _write_json(REVIEW_REPORT_PATH, review_report)
    _write_json(CLARIFICATION_REPORT_PATH, clarification_report)
    _write_json(CONFIRMATION_PACKAGE_PATH, confirmation_package)
    _write_json(CONFIRMATION_SHORTLIST_PATH, shortlist)
    _write_json(MIGRATION_CONFIG_PATH, migration_config)
    _write_json(A_REGRESSION_QUESTION_SET_PATH, a_regression_set)
    REVIEW_DOC_PATH.write_text(_render_review_doc(review_report), encoding="utf-8")
    CLARIFICATION_DOC_PATH.write_text(_render_clarification_doc(clarification_report), encoding="utf-8")
    CONFIRMATION_DOC_PATH.write_text(_render_confirmation_doc(confirmation_package, "903 剩余 B Wave5 业务确认交付包 v2"), encoding="utf-8")
    CONFIRMATION_SHORTLIST_DOC_PATH.write_text(_render_confirmation_doc(shortlist, "903 剩余 B Wave5 业务确认简洁清单 v2"), encoding="utf-8")
    print(json.dumps(review_report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
