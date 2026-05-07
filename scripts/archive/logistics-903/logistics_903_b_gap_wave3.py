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
ROADMAP_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_gap_capability_roadmap.json"
WAVE2_FOLLOWUP_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_followup_closure_report.json"

SECONDARY_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave3_secondary_review_report.json"
WAVE3_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_gap_wave3_report.json"
FOLLOWUP_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave3_followup_closure_regression_report.json"
UNCLOSED_ATTRIBUTION_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave3_unclosed_24_attribution_report.json"
BUSINESS_CONFIRMATION_MATRIX_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave3_business_confirmation_matrix.json"

MIGRATION_CONFIG_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b_gap_wave3_migration_candidates.json"
A_REGRESSION_QUESTION_SET_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b_gap_wave3_a_regression_questions.json"

SECONDARY_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_WAVE3_SECONDARY_REVIEW.md"
WAVE3_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_GAP_WAVE3.md"
FOLLOWUP_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_WAVE3_FOLLOWUP_CLOSURE_REGRESSION.md"
UNCLOSED_ATTRIBUTION_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_WAVE3_UNCLOSED_ATTRIBUTION.md"
BUSINESS_CONFIRMATION_MATRIX_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_WAVE3_BUSINESS_CONFIRMATION_MATRIX.md"


class NoopQueryLogRepository:
    """无副作用查询日志仓储。

    说明：
        Wave3 会批量调用真实 data-qa 主链路，但回归脚本不应污染正式用户查询日志。
    """

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        """忽略查询日志写入请求。"""

        _ = db, payload
        return 0


@dataclass
class Wave3ReviewRecord:
    """Wave3 B 类真实链路复核记录。

    参数：
        question_id: 题号。
        question: 原始问题。
        source_group: 题目来源分组。
        family: 题族。
        governance_pool_before: 复核前治理池。
        actual_query_key: 真实链路命中的 query_key。
        status_code: 真实链路状态码。
        supported: 是否 supported。
        needs_clarification: 是否仍需澄清。
        row_count: 结果行数。
        recommended_status: Wave3 推荐状态。
        gap_type: 未迁移时的缺口类型。
        capability_id: 对应能力项。
        closure_reason: 迁移或保留原因。
        answer_summary: 真实链路摘要。
    """

    question_id: str
    question: str
    source_group: str
    family: str
    governance_pool_before: str
    actual_query_key: str | None
    status_code: str
    supported: bool
    needs_clarification: bool
    row_count: int
    recommended_status: str
    gap_type: str | None
    capability_id: str | None
    closure_reason: str
    answer_summary: str


@dataclass
class FollowupRegressionRecord:
    """补槽后续答闭环回归记录。"""

    question_id: str
    question: str
    followup_question: str
    actual_query_key: str | None
    status_code: str
    row_count: int
    passed: bool
    outcome: str
    gap_type: str | None
    closure_reason: str


@dataclass
class UnclosedAttributionRecord:
    """补槽后未闭环 24 条归因记录。"""

    question_id: str
    question: str
    previous_query_key: str | None
    current_query_key: str | None
    current_status_code: str
    current_row_count: int
    attribution: str
    engineering_action: str
    recommended_status: str
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


def _load_b_items() -> list[dict[str, Any]]:
    """读取当前 903 总账中的 B 类题。"""

    payload = _load_json(LEDGER_PATH)
    return [item for item in payload["items"] if item.get("current_status") == "B"]


def _load_wave3_review_items() -> list[dict[str, Any]]:
    """读取 Wave3 固定复核题源。

    返回：
        当前 B 类题 + Wave2 未闭环 24 条固定复核题。

    说明：
        Wave3 首次执行后会把 24 条工程修复题迁入 A；如果脚本再次执行，只读取当前 B
        会丢失这 24 条迁移配置，导致总账重建回滚。因此这里把 Wave2 未闭环 24 条作为
        固定复核题源纳入，保证脚本可重复执行。
    """

    payload = _load_json(LEDGER_PATH)
    ledger_index = {
        (item["question_id"], item["question"]): item
        for item in payload["items"]
    }
    review_items = [dict(item) for item in payload["items"] if item.get("current_status") == "B"]
    seen = {(item["question_id"], item["question"]) for item in review_items}
    for source_item in _load_wave2_followup_items("unresolved_after_followup"):
        key = (source_item["question_id"], source_item["question"])
        if key in seen or key not in ledger_index:
            continue
        ledger_item = dict(ledger_index[key])
        ledger_item["governance_pool"] = ledger_item.get("governance_pool") or "Wave2未闭环复核固定源"
        review_items.append(ledger_item)
        seen.add(key)
    return review_items


def _load_roadmap_items() -> dict[str, dict[str, Any]]:
    """读取 B-gap 能力路线图，按能力编号索引。"""

    if not ROADMAP_PATH.exists():
        return {}
    payload = _load_json(ROADMAP_PATH)
    return {
        item["capability_id"]: item
        for item in payload.get("items", [])
        if item.get("capability_id")
    }


def _load_wave2_followup_items(outcome: str) -> list[dict[str, Any]]:
    """读取 Wave2 补槽闭环中特定 outcome 的题。"""

    if not WAVE2_FOLLOWUP_REPORT_PATH.exists():
        return []
    payload = _load_json(WAVE2_FOLLOWUP_REPORT_PATH)
    return [item for item in payload.get("items", []) if item.get("outcome") == outcome]


def _build_service() -> tuple[Any, LogisticsDataQaService]:
    """构造真实 data-qa 服务，并关闭 LLM 对正式裁决的影响。

    返回：
        数据库会话与 data-qa 服务实例。
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


def _contains_any(text: str, keywords: list[str]) -> bool:
    """判断文本是否包含任一关键词。"""

    return any(keyword in text for keyword in keywords)


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
    """识别不应因为通用 query_key 命中而迁 A 的题。

    说明：
        部分开放诊断题在模拟补槽后可能被泛化到 `hist_mw_summary`，
        但原题实际要求原因、影响、字段一致性或业务建议，不能迁入 A。
    """

    compact = re.sub(r"\s+", "", question)
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
        "高频前三类",
        "推广",
        "划算",
        "口径",
    ]
    return query_key == "hist_mw_summary" and _contains_any(compact, diagnostic_keywords)


def _capability_id_for_item(query_key: str | None, question: str) -> str | None:
    """把 query_key 和题面映射到 B-gap 能力项。"""

    compact = re.sub(r"\s+", "", question)
    if query_key == "hist_quarter_region_metric":
        return "B-GAP-006" if _contains_any(compact, ["单瓦", "元瓦", "成本"]) else "B-GAP-005"
    if query_key == "hist_monthly_trip_count_summary":
        return "B-GAP-003"
    if query_key in {"hist_route_aggregate_summary", "hist_origin_vehicle_metric_summary"}:
        return "B-GAP-001"
    if query_key in {"hist_procurement_customer_mw_summary", "sys_procurement_task_distribution"}:
        return "B-GAP-009"
    return None


def _classify_gap(question: str, result: Any) -> tuple[str, str, str]:
    """对不能迁 A 的 B 题进行缺口归因。

    返回：
        (gap_type, bucket, reason)。
    """

    compact = re.sub(r"\s+", "", question)
    status_code = result.status.code if result.status else "NO_STATUS"
    if status_code == LogisticsErrorCodeRegistry.EMPTY_RESULT:
        return "data_scope_gap", "B-数据口径缺口", "当前 query_key 已命中但结果为空，需要确认数据覆盖范围或零值回答口径。"
    if result.query_plan.intent == "unsupported" or status_code == LogisticsErrorCodeRegistry.UNSUPPORTED_QUESTION:
        return "business_definition_gap", "B-不应迁移边界题", "真实链路判定超出现有结构化能力边界，本轮不强迁 A。"
    if _contains_any(compact, ["最近", "近期", "最差", "异常", "问题", "风险", "高不高", "合理", "原因", "影响", "为什么", "效率", "划算", "推广"]):
        return "business_definition_gap", "B-业务定义缺口", "缺少异常、好坏、原因或收益判断口径，必须业务化澄清。"
    if _contains_any(compact, ["仓库", "allocate", "warehouse", "字段", "空值", "合同", "单据", "回单", "经纬度", "打卡", "绑定"]):
        return "data_scope_gap", "B-数据口径缺口", "依赖一期未固化字段、映射关系或数据覆盖范围，暂不迁 A。"
    if result.needs_clarification:
        return "query_key_gap", "B-长期澄清池", "真实链路仍要求补充时间、指标、维度或比较口径。"
    return "query_key_gap", "B-长期澄清池", "真实链路未稳定进入 OK，也未形成明确拒答，需继续补能力或澄清模板。"


def _evaluate_b_items() -> tuple[list[Wave3ReviewRecord], dict[str, Any]]:
    """执行剩余 B=206 的 Wave3 真实链路复核。

    返回：
        逐题复核记录和能力路线图上下文。
    """

    items = _load_wave3_review_items()
    roadmap_items = _load_roadmap_items()
    db, service = _build_service()
    records: list[Wave3ReviewRecord] = []
    try:
        for item in items:
            try:
                result = service.query(
                    LogisticsDataQaQueryRequest(question=item["question"]),
                    trace_id="logistics-903-b-gap-wave3",
                )
                status_code = result.status.code if result.status else "NO_STATUS"
                query_key = result.query_plan.query_key
                row_count = len(result.result_table.rows)
                if _is_answerable(result) and not _is_false_generic_answer(item["question"], query_key):
                    gap_type = None
                    recommended_status = "A"
                    capability_id = _capability_id_for_item(query_key, item["question"])
                    closure_reason = "真实 data-qa 主链路返回 OK、supported=true、非澄清、非拒答、结果非空，可进入 Wave3 B->A 迁移复核。"
                    if capability_id:
                        closure_reason += f" 对应能力项：{capability_id}。"
                else:
                    gap_type, _bucket, closure_reason = _classify_gap(item["question"], result)
                    recommended_status = "B"
                    capability_id = _capability_id_for_item(query_key, item["question"])
                records.append(
                    Wave3ReviewRecord(
                        question_id=item["question_id"],
                        question=item["question"],
                        source_group=item["source_group"],
                        family=item["family"],
                        governance_pool_before=item["governance_pool"],
                        actual_query_key=query_key,
                        status_code=status_code,
                        supported=bool(result.supported),
                        needs_clarification=bool(result.needs_clarification),
                        row_count=row_count,
                        recommended_status=recommended_status,
                        gap_type=gap_type,
                        capability_id=capability_id,
                        closure_reason=closure_reason,
                        answer_summary=result.answer_summary,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                records.append(
                    Wave3ReviewRecord(
                        question_id=item["question_id"],
                        question=item["question"],
                        source_group=item["source_group"],
                        family=item["family"],
                        governance_pool_before=item["governance_pool"],
                        actual_query_key=None,
                        status_code="EXCEPTION",
                        supported=False,
                        needs_clarification=False,
                        row_count=0,
                        recommended_status="B",
                        gap_type="execution_gap",
                        capability_id=None,
                        closure_reason=f"真实链路执行异常，暂不迁 A：{exc}",
                        answer_summary="",
                    )
                )
    finally:
        db.close()
    return records, {"roadmap_items": roadmap_items}


def _evaluate_followup_16() -> dict[str, Any]:
    """对 Wave2 补槽后可答 16 条建立正式闭环回归。

    返回：
        包含汇总和逐题记录的报告。
    """

    source_items = _load_wave2_followup_items("answerable_after_followup")
    db, service = _build_service()
    records: list[FollowupRegressionRecord] = []
    try:
        for item in source_items:
            followup_question = item["followup_question"]
            result = service.query(
                LogisticsDataQaQueryRequest(question=followup_question),
                trace_id="logistics-903-b-wave3-followup-closure",
            )
            status_code = result.status.code if result.status else "NO_STATUS"
            query_key = result.query_plan.query_key
            row_count = len(result.result_table.rows)
            passed = _is_answerable(result) and not _is_false_generic_answer(item["question"], query_key)
            if passed:
                outcome = "answerable_after_followup_confirmed"
                gap_type = None
                closure_reason = "用户补充口径后真实链路稳定进入受控 query_key，可作为后续迁移复核输入；原题仍需先澄清。"
            else:
                outcome = "generic_or_boundary_followup_not_migratable"
                gap_type, _bucket, closure_reason = _classify_gap(item["question"], result)
                if _is_false_generic_answer(item["question"], query_key):
                    gap_type = "business_definition_gap"
                    closure_reason = "补槽后虽命中通用汇总 query_key，但原题要求原因/影响/字段一致性或业务建议，不能作为真实可答闭环迁 A。"
            records.append(
                FollowupRegressionRecord(
                    question_id=item["question_id"],
                    question=item["question"],
                    followup_question=followup_question,
                    actual_query_key=query_key,
                    status_code=status_code,
                    row_count=row_count,
                    passed=passed,
                    outcome=outcome,
                    gap_type=gap_type,
                    closure_reason=closure_reason,
                )
            )
    finally:
        db.close()
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_report": str(WAVE2_FOLLOWUP_REPORT_PATH),
        "summary": {
            "total_questions": len(records),
            "closed_after_followup": sum(1 for record in records if record.passed),
            "not_migratable_after_followup": sum(1 for record in records if not record.passed),
            "outcome_breakdown": dict(Counter(record.outcome for record in records)),
            "gap_type_breakdown": dict(Counter(record.gap_type or "none" for record in records)),
        },
        "items": [asdict(record) for record in records],
    }


def _evaluate_unclosed_24() -> dict[str, Any]:
    """对 Wave2 未闭环 24 条做失败归因复检。

    返回：
        当前归因报告；可工程化修复后稳定可答的题会进入 Wave3 迁移候选。
    """

    source_items = _load_wave2_followup_items("unresolved_after_followup")
    db, service = _build_service()
    records: list[UnclosedAttributionRecord] = []
    try:
        for item in source_items:
            result = service.query(
                LogisticsDataQaQueryRequest(question=item["question"]),
                trace_id="logistics-903-b-wave3-unclosed-24",
            )
            status_code = result.status.code if result.status else "NO_STATUS"
            query_key = result.query_plan.query_key
            row_count = len(result.result_table.rows)
            if _is_answerable(result):
                attribution = "repository_query_fixed"
                engineering_action = "已修复 hist_quarter_region_metric 历史台账季度月份过滤逻辑，真实链路从 EMPTY_RESULT 恢复为 OK。"
                recommended_status = "A"
                closure_reason = "原未闭环原因是 repository 查询条件错误，不是业务口径缺失；修复后可进入 Wave3 B->A 迁移。"
            else:
                gap_type, _bucket, closure_reason = _classify_gap(item["question"], result)
                attribution = gap_type or "query_key_gap"
                engineering_action = "当前仍未稳定可答；如果继续修复会涉及业务口径或数据范围确认，本轮不强迁。"
                recommended_status = "B"
            records.append(
                UnclosedAttributionRecord(
                    question_id=item["question_id"],
                    question=item["question"],
                    previous_query_key=item.get("final_query_key"),
                    current_query_key=query_key,
                    current_status_code=status_code,
                    current_row_count=row_count,
                    attribution=attribution,
                    engineering_action=engineering_action,
                    recommended_status=recommended_status,
                    closure_reason=closure_reason,
                )
            )
    finally:
        db.close()
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_report": str(WAVE2_FOLLOWUP_REPORT_PATH),
        "summary": {
            "total_questions": len(records),
            "engineering_fixed_to_a": sum(1 for record in records if record.recommended_status == "A"),
            "remain_b": sum(1 for record in records if record.recommended_status != "A"),
            "attribution_breakdown": dict(Counter(record.attribution for record in records)),
        },
        "items": [asdict(record) for record in records],
    }


def _build_reports(
    records: list[Wave3ReviewRecord],
    context: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """组装 Wave3 各类 JSON 报告和迁移配置。"""

    reviewed_at = datetime.now().isoformat(timespec="seconds")
    migration_records = [record for record in records if record.recommended_status == "A"]
    remain_records = [record for record in records if record.recommended_status != "A"]
    candidate_pool_records = [record for record in records if record.governance_pool_before == "B-候选收口池"]
    query_key_counter = Counter(record.actual_query_key or "NONE" for record in records)
    status_counter = Counter(record.status_code for record in records)
    gap_counter = Counter(record.gap_type or "none" for record in records)
    capability_counter = Counter(record.capability_id or "none" for record in records)

    secondary_report = {
        "generated_at": reviewed_at,
        "source_ledger": str(LEDGER_PATH),
        "summary": {
            "total_b_questions": len(records),
            "candidate_pool_total": len(candidate_pool_records),
            "candidate_pool_migrated_to_a": sum(1 for record in candidate_pool_records if record.recommended_status == "A"),
            "candidate_pool_remain_b": sum(1 for record in candidate_pool_records if record.recommended_status != "A"),
            "recommended_status_breakdown": dict(Counter(record.recommended_status for record in records)),
            "status_code_breakdown": dict(status_counter),
            "query_key_breakdown": dict(query_key_counter),
            "gap_type_breakdown": dict(gap_counter),
            "capability_breakdown": dict(capability_counter),
        },
        "candidate_pool_items": [asdict(record) for record in candidate_pool_records],
        "items": [asdict(record) for record in records],
    }
    wave3_report = {
        "generated_at": reviewed_at,
        "source_roadmap": str(ROADMAP_PATH),
        "summary": {
            "reviewed_questions": len(records),
            "migrated_to_a_total": len(migration_records),
            "remain_b_total": len(remain_records),
            "handled_capability_items": {
                key: value
                for key, value in capability_counter.items()
                if key != "none"
            },
            "policy": "只有真实 data-qa 主链路返回 OK、supported=true、非澄清、非拒答且结果非空的题，才允许作为 Wave3 B->A 迁移候选。",
        },
        "migration_items": [asdict(record) for record in migration_records],
        "remain_b_items": [asdict(record) for record in remain_records],
        "roadmap_items": context["roadmap_items"],
    }
    migration_config = {
        "generated_at": reviewed_at,
        "source_report": str(WAVE3_REPORT_PATH),
        "migration_rule": "Wave3 真实 data-qa 主链路返回 OK、supported=true、非澄清、非拒答、结果非空，且不是通用 query_key 误吸收开放诊断题。",
        "items": [
            {
                "migration_id": f"B-GAP-W3-{index:03d}",
                "question_id": record.question_id,
                "question": record.question,
                "source": "B-gap Wave3 query_key_gap migration review",
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
        "generated_at": reviewed_at,
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
    business_matrix = _build_business_confirmation_matrix(remain_records, reviewed_at)
    return secondary_report, wave3_report, migration_config, a_regression_set, business_matrix


def _build_business_confirmation_matrix(records: list[Wave3ReviewRecord], generated_at: str) -> dict[str, Any]:
    """生成 data_scope_gap / business_definition_gap 业务确认矩阵。

    说明：
        用户要求的 `data_scope_gap=69 / business_definition_gap=33` 来自 Wave2 补槽闭环基线；
        Wave3 真实链路复核后部分题已经迁移或重新归因，因此矩阵同时保留 Wave2 要求确认
        范围和 Wave3 后仍开放的当前确认范围，避免把历史基线误读成当前剩余缺口。
    """

    current_record_index = {
        (record.question_id, record.question): record
        for record in records
    }
    matrix_items: list[dict[str, Any]] = []

    # 先按 Wave2 基线口径纳入用户指定的 data_scope_gap=69 / business_definition_gap=33。
    if WAVE2_FOLLOWUP_REPORT_PATH.exists():
        for item in _load_json(WAVE2_FOLLOWUP_REPORT_PATH).get("items", []):
            gap_type = item.get("gap_type")
            if gap_type not in {"data_scope_gap", "business_definition_gap"}:
                continue
            current_record = current_record_index.get((item["question_id"], item["question"]))
            if gap_type == "data_scope_gap":
                missing = "缺少稳定数据字段、数据覆盖范围、空值处理或零值统计口径。"
                migration_path = "数据 owner 确认字段来源、过滤范围和空值/零值展示规则后，再进入 B->A 迁移复核。"
                owner_type = "数据 owner"
            else:
                missing = "缺少异常、风险、最差、原因、效率或业务判断定义。"
                migration_path = "业务 owner 确认评价标准、阈值或原因分类口径后，再进入澄清模板或 A 候选复核。"
                owner_type = "业务 owner"
            matrix_items.append(
                {
                    "question_id": item["question_id"],
                    "question": item["question"],
                    "gap_type": gap_type,
                    "family": item.get("family"),
                    "owner_type": owner_type,
                    "source_scope": "wave2_requested_confirmation_scope",
                    "current_status_after_wave3": current_record.recommended_status if current_record else "UNKNOWN",
                    "current_gap_type_after_wave3": current_record.gap_type if current_record else None,
                    "missing_definition": missing,
                    "current_reason": (
                        current_record.closure_reason
                        if current_record
                        else item.get("closure_reason", "")
                    ),
                    "confirmation_needed": current_record is None or current_record.recommended_status != "A",
                    "migration_path_after_confirmation": migration_path,
                }
            )

    existing_keys = {
        (item["question_id"], item["question"], item["gap_type"])
        for item in matrix_items
    }
    for record in records:
        if record.gap_type not in {"data_scope_gap", "business_definition_gap"}:
            continue
        matrix_key = (record.question_id, record.question, record.gap_type)
        if matrix_key in existing_keys:
            continue
        if record.gap_type == "data_scope_gap":
            missing = "缺少稳定数据字段、数据覆盖范围、空值处理或零值统计口径。"
            migration_path = "数据 owner 确认字段来源、过滤范围和空值/零值展示规则后，再进入 B->A 迁移复核。"
            owner_type = "数据 owner"
        else:
            missing = "缺少异常、风险、最差、原因、效率或业务判断定义。"
            migration_path = "业务 owner 确认评价标准、阈值或原因分类口径后，再进入澄清模板或 A 候选复核。"
            owner_type = "业务 owner"
        matrix_items.append(
            {
                "question_id": record.question_id,
                "question": record.question,
                "gap_type": record.gap_type,
                "family": record.family,
                "owner_type": owner_type,
                "source_scope": "wave3_current_open_confirmation_scope",
                "current_status_after_wave3": record.recommended_status,
                "current_gap_type_after_wave3": record.gap_type,
                "missing_definition": missing,
                "current_reason": record.closure_reason,
                "confirmation_needed": True,
                "migration_path_after_confirmation": migration_path,
            }
        )
    wave2_scope_items = [
        item for item in matrix_items if item["source_scope"] == "wave2_requested_confirmation_scope"
    ]
    current_open_items = [
        item for item in matrix_items if item.get("confirmation_needed") is True
    ]
    return {
        "generated_at": generated_at,
        "source_report": str(WAVE3_REPORT_PATH),
        "summary": {
            "total_items": len(matrix_items),
            "wave2_requested_confirmation_total": len(wave2_scope_items),
            "wave2_requested_gap_type_breakdown": dict(Counter(item["gap_type"] for item in wave2_scope_items)),
            "current_open_confirmation_total": len(current_open_items),
            "gap_type_breakdown": dict(Counter(item["gap_type"] for item in matrix_items)),
            "owner_type_breakdown": dict(Counter(item["owner_type"] for item in matrix_items)),
        },
        "items": matrix_items,
    }


def _render_secondary_doc(report: dict[str, Any]) -> str:
    """渲染 Wave3 B=206 二次复核文档。"""

    summary = report["summary"]
    lines = [
        "# 903 剩余 B 类 Wave3 二次复核",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、复核结论",
        "",
        f"- 复核 B 类题总数：`{summary['total_b_questions']}`",
        f"- B-候选收口池：`{summary['candidate_pool_total']}`",
        f"- 候选池迁入 A：`{summary['candidate_pool_migrated_to_a']}`",
        f"- 候选池保留 B：`{summary['candidate_pool_remain_b']}`",
        f"- 推荐状态：`{summary['recommended_status_breakdown']}`",
        f"- gap 类型：`{summary['gap_type_breakdown']}`",
        "",
        "## 二、候选池 4 条复核结果",
        "",
    ]
    for item in report["candidate_pool_items"]:
        lines.append(f"- {item['question_id']} | {item['recommended_status']} | {item['closure_reason']} | {item['question']}")
    lines.extend(["", "## 三、迁入 A 代表题", ""])
    for item in [item for item in report["items"] if item["recommended_status"] == "A"][:30]:
        lines.append(f"- {item['question_id']} | {item['actual_query_key']} | {item['question']}")
    lines.extend(["", "## 四、继续留 B 代表题", ""])
    for item in [item for item in report["items"] if item["recommended_status"] != "A"][:30]:
        lines.append(f"- {item['question_id']} | {item['gap_type']} | {item['closure_reason']} | {item['question']}")
    return "\n".join(lines) + "\n"


def _render_wave3_doc(report: dict[str, Any]) -> str:
    """渲染 Wave3 能力建设与迁移复核文档。"""

    summary = report["summary"]
    lines = [
        "# 903 B-gap Wave3 能力建设与迁移复核",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、结论",
        "",
        f"- 本轮复核题数：`{summary['reviewed_questions']}`",
        f"- Wave3 迁入 A 候选：`{summary['migrated_to_a_total']}`",
        f"- Wave3 保留 B：`{summary['remain_b_total']}`",
        "",
        "## 二、处理能力项",
        "",
    ]
    for capability_id, count in summary["handled_capability_items"].items():
        lines.append(f"- `{capability_id}`：`{count}` 条")
    lines.extend(
        [
            "",
            "## 三、迁移规则",
            "",
            f"- {summary['policy']}",
            "- 对缺数据范围、业务定义或仍需澄清的题继续保留 B。",
            "- LLM 不查数、不生成 SQL、不改写 B/C 边界。",
            "",
            "## 四、迁移候选",
            "",
        ]
    )
    for item in report["migration_items"]:
        lines.append(f"- {item['question_id']} | {item['actual_query_key']} | {item['question']}")
    lines.extend(["", "## 五、保留 B 样例", ""])
    for item in report["remain_b_items"][:30]:
        lines.append(f"- {item['question_id']} | {item['gap_type']} | {item['closure_reason']} | {item['question']}")
    return "\n".join(lines) + "\n"


def _render_followup_doc(report: dict[str, Any]) -> str:
    """渲染补槽闭环 16 条正式回归文档。"""

    summary = report["summary"]
    lines = [
        "# Wave3 B 类补槽后续答闭环正式回归",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、结论",
        "",
        f"- 复核总数：`{summary['total_questions']}`",
        f"- 补槽后稳定闭环：`{summary['closed_after_followup']}`",
        f"- 补槽后仍不宜迁移：`{summary['not_migratable_after_followup']}`",
        f"- outcome 分布：`{summary['outcome_breakdown']}`",
        f"- gap 分布：`{summary['gap_type_breakdown']}`",
        "",
        "## 二、逐题结果",
        "",
    ]
    for item in report["items"]:
        lines.append(f"- {item['question_id']} | {item['outcome']} | {item['closure_reason']} | {item['question']}")
    return "\n".join(lines) + "\n"


def _render_unclosed_doc(report: dict[str, Any]) -> str:
    """渲染未闭环 24 条归因文档。"""

    summary = report["summary"]
    lines = [
        "# Wave3 B 类补槽后未闭环 24 条归因",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、结论",
        "",
        f"- 复核总数：`{summary['total_questions']}`",
        f"- 工程修复后可迁 A：`{summary['engineering_fixed_to_a']}`",
        f"- 继续留 B：`{summary['remain_b']}`",
        f"- 归因分布：`{summary['attribution_breakdown']}`",
        "",
        "## 二、逐题归因",
        "",
    ]
    for item in report["items"]:
        lines.append(f"- {item['question_id']} | {item['attribution']} | {item['engineering_action']} | {item['question']}")
    return "\n".join(lines) + "\n"


def _render_business_matrix_doc(report: dict[str, Any]) -> str:
    """渲染业务确认矩阵文档。"""

    summary = report["summary"]
    lines = [
        "# Wave3 B 类数据口径 / 业务定义确认矩阵",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、结论",
        "",
        f"- 待确认题数：`{summary['total_items']}`",
        f"- Wave2 要求确认范围：`{summary['wave2_requested_confirmation_total']}`",
        f"- Wave2 要求确认缺口：`{summary['wave2_requested_gap_type_breakdown']}`",
        f"- Wave3 后当前仍开放确认范围：`{summary['current_open_confirmation_total']}`",
        f"- 缺口类型：`{summary['gap_type_breakdown']}`",
        f"- Owner 类型：`{summary['owner_type_breakdown']}`",
        "",
        "## 二、确认原则",
        "",
        "- data_scope_gap 不硬开发，必须先确认数据字段、覆盖范围和空值/零值口径。",
        "- business_definition_gap 不硬迁 A，必须先确认异常、风险、好坏、原因或效率评价标准。",
        "- 业务确认后再进入 B->A 迁移复核或澄清模板复检。",
        "",
        "## 三、代表题",
        "",
    ]
    for item in report["items"][:80]:
        lines.append(f"- {item['question_id']} | {item['gap_type']} | {item['owner_type']} | {item['current_reason']} | {item['question']}")
    return "\n".join(lines) + "\n"


def main() -> None:
    """命令行入口：执行 Wave3 全部 B 侧治理报告生成。"""

    records, context = _evaluate_b_items()
    secondary_report, wave3_report, migration_config, a_regression_set, business_matrix = _build_reports(records, context)
    followup_report = _evaluate_followup_16()
    unclosed_report = _evaluate_unclosed_24()

    for path, payload in (
        (SECONDARY_REPORT_PATH, secondary_report),
        (WAVE3_REPORT_PATH, wave3_report),
        (MIGRATION_CONFIG_PATH, migration_config),
        (A_REGRESSION_QUESTION_SET_PATH, a_regression_set),
        (FOLLOWUP_REPORT_PATH, followup_report),
        (UNCLOSED_ATTRIBUTION_REPORT_PATH, unclosed_report),
        (BUSINESS_CONFIRMATION_MATRIX_PATH, business_matrix),
    ):
        _write_json(path, payload)

    SECONDARY_DOC_PATH.write_text(_render_secondary_doc(secondary_report), encoding="utf-8")
    WAVE3_DOC_PATH.write_text(_render_wave3_doc(wave3_report), encoding="utf-8")
    FOLLOWUP_DOC_PATH.write_text(_render_followup_doc(followup_report), encoding="utf-8")
    UNCLOSED_ATTRIBUTION_DOC_PATH.write_text(_render_unclosed_doc(unclosed_report), encoding="utf-8")
    BUSINESS_CONFIRMATION_MATRIX_DOC_PATH.write_text(_render_business_matrix_doc(business_matrix), encoding="utf-8")

    print(
        json.dumps(
            {
                "wave3": wave3_report["summary"],
                "followup_16": followup_report["summary"],
                "unclosed_24": unclosed_report["summary"],
                "business_confirmation": business_matrix["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
