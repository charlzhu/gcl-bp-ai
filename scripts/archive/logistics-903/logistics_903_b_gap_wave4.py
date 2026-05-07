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

from backend.app.db.session import SessionLocal
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.domains.logistics.services.error_code_registry import LogisticsErrorCodeRegistry
from backend.app.domains.logistics.services.llm_clarification_assist_service import (
    LogisticsLlmClarificationAssistService,
)
from backend.app.domains.logistics.services.llm_unsupported_assist_service import (
    LogisticsLlmUnsupportedAssistService,
)
from backend.app.domains.logistics.services.llm_understanding_guardrail_service import (
    LogisticsLlmUnderstandingGuardrailService,
)


LEDGER_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
WAVE4_CLASSIFICATION_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave4_final_classification_report.json"
WAVE4_GAP_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_gap_wave4_report.json"
WAVE4_FOLLOWUP_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave4_followup_closure_report.json"
WAVE4_CONFIRMATION_PACKAGE_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave4_business_confirmation_package.json"
WAVE4_CONFIRMATION_SHORTLIST_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave4_business_confirmation_shortlist.json"
MIGRATION_CONFIG_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b_gap_wave4_migration_candidates.json"
A_REGRESSION_QUESTION_SET_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b_gap_wave4_a_regression_questions.json"

WAVE4_CLASSIFICATION_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_WAVE4_FINAL_CLASSIFICATION.md"
WAVE4_GAP_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_GAP_WAVE4.md"
WAVE4_FOLLOWUP_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_WAVE4_FOLLOWUP_CLOSURE.md"
WAVE4_CONFIRMATION_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_WAVE4_BUSINESS_CONFIRMATION_PACKAGE.md"
WAVE4_CONFIRMATION_SHORTLIST_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_WAVE4_BUSINESS_CONFIRMATION_SHORTLIST.md"


class NoopQueryLogRepository:
    """无副作用查询日志仓储。

    说明：
        Wave4 会批量调用真实 data-qa 主链路，但治理脚本不应污染正式用户查询日志。
    """

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        """忽略查询日志写入请求。

        参数：
            db: 数据库会话。
            payload: 查询日志内容。

        返回：
            固定返回 0，表示没有写入正式日志。
        """

        _ = db, payload
        return 0


@dataclass
class Wave4Record:
    """Wave4 B 题最终分层与真实链路复核记录。

    参数：
        question_id: 题号。
        question: 原始问题。
        source_group: 来源分组。
        family: 题族。
        current_pool: 复核前治理池。
        actual_query_key: 当前真实链路命中的 query_key。
        status_code: 当前真实链路状态码。
        supported: 是否支持。
        needs_clarification: 是否需要澄清。
        row_count: 结果行数。
        final_bucket: Wave4 六类分层结果。
        recommended_status: 推荐状态。
        gap_type: 未迁移时的缺口类型。
        capability_id: Wave4 能力项编号。
        closure_reason: 迁移或保留原因。
        answer_summary: 当前返回摘要。
    """

    question_id: str
    question: str
    source_group: str
    family: str
    current_pool: str
    actual_query_key: str | None
    status_code: str
    supported: bool
    needs_clarification: bool
    row_count: int
    final_bucket: str
    recommended_status: str
    gap_type: str | None
    capability_id: str | None
    closure_reason: str
    answer_summary: str


@dataclass
class FollowupRecord:
    """Wave4 B 类补槽后续答闭环记录。

    参数：
        question_id: 题号。
        question: 原始问题。
        followup_question: 模拟用户补槽后的问题。
        actual_query_key: 补槽后命中的 query_key。
        status_code: 补槽后状态码。
        row_count: 补槽后结果行数。
        passed: 是否补槽后可稳定回答。
        gap_type: 未闭环缺口类型。
        closure_reason: 归因说明。
    """

    question_id: str
    question: str
    followup_question: str
    actual_query_key: str | None
    status_code: str
    row_count: int
    passed: bool
    gap_type: str | None
    closure_reason: str


def _load_json(path: Path) -> Any:
    """读取 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    """写出 JSON 文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _compact(text: str) -> str:
    """压缩问题文本中的空白。"""

    return re.sub(r"\s+", "", text or "")


def _contains_any(text: str, keywords: list[str]) -> bool:
    """判断文本是否包含任一关键词。"""

    return any(keyword in text for keyword in keywords)


def _load_current_b_items() -> list[dict[str, Any]]:
    """读取当前 903 总账中的 B 类题。

    返回：
        当前状态为 B 的全部题目。
    """

    payload = _load_json(LEDGER_PATH)
    return [item for item in payload["items"] if item.get("current_status") == "B"]


def _load_wave4_review_items() -> list[dict[str, Any]]:
    """读取 Wave4 固定复核题源。

    返回：
        当前 B 类题 + 已生成的 Wave4 迁移候选固定源。

    说明：
        Wave4 首次执行后会把若干 B 题迁入 A；如果脚本再次执行，只读取当前 B
        会丢失已迁移题并覆盖迁移配置，导致总账重建回滚。因此这里把既有 Wave4
        迁移配置作为固定复核源纳入，保证脚本可重复执行。
    """

    payload = _load_json(LEDGER_PATH)
    ledger_index = {
        (item["question_id"], item["question"]): item
        for item in payload["items"]
    }
    review_items = [dict(item) for item in payload["items"] if item.get("current_status") == "B"]
    seen = {(item["question_id"], item["question"]) for item in review_items}
    if not MIGRATION_CONFIG_PATH.exists():
        return review_items
    for migration_item in _load_json(MIGRATION_CONFIG_PATH).get("items", []):
        key = (migration_item["question_id"], migration_item["question"])
        if key in seen or key not in ledger_index:
            continue
        ledger_item = dict(ledger_index[key])
        ledger_item["governance_pool"] = ledger_item.get("governance_pool") or "Wave4迁移复核固定源"
        review_items.append(ledger_item)
        seen.add(key)
    return review_items


def _build_service() -> tuple[Any, LogisticsDataQaService]:
    """构造真实 data-qa 服务，并关闭 LLM 对正式裁决的影响。

    返回：
        数据库会话与服务实例。
    """

    db = SessionLocal()
    service = LogisticsDataQaService(
        db=db,
        query_log_repository=NoopQueryLogRepository(),
        guardrail_service=LogisticsLlmUnderstandingGuardrailService(
            enabled=False,
            mode="off",
            sample_rate=0.0,
            audit_enabled=False,
        ),
        clarification_assist_service=LogisticsLlmClarificationAssistService(
            enabled=False,
            mode="off",
            sample_rate=0.0,
            audit_enabled=False,
        ),
        unsupported_assist_service=LogisticsLlmUnsupportedAssistService(
            enabled=False,
            mode="off",
            sample_rate=0.0,
            audit_enabled=False,
        ),
    )
    return db, service


def _is_answerable(result: Any) -> bool:
    """判断真实链路是否稳定进入 A 类可答状态。

    返回：
        True 表示 OK、supported=true、非澄清、非拒答、有 query_key 且结果非空。
    """

    status_code = result.status.code if result.status else "NO_STATUS"
    return (
        status_code == LogisticsErrorCodeRegistry.OK
        and bool(result.supported)
        and not bool(result.needs_clarification)
        and bool(result.query_plan.query_key)
        and len(result.result_table.rows) > 0
    )


def _is_false_generic_answer(question: str, query_key: str | None) -> bool:
    """识别不应因通用汇总 query_key 命中而迁 A 的问题。

    参数：
        question: 原始问题。
        query_key: 实际命中的 query_key。

    返回：
        True 表示该命中是开放诊断、原因解释或口径讨论题的误吸收。
    """

    compact = _compact(question)
    diagnostic_keywords = [
        "原因",
        "影响",
        "是否值得",
        "如何",
        "应如何",
        "冲突",
        "异常",
        "绑定",
        "打卡",
        "经纬度",
        "字段",
        "不一致",
        "为什么",
        "推广",
        "划算",
        "口径",
    ]
    return query_key == "hist_mw_summary" and _contains_any(compact, diagnostic_keywords)


def _capability_id_for_item(query_key: str | None, question: str) -> str | None:
    """把 query_key 和题面映射到 Wave4 能力项。"""

    compact = _compact(question)
    if query_key == "hist_total_fee_summary" and "客户" in compact:
        return "B-GAP-W4-001"
    return None


def _classify_non_answerable(question: str, result: Any) -> tuple[str, str, str]:
    """对未迁移 B 题做 Wave4 六类分层。

    返回：
        (gap_type, final_bucket, closure_reason)。
    """

    compact = _compact(question)
    status_code = result.status.code if result.status else "NO_STATUS"
    if status_code == LogisticsErrorCodeRegistry.EMPTY_RESULT:
        return "data_scope_gap", "B-数据口径缺口池", "当前 query_key 已命中但结果为空，需要确认数据覆盖范围或零值回答口径。"
    if result.query_plan.intent == "unsupported" or status_code == LogisticsErrorCodeRegistry.UNSUPPORTED_QUESTION:
        if _contains_any(compact, ["预测", "预计", "风险", "模型", "推广", "如何", "应如何", "影响"]):
            return "unsupported_boundary", "B-疑似应转 C 池", "问题本质偏预测、开放分析或治理建议，需评估转入 C 类不支持边界。"
        return "data_scope_gap", "B-数据口径缺口池", "真实链路已拒答，当前主要受数据范围或一期字段边界约束。"
    if _contains_any(compact, ["仓库", "allocate", "warehouse", "合同", "单据", "回单", "经纬度", "打卡", "字段", "空值"]):
        return "data_scope_gap", "B-数据口径缺口池", "依赖一期未固化字段、映射关系或数据覆盖范围，需数据侧确认后再迁移。"
    if _contains_any(compact, ["异常", "最差", "风险", "效率", "合理", "原因", "影响", "为什么", "划算", "推广", "达标率", "平均路程"]):
        return "business_definition_gap", "B-业务定义缺口池", "缺少异常、好坏、原因、效率或收益判断口径，必须业务确认。"
    if _contains_any(compact, ["车辆数", "车数"]) and _contains_any(compact, ["车次", "车辆数"]):
        return "business_definition_gap", "B-业务定义缺口池", "题面同时出现车次/车辆数，需要先确认是按车次还是去重车辆统计。"
    if _contains_any(compact, ["最近", "近期", "当前", "哪些", "哪个", "多少", "分别", "各"]):
        return "followup_answerable_gap", "B-补槽后可答池", "题面存在可补槽空间，需用户补充时间、指标、维度或输出口径后再进入受控查询。"
    if result.needs_clarification:
        return "clarification_boundary", "B-长期澄清边界池", "真实链路仍要求补充关键槽位，本轮保持业务化澄清。"
    return "query_key_gap", "B-可工程化收口池", "当前未稳定可答但缺口偏工程化解析或 query_key 能力，后续可继续按题族收口。"


def _build_followup_question(item: dict[str, Any], record: Wave4Record) -> str:
    """为仍为 B 的问题生成合理补槽输入。

    参数：
        item: 总账题目。
        record: Wave4 复核记录。

    返回：
        用于验证补槽后续答闭环的模拟追问后完整问题。
    """

    question = item["question"]
    compact = _compact(question)
    if record.final_bucket == "B-补槽后可答池" and "最近物流成本" in compact:
        return "请按2025年各月总运费看物流成本变化趋势。"
    if record.final_bucket == "B-补槽后可答池" and "各任务状态" in compact:
        return "请按2026年主任务表 ship_task 的 status 字段统计各任务状态数量。"
    if "总运费" in compact and "客户" in compact:
        return question
    if "总发运量" in compact or "发运量" in compact or "运量" in compact:
        return f"{question} 请按2025年全年、MW口径、只输出汇总结果。"
    if "运费" in compact or "费用" in compact or "成本" in compact:
        return f"{question} 请按2025年全年、总运费口径、只输出汇总结果。"
    if "车次" in compact:
        return f"{question} 请按2025年全年、shipment_trip_count 车次口径统计。"
    return f"{question} 请限定为2025年全年，只输出可统计的汇总指标。"


def _evaluate_b_items() -> list[Wave4Record]:
    """对当前 B=182 做真实链路复核与最终分层。"""

    items = _load_wave4_review_items()
    db, service = _build_service()
    records: list[Wave4Record] = []
    try:
        for item in items:
            result = service.query(
                LogisticsDataQaQueryRequest(question=item["question"]),
                trace_id="logistics-903-b-gap-wave4",
            )
            status_code = result.status.code if result.status else "NO_STATUS"
            query_key = result.query_plan.query_key
            row_count = len(result.result_table.rows)
            if _is_answerable(result) and not _is_false_generic_answer(item["question"], query_key):
                final_bucket = "B-可工程化收口池"
                recommended_status = "A"
                gap_type = None
                capability_id = _capability_id_for_item(query_key, item["question"])
                closure_reason = "真实 data-qa 主链路返回 OK、supported=true、非澄清、非拒答、结果非空，可进入 Wave4 B->A 迁移复核。"
                if capability_id:
                    closure_reason += f" 对应能力项：{capability_id}。"
            else:
                gap_type, final_bucket, closure_reason = _classify_non_answerable(item["question"], result)
                recommended_status = "B"
                capability_id = _capability_id_for_item(query_key, item["question"])
            records.append(
                Wave4Record(
                    question_id=item["question_id"],
                    question=item["question"],
                    source_group=item["source_group"],
                    family=item["family"],
                    current_pool=item.get("governance_pool") or "",
                    actual_query_key=query_key,
                    status_code=status_code,
                    supported=bool(result.supported),
                    needs_clarification=bool(result.needs_clarification),
                    row_count=row_count,
                    final_bucket=final_bucket,
                    recommended_status=recommended_status,
                    gap_type=gap_type,
                    capability_id=capability_id,
                    closure_reason=closure_reason,
                    answer_summary=result.answer_summary,
                )
            )
    finally:
        db.close()
    return records


def _evaluate_followups(records: list[Wave4Record]) -> dict[str, Any]:
    """对仍为 B 的题执行补槽后续答闭环增强。"""

    ledger_index = {
        (item["question_id"], item["question"]): item
        for item in _load_current_b_items()
    }
    remain_records = [record for record in records if record.recommended_status != "A"]
    db, service = _build_service()
    followups: list[FollowupRecord] = []
    try:
        for record in remain_records:
            item = ledger_index[(record.question_id, record.question)]
            followup_question = _build_followup_question(item, record)
            result = service.query(
                LogisticsDataQaQueryRequest(question=followup_question),
                trace_id="logistics-903-b-wave4-followup-closure",
            )
            status_code = result.status.code if result.status else "NO_STATUS"
            query_key = result.query_plan.query_key
            row_count = len(result.result_table.rows)
            passed = _is_answerable(result) and not _is_false_generic_answer(record.question, query_key)
            if passed:
                gap_type = None
                closure_reason = "用户补充关键槽位后可进入受控 query_key；原题仍需先澄清，不直接迁 A。"
            else:
                gap_type, _bucket, closure_reason = _classify_non_answerable(record.question, result)
                if _is_false_generic_answer(record.question, query_key):
                    gap_type = "business_definition_gap"
                    closure_reason = "补槽后虽命中通用汇总 query_key，但原题要求原因、影响、字段一致性或业务建议，不能作为真实闭环。"
            followups.append(
                FollowupRecord(
                    question_id=record.question_id,
                    question=record.question,
                    followup_question=followup_question,
                    actual_query_key=query_key,
                    status_code=status_code,
                    row_count=row_count,
                    passed=passed,
                    gap_type=gap_type,
                    closure_reason=closure_reason,
                )
            )
    finally:
        db.close()
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_classification_report": str(WAVE4_CLASSIFICATION_REPORT_PATH),
        "summary": {
            "total_remain_b_questions": len(followups),
            "closed_after_followup": sum(1 for item in followups if item.passed),
            "still_not_closed": sum(1 for item in followups if not item.passed),
            "gap_type_breakdown": dict(Counter(item.gap_type or "none" for item in followups)),
            "query_key_breakdown": dict(Counter(item.actual_query_key or "NONE" for item in followups)),
        },
        "items": [asdict(item) for item in followups],
    }


def _build_confirmation_package(records: list[Wave4Record], followup_report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """生成数据口径与业务定义确认包。

    参数：
        records: Wave4 复核记录。
        followup_report: 补槽闭环报告。

    返回：
        完整确认包与简洁版确认清单。
    """

    followup_by_key = {
        (item["question_id"], item["question"]): item
        for item in followup_report["items"]
    }
    confirmation_items: list[dict[str, Any]] = []
    for record in records:
        if record.recommended_status == "A":
            continue
        if record.final_bucket not in {"B-数据口径缺口池", "B-业务定义缺口池", "B-疑似应转 C 池"}:
            continue
        followup_item = followup_by_key.get((record.question_id, record.question), {})
        if record.final_bucket == "B-数据口径缺口池":
            missing_data = "当前数据源字段、历史覆盖范围、allocate/仓库/回单/打卡等一期边界尚未固化。"
            missing_definition = ""
            confirm_question = "请确认是否补齐相关字段或明确当前阶段不纳入物流一期结构化查询。"
        elif record.final_bucket == "B-业务定义缺口池":
            missing_data = ""
            missing_definition = "缺少异常、达标、效率、好坏、原因、去重车辆数或成本口径定义。"
            confirm_question = "请确认指标定义、评价标准、阈值、排序方式和输出粒度。"
        else:
            missing_data = "当前结构化数据无法支撑预测、原因诊断或开放治理建议。"
            missing_definition = "需要确认是否转入 C 类不支持边界，或先新增独立业务模型和数据。"
            confirm_question = "请确认该题是否继续保留 B 类澄清，还是转入 C 类明确不支持。"
        confirmation_items.append(
            {
                "question_id": record.question_id,
                "question": record.question,
                "family": record.family,
                "bucket": record.final_bucket,
                "gap_type": record.gap_type,
                "why_not_answerable": record.closure_reason,
                "missing_data_fields": missing_data,
                "missing_business_definition": missing_definition,
                "business_confirmation_needed": confirm_question,
                "migration_path_after_confirmation": "业务确认并补齐数据/口径后，先进入 B->A 迁移复核，再建立行为回归和精确断言。",
                "suggested_query_key_or_data_work": record.actual_query_key or followup_item.get("actual_query_key") or "待业务确认后设计受控 query_key",
            }
        )
    package = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_classification_report": str(WAVE4_CLASSIFICATION_REPORT_PATH),
        "summary": {
            "total_confirmation_items": len(confirmation_items),
            "bucket_breakdown": dict(Counter(item["bucket"] for item in confirmation_items)),
            "gap_type_breakdown": dict(Counter(item["gap_type"] or "none" for item in confirmation_items)),
        },
        "items": confirmation_items,
    }
    shortlist_items = confirmation_items[:50]
    shortlist = {
        "generated_at": package["generated_at"],
        "source_package": str(WAVE4_CONFIRMATION_PACKAGE_PATH),
        "summary": {
            "total_shortlist_items": len(shortlist_items),
            "selection_rule": "优先输出前 50 条数据口径、业务定义和疑似 C 边界确认项，便于业务侧先处理高频样例。",
        },
        "items": [
            {
                "question_id": item["question_id"],
                "question": item["question"],
                "bucket": item["bucket"],
                "business_confirmation_needed": item["business_confirmation_needed"],
            }
            for item in shortlist_items
        ],
    }
    return package, shortlist


def _build_reports(records: list[Wave4Record], followup_report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """组装 Wave4 结构化报告、迁移配置和 A 行为回归题集。"""

    generated_at = datetime.now().isoformat(timespec="seconds")
    migration_records = [record for record in records if record.recommended_status == "A"]
    remain_records = [record for record in records if record.recommended_status != "A"]
    classification_report = {
        "generated_at": generated_at,
        "source_ledger": str(LEDGER_PATH),
        "summary": {
            "total_b_questions": len(records),
            "recommended_a": len(migration_records),
            "remain_b": len(remain_records),
            "final_bucket_breakdown": dict(Counter(record.final_bucket for record in records)),
            "gap_type_breakdown": dict(Counter(record.gap_type or "none" for record in records)),
            "status_code_breakdown": dict(Counter(record.status_code for record in records)),
            "query_key_breakdown": dict(Counter(record.actual_query_key or "NONE" for record in records)),
        },
        "items": [asdict(record) for record in records],
    }
    wave4_report = {
        "generated_at": generated_at,
        "source_classification_report": str(WAVE4_CLASSIFICATION_REPORT_PATH),
        "summary": {
            "reviewed_questions": len(records),
            "migrated_to_a_total": len(migration_records),
            "remain_b_total": len(remain_records),
            "handled_capability_items": dict(Counter(record.capability_id for record in migration_records if record.capability_id)),
            "policy": "只有真实 data-qa 主链路返回 OK、supported=true、非澄清、非拒答且结果非空的题，才允许作为 Wave4 B->A 迁移候选。",
        },
        "migration_items": [asdict(record) for record in migration_records],
        "remain_b_items": [asdict(record) for record in remain_records],
        "followup_summary": followup_report["summary"],
    }
    migration_config = {
        "generated_at": generated_at,
        "source_report": str(WAVE4_GAP_REPORT_PATH),
        "migration_rule": "Wave4 真实 data-qa 主链路返回 OK、supported=true、非澄清、非拒答、结果非空，且不是通用 query_key 误吸收开放诊断题。",
        "items": [
            {
                "migration_id": f"B-GAP-W4-{index:03d}",
                "question_id": record.question_id,
                "question": record.question,
                "source": "B-gap Wave4 final classification migration review",
                "source_group": record.source_group,
                "family": record.family,
                "capability_id": record.capability_id,
                "query_key": record.actual_query_key,
                "recommended_status": "A",
                "migration_reason": record.closure_reason,
            }
            for index, record in enumerate(migration_records, start=1)
        ],
    }
    a_regression_set = {
        "generated_at": generated_at,
        "source_migration_config": str(MIGRATION_CONFIG_PATH),
        "summary": {
            "total_questions": len(migration_records),
            "expected_status_code": LogisticsErrorCodeRegistry.OK,
        },
        "items": [
            {
                "question_id": record.question_id,
                "question": record.question,
                "source_group": record.source_group,
                "family": record.family,
                "expected_query_key": record.actual_query_key,
                "expected_status_code": LogisticsErrorCodeRegistry.OK,
            }
            for record in migration_records
        ],
    }
    return classification_report, wave4_report, migration_config, a_regression_set


def _render_simple_doc(title: str, report: dict[str, Any], *, sample_key: str = "items") -> str:
    """渲染通用 Markdown 报告。"""

    lines = [
        f"# {title}",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、汇总",
        "",
    ]
    for key, value in report.get("summary", {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## 二、代表样例", ""])
    for item in report.get(sample_key, [])[:30]:
        lines.append(f"- {item.get('question_id')} | {item.get('final_bucket') or item.get('bucket') or item.get('gap_type')} | {item.get('question')}")
    return "\n".join(lines) + "\n"


def main() -> None:
    """命令行入口：执行 Wave4 B=182 最终分层、补槽闭环和迁移配置生成。"""

    records = _evaluate_b_items()
    followup_report = _evaluate_followups(records)
    classification_report, wave4_report, migration_config, a_regression_set = _build_reports(records, followup_report)
    confirmation_package, confirmation_shortlist = _build_confirmation_package(records, followup_report)

    _write_json(WAVE4_CLASSIFICATION_REPORT_PATH, classification_report)
    _write_json(WAVE4_GAP_REPORT_PATH, wave4_report)
    _write_json(WAVE4_FOLLOWUP_REPORT_PATH, followup_report)
    _write_json(WAVE4_CONFIRMATION_PACKAGE_PATH, confirmation_package)
    _write_json(WAVE4_CONFIRMATION_SHORTLIST_PATH, confirmation_shortlist)
    _write_json(MIGRATION_CONFIG_PATH, migration_config)
    _write_json(A_REGRESSION_QUESTION_SET_PATH, a_regression_set)

    WAVE4_CLASSIFICATION_DOC_PATH.write_text(
        _render_simple_doc("903 B 类 Wave4 最终分层复核", classification_report),
        encoding="utf-8",
    )
    WAVE4_GAP_DOC_PATH.write_text(
        _render_simple_doc("903 B-gap Wave4 可工程化收口报告", wave4_report, sample_key="migration_items"),
        encoding="utf-8",
    )
    WAVE4_FOLLOWUP_DOC_PATH.write_text(
        _render_simple_doc("903 B 类 Wave4 补槽后续答闭环", followup_report),
        encoding="utf-8",
    )
    WAVE4_CONFIRMATION_DOC_PATH.write_text(
        _render_simple_doc("903 B 类 Wave4 业务确认包", confirmation_package),
        encoding="utf-8",
    )
    WAVE4_CONFIRMATION_SHORTLIST_DOC_PATH.write_text(
        _render_simple_doc("903 B 类 Wave4 简洁版业务确认清单", confirmation_shortlist),
        encoding="utf-8",
    )
    print(json.dumps(classification_report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
