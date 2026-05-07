from __future__ import annotations

import argparse
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
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
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
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_followup_closure_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_FOLLOWUP_CLOSURE.md"


@dataclass
class BFollowupRecord:
    """B 类补槽后续答闭环单题记录。"""

    question_id: str
    question: str
    family: str | None
    initial_category: str | None
    initial_missing_slots: list[str]
    initial_questions: list[str]
    assist_used: bool
    assist_provider_mode: str | None
    synthetic_followup: str
    followup_question: str
    final_intent: str | None
    final_query_key: str | None
    final_status_code: str
    final_row_count: int
    final_needs_clarification: bool
    final_clarification_category: str | None
    final_unsupported_category: str | None
    outcome: str
    gap_type: str | None
    closure_reason: str


class NoopQueryLogRepository:
    """无副作用查询日志仓储。

    说明：
        B 类补槽闭环会批量调用真实 data-qa 主链路，但不应写入用户查询历史。
    """

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        """忽略查询日志写入请求。"""

        _ = db, payload
        return 0


def _load_b_items() -> list[dict[str, Any]]:
    """读取 903 总账中的 B 类题。

    返回：
        当前状态为 B 的题目列表。
    """

    payload = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("logistics_903_master_ledger.json 缺少 items 数组。")
    return [item for item in items if item.get("current_status") == "B"]


def _contains_year(question: str) -> bool:
    """判断题目是否已经包含明确年份。"""

    compact = re.sub(r"\s+", "", question)
    return bool(re.search(r"\d{2,4}年", compact) or re.search(r"20(23|24|25|26)", compact))


def _infer_source_scope(question: str) -> str:
    """根据题面推断数据来源补槽口径。"""

    compact = re.sub(r"\s+", "", question)
    if "2026" in compact or "26年" in compact:
        return "数据范围按 2026 年正式系统数据，不纳入测试数据"
    if any(year in compact for year in ("2023", "2024", "2025", "23年", "24年", "25年")):
        return "数据范围按 2023-2025 历史台账口径"
    return "数据范围优先按题目已给年份；如未给年份，先按 2024 年历史台账口径"


def _infer_metric_scope(question: str) -> str:
    """根据题面推断指标补槽口径。

    说明：
        该方法只用于回归中的“用户补充口径”模拟，不作为线上业务口径自动裁决。
    """

    compact = re.sub(r"\s+", "", question)
    if any(keyword in compact for keyword in ("总运费", "总费用", "运费", "费用")):
        return "指标按总运费统计，金额单位按系统默认展示"
    if any(keyword in compact for keyword in ("单瓦", "元/瓦", "元瓦", "单瓦成本", "平均单瓦")):
        return "指标按总运费除以总发运瓦数计算单瓦成本，额外费用默认不并入，除非题目明确要求"
    if any(keyword in compact for keyword in ("车次", "车辆数", "多少车", "总车数")):
        return "指标按发运车次统计，不按唯一车辆数统计"
    if any(keyword in compact for keyword in ("件数", "记录数", "任务量", "任务数")):
        return "指标按题面对象数量统计，输出汇总数量"
    if any(keyword in compact for keyword in ("签收率", "占比", "填充率", "达标率")):
        return "指标按比例口径统计，并同时说明分子和分母"
    if any(keyword in compact for keyword in ("发运量", "运量", "运输量", "MW", "瓦数", "发货量")):
        return "指标按默认运量口径发运瓦数统计，并用 MW 展示"
    return "指标先按发运量 MW 统计；如果题面已有更明确指标，则以题面指标为准"


def _build_synthetic_followup(question: str, missing_slots: list[str], category: str | None) -> str:
    """基于缺失槽位合成一条业务用户补充。

    参数：
        question: 原始 B 类题。
        missing_slots: 规则层识别出的缺失口径。
        category: 澄清类别。

    返回：
        模拟用户补充内容，用于评估“追问之后能否继续进入受控链路”。
    """

    supplements: list[str] = []
    slot_set = set(missing_slots)
    if "time_range" in slot_set or not _contains_year(question):
        supplements.append("时间范围按题目已有时间；如果题目没写年份，则按 2024 年全年")
    if slot_set & {"metric_definition", "evaluation_metric", "result_metric", "price_metric"}:
        supplements.append(_infer_metric_scope(question))
    if "source_scope" in slot_set:
        supplements.append(_infer_source_scope(question))
    if "dimension_split" in slot_set:
        supplements.append("输出先不额外拆分维度，只给汇总结果；如果题目已明确区域、省份、客户或承运商，则按题面限定过滤")
    if "record_scope" in slot_set:
        supplements.append("记录口径按发运车次或任务记录统计，不按去重车辆统计")
    if "aggregation_basis" in slot_set:
        supplements.append("比较和排名按题目指标的汇总值判断，默认从高到低展示")
    if "mapping_field" in slot_set:
        supplements.append("字段归一按业务同义口径处理，例如公路/汽运合并、铁路/铁运合并")
    if "fee_scope" in slot_set:
        supplements.append("费用口径默认只看主运费，不把额外费用并入")
    if "status_scope" in slot_set:
        supplements.append("状态范围按题面指定状态；如未指定状态，则先看全部正式状态")
    if "statistic_scope" in slot_set:
        supplements.append("统计对象只看当前物流正式数据中有效记录，剔除测试数据")
    if "threshold_scope" in slot_set or "exception_threshold" in slot_set:
        supplements.append("异常阈值按超过均值 30% 或题面给定阈值判断")
    if "procurement_scope" in slot_set:
        supplements.append("采购方式按当前系统或台账已有标签统计，未知标签不强行补齐")
    if "sort_order" in slot_set:
        supplements.append("排序按指标值从高到低")
    if not supplements:
        if category == "short_context_scope":
            supplements.append("请按 2024 年全年、发运量 MW、汇总口径查询")
        else:
            supplements.append("按题面已有条件执行，缺失口径按当前物流一期默认口径处理")
    return "；".join(dict.fromkeys(supplements))


def _build_followup_question(question: str, synthetic_followup: str) -> str:
    """把原问题和模拟补充合并为二轮用户问题。"""

    return f"{question}。用户补充口径：{synthetic_followup}。请按这个补充口径继续回答。"


def _resolve_outcome(initial_plan: Any, followup_plan: Any) -> tuple[str, str]:
    """判定 B 类补槽后的 planner 闭环结果。"""

    if initial_plan.query_key and not initial_plan.needs_clarification:
        return "initial_answerable_migration_candidate", "当前总账仍为 B，但正式 planner 已可直接给出受控 query_key，建议后续做台账迁移复核。"
    if followup_plan.query_key and not followup_plan.needs_clarification:
        return "answerable_after_followup", "用户补充口径后已进入受控 query_key，可继续由 data-qa 主链路回答。"
    if followup_plan.intent == "unsupported":
        return "unsupported_after_followup", "用户补充后仍超出现有结构化查询边界，应保持拒答并解释原因。"
    if followup_plan.needs_clarification:
        return "still_clarification_after_followup", "用户补充后仍缺少稳定口径或当前 query_key 不覆盖，应继续澄清或进入能力补齐池。"
    return "unresolved_after_followup", "补槽后没有得到可执行 query_key、澄清或拒答，需补规则保护。"


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


def _is_answerable_result(result: Any) -> bool:
    """判断真实 data-qa 结果是否已经稳定可答。"""

    status_code = result.status.code if result.status else "NO_STATUS"
    return (
        bool(result.query_plan.query_key)
        and bool(result.supported)
        and not bool(result.needs_clarification)
        and status_code == LogisticsErrorCodeRegistry.OK
        and len(result.result_table.rows) > 0
    )


def _resolve_outcome_from_results(initial_result: Any, followup_result: Any) -> tuple[str, str]:
    """基于真实 data-qa 返回判定补槽闭环结果。"""

    if _is_answerable_result(initial_result):
        return "initial_answerable_migration_candidate", "当前总账仍为 B，但真实 data-qa 已可直接回答；需进入迁移复核而不是只停留在澄清。"
    if _is_answerable_result(followup_result):
        return "answerable_after_followup", "用户补充口径后，真实 data-qa 已进入受控 query_key 并返回 OK 非空结果。"
    if followup_result.query_plan.intent == "unsupported" or not followup_result.supported and not followup_result.needs_clarification:
        return "unsupported_after_followup", "用户补充后真实链路仍判定超出现有结构化查询边界。"
    if followup_result.needs_clarification:
        return "still_clarification_after_followup", "用户补充后真实链路仍需澄清，当前不应迁入 A。"
    return "unresolved_after_followup", "用户补充后真实链路没有稳定进入 OK、澄清或拒答，需补规则保护。"


def _resolve_gap_type(question: str, outcome: str, followup_plan: Any) -> str | None:
    """把补槽后仍未闭环的 B 题归因到后续建设缺口。

    参数：
        question: 原始问题。
        outcome: 补槽闭环结果。
        followup_plan: 补槽后的规则解析计划。

    返回：
        None 表示已可答；其他值用于后续 B-gap 能力路线拆分。
    """

    if outcome in {"initial_answerable_migration_candidate", "answerable_after_followup"}:
        return None
    compact = re.sub(r"\s+", "", question)
    data_keywords = [
        "仓库",
        "allocate",
        "warehouse",
        "项目名称",
        "合同",
        "单据",
        "回单",
        "supplier_price",
        "字段",
        "空值",
        "距离",
        "身份证",
        "车牌",
    ]
    business_keywords = [
        "最近",
        "近期",
        "怎么样",
        "最差",
        "异常",
        "问题",
        "风险",
        "高不高",
        "合理",
        "原因",
        "影响",
        "为什么",
        "忙",
        "效率",
        "特殊",
        "治理",
    ]
    if outcome == "unsupported_after_followup":
        return "business_definition_gap"
    if any(keyword in compact for keyword in data_keywords):
        return "data_scope_gap"
    if any(keyword in compact for keyword in business_keywords):
        return "business_definition_gap"
    if followup_plan.clarification_category in {
        "data_quality_scope",
        "data_consistency_scope",
        "mapping_consistency_scope",
        "field_alias_comparison_scope",
        "driver_identity_consistency_scope",
    }:
        return "data_scope_gap"
    if followup_plan.clarification_category in {
        "abnormal_or_reason_scope",
        "comparison_basis_scope",
        "ranking_basis_scope",
        "status_risk_scope",
    }:
        return "business_definition_gap"
    return "query_key_gap"


def evaluate(*, use_live_llm: bool, limit: int) -> dict[str, Any]:
    """执行 B 类补槽后续答闭环评测。"""

    items = _load_b_items()
    if limit > 0:
        items = items[:limit]
    planner = LogisticsDataQaPlanner()
    db, service = _build_service()
    assist = LogisticsLlmClarificationAssistService(
        enabled=True,
        mode="assist" if use_live_llm else "off",
        sample_rate=1.0,
        audit_enabled=False,
    )
    records: list[BFollowupRecord] = []
    counter: Counter[str] = Counter()
    try:
        for item in items:
            question = str(item.get("question") or "")
            initial_plan = planner.build_plan(question)
            assisted_plan, _summary = assist.apply(question=question, plan=initial_plan)
            synthetic_followup = _build_synthetic_followup(
                question=question,
                missing_slots=list(assisted_plan.clarification_missing_slots),
                category=assisted_plan.clarification_category,
            )
            followup_question = _build_followup_question(question, synthetic_followup)
            initial_result = service.query(
                LogisticsDataQaQueryRequest(question=question),
                trace_id="logistics-903-b-followup-closure-initial",
            )
            followup_result = service.query(
                LogisticsDataQaQueryRequest(question=followup_question),
                trace_id="logistics-903-b-followup-closure-followup",
            )
            followup_plan = followup_result.query_plan
            outcome, closure_reason = _resolve_outcome_from_results(initial_result, followup_result)
            gap_type = _resolve_gap_type(question, outcome, followup_plan)
            final_status_code = followup_result.status.code if followup_result.status else "NO_STATUS"
            final_row_count = len(followup_result.result_table.rows)
            counter["total"] += 1
            counter[outcome] += 1
            counter[f"gap::{gap_type or 'none'}"] += 1
            counter[f"family::{item.get('family') or '未分类'}"] += 1
            counter[f"category::{assisted_plan.clarification_category or 'uncategorized'}"] += 1
            records.append(
                BFollowupRecord(
                    question_id=str(item.get("question_id") or ""),
                    question=question,
                    family=item.get("family"),
                    initial_category=assisted_plan.clarification_category,
                    initial_missing_slots=list(assisted_plan.clarification_missing_slots),
                    initial_questions=list(assisted_plan.clarification_questions),
                    assist_used=assisted_plan.clarification_assist_used,
                    assist_provider_mode=assisted_plan.clarification_assist_provider_mode,
                    synthetic_followup=synthetic_followup,
                    followup_question=followup_question,
                    final_intent=followup_plan.intent,
                    final_query_key=followup_plan.query_key,
                    final_status_code=final_status_code,
                    final_row_count=final_row_count,
                    final_needs_clarification=followup_result.needs_clarification,
                    final_clarification_category=followup_plan.clarification_category,
                    final_unsupported_category=followup_plan.unsupported_category,
                    outcome=outcome,
                    gap_type=gap_type,
                    closure_reason=closure_reason,
                )
            )
    finally:
        db.close()
    summary = {
        "total": counter["total"],
        "answerable_after_followup": counter["answerable_after_followup"],
        "initial_answerable_migration_candidate": counter["initial_answerable_migration_candidate"],
        "still_clarification_after_followup": counter["still_clarification_after_followup"],
        "unsupported_after_followup": counter["unsupported_after_followup"],
        "unresolved_after_followup": counter["unresolved_after_followup"],
        "assist_used": sum(1 for record in records if record.assist_used),
        "family_breakdown": {
            key.replace("family::", ""): value
            for key, value in counter.items()
            if key.startswith("family::")
        },
        "category_breakdown": {
            key.replace("category::", ""): value
            for key, value in counter.items()
            if key.startswith("category::")
        },
        "gap_type_breakdown": {
            key.replace("gap::", ""): value
            for key, value in counter.items()
            if key.startswith("gap::")
        },
        "outcome_breakdown": {
            key: value
            for key, value in counter.items()
            if not key.startswith("family::")
            and not key.startswith("category::")
            and not key.startswith("gap::")
            and key != "total"
        },
    }
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "use_live_llm": use_live_llm,
        "source_ledger": str(LEDGER_PATH),
        "summary": summary,
        "items": [asdict(record) for record in records],
    }


def _render_doc(payload: dict[str, Any]) -> str:
    """渲染 B 类补槽闭环文档。"""

    summary = payload["summary"]
    return "\n".join(
        [
            "# 物流域 903 B 类补槽后续答闭环评测",
            "",
            "## 一、结论",
            "",
            f"- 是否真实调用 LLM：`{payload['use_live_llm']}`",
            f"- B 类评测总数：`{summary['total']}`",
            f"- 初始已可答迁移候选：`{summary['initial_answerable_migration_candidate']}`",
            f"- 用户补充后进入可答 query_key：`{summary['answerable_after_followup']}`",
            f"- 用户补充后仍需澄清：`{summary['still_clarification_after_followup']}`",
            f"- 用户补充后应拒答：`{summary['unsupported_after_followup']}`",
            f"- 未解析闭环：`{summary['unresolved_after_followup']}`",
            f"- LLM 追问辅助采用：`{summary['assist_used']}`",
            f"- 补槽后缺口归因：`{summary['gap_type_breakdown']}`",
            "",
            "## 二、解释",
            "",
            "- 本评测不是把 B 类硬改成 A，而是验证用户补充口径后是否能进入现有受控 query_key。",
            "- 如果补充后仍然澄清，说明当前问题缺的是 query_key、数据口径或业务定义，不应假装已可回答。",
            "- 如果补充后拒答，说明问题实质已越过结构化数据问答边界，应给出业务可理解原因。",
            "- LLM 只用于澄清追问候选，不允许改写最终 A/B/C 边界。",
            "",
            "## 三、后续收口方向",
            "",
            "- 对 `answerable_after_followup` 和 `initial_answerable_migration_candidate` 进入台账迁移复核。",
            "- 对 `still_clarification_after_followup` 按题族拆解缺失 query_key 与缺失业务口径。",
            "- 对 `unsupported_after_followup` 纳入 C 类边界观察池，避免反复进入 B 类治理。",
        ]
    ) + "\n"


def main() -> None:
    """命令行入口。"""

    parser = argparse.ArgumentParser(description="物流 903 B 类补槽后续答闭环评测")
    parser.add_argument("--with-live-llm", action="store_true", help="启用真实 LLM 生成业务化追问。")
    parser.add_argument("--limit", type=int, default=0, help="限制评测题数；0 表示全量 B 类。")
    args = parser.parse_args()
    payload = evaluate(use_live_llm=bool(args.with_live_llm), limit=args.limit)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC_PATH.write_text(_render_doc(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
