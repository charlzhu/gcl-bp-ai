from __future__ import annotations

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
SECONDARY_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave2_secondary_review_report.json"
WAVE2_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_gap_wave2_report.json"
MIGRATION_CONFIG_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b_gap_wave2_migration_candidates.json"
A_REGRESSION_QUESTION_SET_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b_gap_wave2_a_regression_questions.json"
SECONDARY_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_WAVE2_SECONDARY_REVIEW.md"
WAVE2_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_GAP_WAVE2.md"


class NoopQueryLogRepository:
    """无副作用查询日志仓储。

    说明：
        Wave2 会批量调用真实 data-qa 主链路，但不应污染用户查询历史。
    """

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        """忽略查询日志写入请求。"""

        _ = db, payload
        return 0


@dataclass
class Wave2ReviewRecord:
    """Wave2 B 类单题复核记录。"""

    question_id: str
    question: str
    source_group: str
    family: str
    governance_pool_before: str
    secondary_bucket: str
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


def _load_json(path: Path) -> Any:
    """读取 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))


def _load_b_items() -> list[dict[str, Any]]:
    """读取当前 903 总账里的 B 类题。"""

    payload = _load_json(LEDGER_PATH)
    return [item for item in payload["items"] if item.get("current_status") == "B"]


def _load_roadmap_items() -> dict[str, dict[str, Any]]:
    """读取 B-gap 能力路线图并按 capability_id 建索引。"""

    if not ROADMAP_PATH.exists():
        return {}
    payload = _load_json(ROADMAP_PATH)
    return {
        item["capability_id"]: item
        for item in payload.get("capability_items", [])
        if item.get("capability_id")
    }


def _build_service() -> tuple[Any, LogisticsDataQaService]:
    """构造真实 data-qa 服务，同时关闭 LLM 对正式裁决的影响。"""

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


def _capability_id_for_query_key(query_key: str | None, question: str) -> str | None:
    """把当前命中的 query_key 反向映射到 Wave2 能力项。"""

    if query_key in {"hist_transport_mode_record_summary", "hist_mw_summary", "hist_unit_fee_per_watt"}:
        return "B-GAP-032"
    if query_key == "hist_product_spec_mw_summary":
        return "B-GAP-002"
    if query_key == "hist_high_fee_addresses_by_customer":
        return "B-GAP-001"
    if query_key == "hist_quarter_region_metric":
        return "B-GAP-005"
    if query_key in {
        "sys_task_status_distribution",
        "sys_task_status_province_ranking",
        "sys_reconciliation_fill_rate_by_month",
        "sys_ship_product_detail_stats",
        "sys_driver_task_ranking",
        "sys_delivery_note_parse_status_distribution",
    }:
        return "B-GAP-007"
    if query_key in {"sys_procurement_task_distribution", "sys_procurement_avg_loading_trucks"}:
        return "B-GAP-009"
    if query_key == "hist_remark_keyword_fee_ratio":
        return "B-GAP-061"
    if query_key == "sys_extra_fee_summary":
        return "B-GAP-061"
    if _contains_any(question, ["mapping", "映射", "同步"]):
        return "B-GAP-011"
    return None


def _classify_gap(question: str, result: Any) -> tuple[str, str, str | None, str]:
    """基于真实链路结果把 B 题分入 Wave2 二次治理桶。

    返回：
        secondary_bucket、recommended_status、gap_type、closure_reason。
    """

    status_code = result.status.code if result.status else "NO_STATUS"
    query_key = result.query_plan.query_key
    row_count = len(result.result_table.rows)
    if (
        result.supported
        and not result.needs_clarification
        and status_code == LogisticsErrorCodeRegistry.OK
        and query_key
        and row_count > 0
    ):
        return (
            "B-候选收口池",
            "A",
            None,
            "真实 data-qa 主链路返回 OK、supported=true、非澄清、非拒答、且结果非空，可进入 B->A 迁移复核。",
        )
    compact = question.replace(" ", "")
    if result.status and status_code == LogisticsErrorCodeRegistry.EMPTY_RESULT:
        return (
            "B-数据口径缺口",
            "B",
            "data_scope_gap",
            "当前 query_key 已命中但结果为空，需要先确认数据覆盖范围或零值回答口径，暂不迁 A。",
        )
    if result.query_plan.intent == "unsupported" or status_code == LogisticsErrorCodeRegistry.UNSUPPORTED_QUESTION:
        return (
            "B-不应迁移边界题",
            "B",
            "business_definition_gap",
            "当前真实链路判定为不支持或超出现有结构化边界，本轮保持 B/C 边界保护，不强迁 A。",
        )
    if _contains_any(compact, ["最近", "近期", "怎么样", "最差", "异常", "问题", "风险", "高不高", "合理", "原因", "影响", "为什么", "忙", "效率"]):
        return (
            "B-业务定义缺口",
            "B",
            "business_definition_gap",
            "题面缺少异常、风险、好坏或原因归因的业务定义，必须先业务化澄清。",
        )
    if _contains_any(compact, ["仓库", "allocate", "warehouse", "项目名称", "合同", "单据", "回单", "supplier_price", "字段", "空值"]):
        return (
            "B-数据口径缺口",
            "B",
            "data_scope_gap",
            "题面依赖当前一期未固化的数据字段、映射关系或数据覆盖范围，暂不迁 A。",
        )
    if result.needs_clarification:
        return (
            "B-补槽后可答池",
            "B",
            "query_key_gap",
            "当前仍需要补充时间、指标、维度或比较口径；后续可通过补槽闭环验证是否进入 A。",
        )
    return (
        "B-长期澄清池",
        "B",
        "business_definition_gap",
        "当前结果没有稳定进入 OK，也没有明确数据口径可落地，继续保持澄清边界。",
    )


def _evaluate_items() -> tuple[list[Wave2ReviewRecord], dict[str, Any]]:
    """执行 B=267 的真实链路二次复核。"""

    items = _load_b_items()
    roadmap_items = _load_roadmap_items()
    db, service = _build_service()
    records: list[Wave2ReviewRecord] = []
    try:
        for item in items:
            try:
                result = service.query(
                    LogisticsDataQaQueryRequest(question=item["question"]),
                    trace_id="logistics-903-b-gap-wave2",
                )
                status_code = result.status.code if result.status else "NO_STATUS"
                query_key = result.query_plan.query_key
                row_count = len(result.result_table.rows)
                secondary_bucket, recommended_status, gap_type, closure_reason = _classify_gap(item["question"], result)
                capability_id = _capability_id_for_query_key(query_key, item["question"])
                if capability_id and capability_id in roadmap_items and recommended_status == "A":
                    closure_reason += f" 对应能力项：{capability_id}。"
                records.append(
                    Wave2ReviewRecord(
                        question_id=item["question_id"],
                        question=item["question"],
                        source_group=item["source_group"],
                        family=item["family"],
                        governance_pool_before=item["governance_pool"],
                        secondary_bucket=secondary_bucket,
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
                    Wave2ReviewRecord(
                        question_id=item["question_id"],
                        question=item["question"],
                        source_group=item["source_group"],
                        family=item["family"],
                        governance_pool_before=item["governance_pool"],
                        secondary_bucket="B-数据口径缺口",
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


def _build_reports(records: list[Wave2ReviewRecord], context: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """组装 Wave2 结构化报告、迁移配置和 A 行为回归题集。"""

    bucket_counter = Counter(record.secondary_bucket for record in records)
    status_counter = Counter(record.status_code for record in records)
    query_key_counter = Counter(record.actual_query_key or "NONE" for record in records)
    family_counter = Counter(record.family for record in records)
    gap_counter = Counter(record.gap_type or "none" for record in records)
    capability_counter = Counter(record.capability_id or "none" for record in records)
    migration_records = [record for record in records if record.recommended_status == "A"]
    candidate_pool_records = [record for record in records if record.governance_pool_before == "B-候选收口池"]
    reviewed_at = datetime.now().isoformat(timespec="seconds")

    secondary_report = {
        "generated_at": reviewed_at,
        "source_ledger": str(LEDGER_PATH),
        "summary": {
            "total_b_questions": len(records),
            "secondary_bucket_breakdown": dict(bucket_counter),
            "recommended_status_breakdown": dict(Counter(record.recommended_status for record in records)),
            "status_code_breakdown": dict(status_counter),
            "query_key_breakdown": dict(query_key_counter),
            "family_breakdown": dict(family_counter),
            "gap_type_breakdown": dict(gap_counter),
            "capability_breakdown": dict(capability_counter),
        },
        "items": [asdict(record) for record in records],
    }
    wave2_report = {
        "generated_at": reviewed_at,
        "source_roadmap": str(ROADMAP_PATH),
        "summary": {
            "reviewed_questions": len(records),
            "candidate_pool_total": len(candidate_pool_records),
            "candidate_pool_migrated_to_a": sum(1 for record in candidate_pool_records if record.recommended_status == "A"),
            "candidate_pool_remain_b": sum(1 for record in candidate_pool_records if record.recommended_status != "A"),
            "migrated_to_a_total": len(migration_records),
            "remain_b_total": len(records) - len(migration_records),
            "handled_capability_items": {
                key: value
                for key, value in capability_counter.items()
                if key != "none"
            },
            "policy": "只有真实 data-qa 主链路返回 OK、supported=true、非澄清、非拒答且结果非空的题，才允许作为 Wave2 B->A 迁移候选。",
        },
        "candidate_pool_items": [asdict(record) for record in candidate_pool_records],
        "migration_items": [asdict(record) for record in migration_records],
        "remain_b_items": [asdict(record) for record in records if record.recommended_status != "A"],
        "roadmap_items": context["roadmap_items"],
    }
    migration_config = {
        "generated_at": reviewed_at,
        "source_report": str(WAVE2_REPORT_PATH),
        "migration_rule": "Wave2 真实 data-qa 主链路返回 OK、supported=true、非澄清、非拒答、结果非空。",
        "items": [
            {
                "migration_id": f"B-GAP-W2-{index:03d}",
                "question_id": record.question_id,
                "question": record.question,
                "source": "B-gap Wave2 P1/P2 query_key_gap migration review",
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
    return secondary_report, wave2_report, migration_config, a_regression_set


def _render_secondary_doc(report: dict[str, Any]) -> str:
    """渲染 B=267 二次分层复核文档。"""

    summary = report["summary"]
    lines = [
        "# 903 剩余 B 类 Wave2 二次分层复核",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、复核结论",
        "",
        f"- 复核 B 类题总数：`{summary['total_b_questions']}`",
        f"- 二次分层：`{summary['secondary_bucket_breakdown']}`",
        f"- 推荐状态：`{summary['recommended_status_breakdown']}`",
        f"- gap 类型：`{summary['gap_type_breakdown']}`",
        "",
        "## 二、分层原则",
        "",
        "- 真实 data-qa 返回 OK、supported=true、非澄清、非拒答且结果非空，才进入可迁 A 候选。",
        "- 需要补充时间、指标、维度或比较标准的题，继续进入 B-补槽后可答池。",
        "- 缺数据字段、数据覆盖范围或零值口径的题，进入 B-数据口径缺口。",
        "- 缺异常、风险、最差、原因、效率等业务定义的题，进入 B-业务定义缺口或 B-长期澄清池。",
        "- 超出结构化查询边界的题，不因 LLM 或相似问法强迁 A。",
        "",
        "## 三、代表迁移候选",
        "",
    ]
    migrated = [item for item in report["items"] if item["recommended_status"] == "A"][:20]
    for item in migrated:
        lines.append(f"- {item['question_id']} | {item['actual_query_key']} | {item['question']}")
    lines.extend(["", "## 四、仍需澄清/缺口代表题", ""])
    remain = [item for item in report["items"] if item["recommended_status"] != "A"][:20]
    for item in remain:
        lines.append(f"- {item['question_id']} | {item['secondary_bucket']} | {item['closure_reason']} | {item['question']}")
    return "\n".join(lines) + "\n"


def _render_wave2_doc(report: dict[str, Any]) -> str:
    """渲染 B-gap Wave2 能力建设文档。"""

    summary = report["summary"]
    lines = [
        "# 903 B-gap Wave2 能力建设与迁移复核",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、结论",
        "",
        f"- 本轮复核题数：`{summary['reviewed_questions']}`",
        f"- B-候选收口池复核：`{summary['candidate_pool_total']}`",
        f"- 候选池迁入 A：`{summary['candidate_pool_migrated_to_a']}`",
        f"- 候选池保留 B：`{summary['candidate_pool_remain_b']}`",
        f"- Wave2 全量迁入 A 候选：`{summary['migrated_to_a_total']}`",
        f"- Wave2 保留 B：`{summary['remain_b_total']}`",
        "",
        "## 二、处理的能力项",
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
            "- 对仍缺数据口径、业务定义或需要补槽的题，保持 B 边界。",
            "- LLM 不参与查数、不生成 SQL、不改写 B/C 最终裁决。",
            "",
            "## 四、迁移候选代表题",
            "",
        ]
    )
    for item in report["migration_items"][:20]:
        lines.append(f"- {item['question_id']} | {item['actual_query_key']} | {item['question']}")
    lines.extend(["", "## 五、保留 B 代表题", ""])
    for item in report["remain_b_items"][:20]:
        lines.append(f"- {item['question_id']} | {item['secondary_bucket']} | {item['closure_reason']} | {item['question']}")
    return "\n".join(lines) + "\n"


def main() -> None:
    """命令行入口：执行 Wave2 二次复核、迁移候选生成与 A 行为回归题集生成。"""

    records, context = _evaluate_items()
    secondary_report, wave2_report, migration_config, a_regression_set = _build_reports(records, context)
    for path, payload in (
        (SECONDARY_REPORT_PATH, secondary_report),
        (WAVE2_REPORT_PATH, wave2_report),
        (MIGRATION_CONFIG_PATH, migration_config),
        (A_REGRESSION_QUESTION_SET_PATH, a_regression_set),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SECONDARY_DOC_PATH.write_text(_render_secondary_doc(secondary_report), encoding="utf-8")
    WAVE2_DOC_PATH.write_text(_render_wave2_doc(wave2_report), encoding="utf-8")
    print(json.dumps(wave2_report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
