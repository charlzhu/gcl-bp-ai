from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.domains.logistics.services.nlu_center_service import LogisticsNluCenterService
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner


CONFIG_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_nlu_center_eval_questions.json"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_nlu_center_eval_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_NLU_CENTER_V1.md"
C2A_PRECISE_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_c_round2_new_a_precise_batches.json"
BCR_BATCH_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_b_candidate_clarification_review_batches.json"
MASTER_LEDGER_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
TOP200_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_top200_questions.json"
TOPN_V2_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_topn_v2_questions.json"


def _load_eval_config(path: Path) -> dict[str, Any]:
    """读取 NLU Center 评测配置。

    参数：
        path: 评测集 JSON 路径。

    返回：
        完整配置字典，包含人工样本和自动扩展来源。
    """

    return json.loads(path.read_text(encoding="utf-8"))


def _load_eval_items(path: Path, *, auto_expand: bool = True) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """读取 NLU Center 评测样本。

    参数：
        path: 评测集 JSON 路径。
        auto_expand: 是否从治理产物自动扩展样本。

    返回：
        评测样本列表和来源分布。
    """

    payload = _load_eval_config(path)
    seed_items = list(payload.get("items", []))
    source_counter: Counter[str] = Counter({"seed": len(seed_items)})
    items = list(seed_items)
    if auto_expand and payload.get("auto_expand_sources", {}).get("enabled", True):
        generated_items = _build_auto_expand_items(payload.get("auto_expand_sources", {}).get("targets", {}))
        existing_questions = {item["question"] for item in items}
        for item in generated_items:
            if item["question"] in existing_questions:
                continue
            items.append(item)
            existing_questions.add(item["question"])
            source_counter[item.get("auto_source", "auto")] += 1
    return items, dict(source_counter)


def _load_json_items(path: Path) -> list[dict[str, Any]]:
    """读取治理产物里的 items 列表。

    参数：
        path: JSON 文件路径。

    返回：
        items 列表；兼容文件本身就是列表的情况。
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return list(payload.get("items", []))


def _query_key_to_intent(query_key: str | None) -> str:
    """把 query_key 映射到统一 intent。

    参数：
        query_key: 当前候选 query_key。

    返回：
        统一 intent 字符串，用于自动生成评测期望。
    """

    if not query_key:
        return "clarification"
    if query_key in {
        "sys_delivery_distance_fill_rate_by_province",
        "sys_parse_success_rate_by_carrier",
        "sys_company_mapping_gap",
    }:
        return "status_quality"
    if "rank" in query_key or "ranking" in query_key or query_key in {
        "hist_total_fee_city_rank",
        "hist_extra_fee_ratio_peak_month",
        "hist_avg_fee_per_watt_by_transport",
        "sys_signedfor_rate_by_carrier",
        "hist_top_customers_fee_and_mw_by_province",
        "hist_customer_mw_ranking",
        "carrier_metric_ranking",
        "sys_task_count_ranking",
    }:
        return "ranking"
    if "compare" in query_key or "deviation" in query_key:
        return "comparison"
    if query_key in {
        "hist_multi_origin_customers",
        "sys_companies_without_tasks",
        "sys_extra_cost_audited_concentration",
        "hist_mw_by_region_province",
        "hist_mw_by_all_regions",
        "sys_mw_by_procurement_type",
    }:
        return "detail"
    return "aggregate"


def _query_key_to_metrics(query_key: str | None, question: str = "") -> list[str]:
    """按 query_key 和问题文本生成宽松指标期望。

    说明：
        1. 自动扩展样本不做精确答案断言，只验证理解层是否抓住关键指标；
        2. 指标列表保持保守，避免把当前不可靠口径误写入评测；
        3. 手工种子样本仍可覆盖更精细指标。
    """

    text = question.upper()
    mapping = {
        "sys_mw_and_trip_count": ["shipment_mw"],
        "hist_mw_summary": ["shipment_mw"],
        "hist_customer_mw": ["shipment_mw"],
        "hist_mw_by_origin_and_carrier": ["shipment_mw"],
        "hist_mw_by_region_province": ["shipment_mw"],
        "hist_mw_by_all_regions": ["shipment_mw"],
        "hist_quantity_by_region": ["shipment_quantity"],
        "hist_trip_count_by_region": ["shipment_trip_count"],
        "hist_vehicle_type_trip_count": ["shipment_trip_count"],
        "hist_total_fee_by_origin_and_carrier": ["total_fee"],
        "hist_total_fee_by_province": ["total_fee"],
        "sys_total_fee_by_filters": ["total_fee"],
        "sys_special_total_fee": ["total_fee"],
        "hist_avg_fee_by_month": ["avg_fee"],
        "hist_route_pricing_analysis": ["avg_fee"],
        "hist_city_carrier_avg_fee_per_trip": ["avg_fee"],
        "hist_unit_fee_per_watt": ["unit_fee_per_watt"],
        "sys_unit_fee_per_watt": ["unit_fee_per_watt"],
        "hist_avg_fee_per_watt_by_transport": ["unit_fee_per_watt"],
        "sys_signedfor_rate_by_carrier": ["signedfor_rate"],
        "sys_delivery_distance_fill_rate_by_province": ["fill_rate"],
        "sys_parse_success_rate_by_carrier": ["parse_success_rate"],
    }
    metrics = list(mapping.get(query_key or "", []))
    if query_key == "sys_mw_and_trip_count" and any(keyword in text for keyword in ("车次", "车数", "多少车", "TRIP")):
        metrics.append("shipment_trip_count")
    return metrics


def _resolve_source_scope(question: str) -> str:
    """按问题文本生成来源层期望。"""

    if "2026" in question or "26年" in question:
        return "system_2026"
    if any(keyword in question for keyword in ("2023", "2024", "2025", "23年", "24年", "25年", "历史", "历史台账")):
        return "historical_2023_2025"
    return "unknown"


def _build_auto_expand_items(targets: dict[str, Any]) -> list[dict[str, Any]]:
    """从治理产物自动生成 NLU 评测样本。

    参数：
        targets: 每个来源期望抽取数量。

    返回：
        自动扩展样本列表。
    """

    items: list[dict[str, Any]] = []
    items.extend(_build_c2a_eval_items(int(targets.get("c2a_precise_a", 0))))
    items.extend(_build_bcr_eval_items(int(targets.get("bcr_clarification", 0))))
    items.extend(_build_ledger_c_eval_items(int(targets.get("ledger_c_unsupported", 0))))
    items.extend(_build_top_a_eval_items(TOP200_PATH, "top200_a", int(targets.get("top200_a", 0))))
    items.extend(_build_top_a_eval_items(TOPN_V2_PATH, "topn_v2_a", int(targets.get("topn_v2_a", 0))))
    return items


def _build_c2a_eval_items(limit: int) -> list[dict[str, Any]]:
    """从 C2A 精确断言计划中抽取 A 类理解样本。"""

    if limit <= 0 or not C2A_PRECISE_PATH.exists():
        return []
    generated: list[dict[str, Any]] = []
    for item in _load_json_items(C2A_PRECISE_PATH):
        question = item.get("question")
        query_key = item.get("query_key")
        if not question or not query_key:
            continue
        # C2A-P3 中有两条预测题已被确认为分层误判，不能再当 A 类样本。
        if any(keyword in question for keyword in ("预测", "未来", "趋势", "波动区间")):
            continue
        generated.append(
            {
                "case_id": f"C2A_{len(generated) + 1:03d}",
                "bucket": "c2a_a_regression",
                "question": question,
                "expected_intent": _query_key_to_intent(query_key),
                "expected_route": "answerable",
                "expected_query_keys": [query_key],
                "expected_metrics": _query_key_to_metrics(query_key, question),
                "expected_source_scope": _resolve_source_scope(question),
                "auto_source": "c2a_precise_a",
                "source_question_id": item.get("question_id"),
                "source_batch_id": item.get("batch_id"),
            }
        )
        if len(generated) >= limit:
            break
    return generated


def _build_bcr_eval_items(limit: int) -> list[dict[str, Any]]:
    """从 BCR 澄清模板复检计划中抽取 B 类理解样本。"""

    if limit <= 0 or not BCR_BATCH_PATH.exists():
        return []
    generated: list[dict[str, Any]] = []
    planner = LogisticsDataQaPlanner()
    for item in _load_json_items(BCR_BATCH_PATH):
        question = item.get("question")
        if not question:
            continue
        # BCR 批次是长期澄清池的来源，但随着 903 全量治理推进，
        # 其中一部分题已经具备稳定 query_key。评测期望必须跟随当前真实 planner，
        # 否则会把“已收口进 A 的题”误判成 false_success。
        plan = planner.build_plan(question)
        if plan.query_key and not plan.needs_clarification and plan.intent != "unsupported":
            expected_intent = _query_key_to_intent(plan.query_key)
            expected_route = "answerable"
            expected_query_keys = [plan.query_key]
            expected_metrics = list(plan.metrics)
        else:
            expected_intent = "clarification"
            expected_route = "clarification"
            expected_query_keys = []
            expected_metrics = []
        generated.append(
            {
                "case_id": f"BCR_{len(generated) + 1:03d}",
                "bucket": "bcr_clarification",
                "question": question,
                "expected_intent": expected_intent,
                "expected_route": expected_route,
                "expected_query_keys": expected_query_keys,
                "expected_metrics": expected_metrics,
                "expected_source_scope": _resolve_source_scope(question),
                "auto_source": "bcr_clarification",
                "source_question_id": item.get("question_id"),
                "source_batch_id": item.get("batch_id"),
            }
        )
        if len(generated) >= limit:
            break
    return generated


def _build_ledger_c_eval_items(limit: int) -> list[dict[str, Any]]:
    """从 903 总账中抽取 C 类边界样本。"""

    if limit <= 0 or not MASTER_LEDGER_PATH.exists():
        return []
    generated: list[dict[str, Any]] = []
    preferred_keywords = ("预测", "预计", "ETA", "到达时间", "设计", "评分模型", "额外费用项目", "原因", "supplier_price", "相关性")
    for item in _load_json_items(MASTER_LEDGER_PATH):
        question = item.get("question")
        if item.get("current_status") != "C" or not question:
            continue
        if not any(keyword in question for keyword in preferred_keywords):
            continue
        generated.append(
            {
                "case_id": f"LEDGER_C_{len(generated) + 1:03d}",
                "bucket": "ledger_c_unsupported",
                "question": question,
                "expected_intent": "unsupported",
                "expected_route": "unsupported",
                "expected_query_keys": [],
                "expected_metrics": [],
                "expected_source_scope": _resolve_source_scope(question),
                "auto_source": "ledger_c_unsupported",
                "source_question_id": item.get("question_id"),
            }
        )
        if len(generated) >= limit:
            break
    return generated


def _build_top_a_eval_items(path: Path, source_name: str, limit: int) -> list[dict[str, Any]]:
    """从 Top200 / TopN v2 中抽取 A 类理解样本。"""

    if limit <= 0 or not path.exists():
        return []
    generated: list[dict[str, Any]] = []
    for item in _load_json_items(path):
        question = item.get("question")
        query_key = item.get("query_key")
        status = item.get("current_classification") or item.get("current_status") or item.get("recommended_status")
        if status != "A" or not question or not query_key:
            continue
        generated.append(
            {
                "case_id": f"{source_name.upper()}_{len(generated) + 1:03d}",
                "bucket": source_name,
                "question": question,
                "expected_intent": _query_key_to_intent(query_key),
                "expected_route": "answerable",
                "expected_query_keys": [query_key],
                "expected_metrics": _query_key_to_metrics(query_key, question),
                "expected_source_scope": _resolve_source_scope(question),
                "auto_source": source_name,
                "source_question_id": item.get("question_id"),
            }
        )
        if len(generated) >= limit:
            break
    return generated


def _contains_all(actual: list[str], expected: list[str]) -> bool:
    """判断实际列表是否覆盖期望列表。

    说明：
        1. 当前采用包含判断，不要求顺序完全一致；
        2. 空期望表示该指标不参与该项评分；
        3. query_key、metric 等结构化槽位均复用此逻辑。
    """

    return all(item in actual for item in expected)


def _evaluate_item(service: LogisticsNluCenterService, item: dict[str, Any], *, use_llm: bool) -> dict[str, Any]:
    """执行单条 NLU 评测。

    参数：
        service: NLU Center 服务实例。
        item: 单条评测样本。
        use_llm: 是否允许真实调用 LLM。

    返回：
        单条评测记录，包含命中情况和风险标记。
    """

    result = service.analyze(item["question"], use_llm=use_llm)
    expected_query_keys = list(item.get("expected_query_keys") or [])
    expected_metrics = list(item.get("expected_metrics") or [])
    expected_multi_intent = bool(item.get("expected_multi_intent", False))
    record = {
        "case_id": item["case_id"],
        "bucket": item["bucket"],
        "question": item["question"],
        "expected": {
            "intent": item.get("expected_intent"),
            "route": item.get("expected_route"),
            "query_keys": expected_query_keys,
            "metrics": expected_metrics,
            "source_scope": item.get("expected_source_scope"),
            "multi_intent": expected_multi_intent,
        },
        "actual": result.model_dump(mode="json"),
        "checks": {
            "intent_hit": result.intent == item.get("expected_intent"),
            "route_hit": result.route_suggestion == item.get("expected_route"),
            "query_key_candidate_hit": _contains_all(result.candidate_query_keys, expected_query_keys),
            "metric_slot_hit": _contains_all(result.metrics, expected_metrics),
            "source_scope_hit": result.source_scope == item.get("expected_source_scope"),
            "multi_intent_hit": result.is_multi_intent == expected_multi_intent,
            "clarification_hit": item.get("expected_route") != "clarification" or result.needs_clarification,
            "unsupported_hit": item.get("expected_route") != "unsupported" or result.unsupported,
            "mis_success": item.get("expected_route") in {"clarification", "unsupported"} and result.route_suggestion == "answerable",
            "mis_unsupported": item.get("expected_route") != "unsupported" and result.unsupported,
            "bc_boundary_changed_by_guardrail": result.guardrail_decision.startswith("assist_applied"),
        },
    }
    return record


def build_report(config_path: Path = CONFIG_PATH, *, use_llm: bool = False, auto_expand: bool = True) -> dict[str, Any]:
    """构建 NLU Center v1 评测报告。

    参数：
        config_path: 评测集路径。
        use_llm: 是否启用真实 LLM 调用。默认关闭，保证本地回归可重复。

    返回：
        评测报告字典。
    """

    service = LogisticsNluCenterService()
    items, source_distribution = _load_eval_items(config_path, auto_expand=auto_expand)
    records = [_evaluate_item(service, item, use_llm=use_llm) for item in items]
    total = len(records)
    bucket_counter = Counter(record["bucket"] for record in records)
    checks = [
        "intent_hit",
        "route_hit",
        "query_key_candidate_hit",
        "metric_slot_hit",
        "source_scope_hit",
        "multi_intent_hit",
        "clarification_hit",
        "unsupported_hit",
    ]
    summary = {
        "total_cases": total,
        "bucket_distribution": dict(bucket_counter),
        "source_distribution": source_distribution,
        "use_live_llm": use_llm,
        "intent_hit_count": sum(1 for record in records if record["checks"]["intent_hit"]),
        "route_hit_count": sum(1 for record in records if record["checks"]["route_hit"]),
        "query_key_candidate_hit_count": sum(1 for record in records if record["checks"]["query_key_candidate_hit"]),
        "metric_slot_hit_count": sum(1 for record in records if record["checks"]["metric_slot_hit"]),
        "source_scope_hit_count": sum(1 for record in records if record["checks"]["source_scope_hit"]),
        "clarification_hit_count": sum(1 for record in records if record["checks"]["clarification_hit"]),
        "unsupported_hit_count": sum(1 for record in records if record["checks"]["unsupported_hit"]),
        "multi_intent_hit_count": sum(1 for record in records if record["checks"]["multi_intent_hit"]),
        "false_success_count": sum(1 for record in records if record["checks"]["mis_success"]),
        "false_unsupported_count": sum(1 for record in records if record["checks"]["mis_unsupported"]),
        "bc_boundary_guardrail_override_count": sum(
            1 for record in records if record["checks"]["bc_boundary_changed_by_guardrail"]
        ),
    }
    for check in checks:
        summary[f"{check}_rate"] = round(
            (sum(1 for record in records if record["checks"][check]) / total) if total else 0,
            4,
        )
    positive_checks = {
        "intent_hit",
        "route_hit",
        "query_key_candidate_hit",
        "metric_slot_hit",
        "source_scope_hit",
        "multi_intent_hit",
        "clarification_hit",
        "unsupported_hit",
    }
    negative_checks = {"mis_success", "mis_unsupported", "bc_boundary_changed_by_guardrail"}
    failed_records = [
        {
            "case_id": record["case_id"],
            "bucket": record["bucket"],
            "question": record["question"],
            "failed_checks": [
                key
                for key, value in record["checks"].items()
                if (key in positive_checks and value is False) or (key in negative_checks and value is True)
            ],
            "actual_intent": record["actual"]["intent"],
            "actual_route": record["actual"]["route_suggestion"],
            "actual_query_keys": record["actual"]["candidate_query_keys"],
            "risk_flags": record["actual"]["risk_flags"],
        }
        for record in records
        if any(
            (key in positive_checks and value is False) or (key in negative_checks and value is True)
            for key, value in record["checks"].items()
        )
    ]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "config_path": str(config_path),
        "summary": summary,
        "eval_items": items,
        "records": records,
        "failed_records": failed_records,
        "conclusion": {
            "nlu_center_ready_for_shadow_diagnostic": summary["false_success_count"] == 0
            and summary["bc_boundary_guardrail_override_count"] == 0,
            "planner_replacement_recommended": False,
            "live_llm_used": use_llm,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    """渲染 NLU Center v1 评测摘要文档。

    参数：
        report: JSON 评测报告。

    返回：
        Markdown 文本。
    """

    summary = report["summary"]
    conclusion = report["conclusion"]
    lines = [
        "# 物流域自然语言理解中枢 v1",
        "",
        "## 结论",
        "",
        "- NLU Center v1 已形成统一 schema、术语归一、规则解析、LLM 候选理解、Guardrail 诊断和多问题拆解 PoC。",
        "- 当前默认是 shadow / diagnostic 模式，不替代正式 `data-qa planner`。",
        "- B/C 边界仍由 `question_bank_response_policy` 和 Guardrail 锁定，LLM 不允许改写最终裁决。",
        "",
        "## 评测规模",
        "",
        f"- 样本总数：{summary['total_cases']}",
        f"- 样本分布：{json.dumps(summary['bucket_distribution'], ensure_ascii=False)}",
        f"- 来源分布：{json.dumps(summary['source_distribution'], ensure_ascii=False)}",
        f"- 是否真实调用 LLM：{summary['use_live_llm']}",
        "",
        "## 指标结果",
        "",
        f"- intent 命中：{summary['intent_hit_count']}/{summary['total_cases']}，命中率 {summary['intent_hit_rate']}",
        f"- route 命中：{summary['route_hit_count']}/{summary['total_cases']}，命中率 {summary['route_hit_rate']}",
        f"- query_key 候选命中：{summary['query_key_candidate_hit_count']}/{summary['total_cases']}，命中率 {summary['query_key_candidate_hit_rate']}",
        f"- metric slot 命中：{summary['metric_slot_hit_count']}/{summary['total_cases']}，命中率 {summary['metric_slot_hit_rate']}",
        f"- source_scope 命中：{summary['source_scope_hit_count']}/{summary['total_cases']}，命中率 {summary['source_scope_hit_rate']}",
        f"- clarification 识别：{summary['clarification_hit_count']}/{summary['total_cases']}，命中率 {summary['clarification_hit_rate']}",
        f"- unsupported 识别：{summary['unsupported_hit_count']}/{summary['total_cases']}，命中率 {summary['unsupported_hit_rate']}",
        f"- 多问题识别：{summary['multi_intent_hit_count']}/{summary['total_cases']}，命中率 {summary['multi_intent_hit_rate']}",
        f"- 误落 success：{summary['false_success_count']}",
        f"- 误落 unsupported：{summary['false_unsupported_count']}",
        f"- Guardrail 改写 B/C 边界：{summary['bc_boundary_guardrail_override_count']}",
        "",
        "## 当前判断",
        "",
        f"- 是否适合 shadow / diagnostic：{conclusion['nlu_center_ready_for_shadow_diagnostic']}",
        f"- 是否建议替换 planner：{conclusion['planner_replacement_recommended']}",
        f"- 是否真实调用 LLM：{conclusion['live_llm_used']}",
        "",
        "## 未命中样本",
        "",
    ]
    if not report["failed_records"]:
        lines.append("- 无。")
    else:
        for record in report["failed_records"]:
            lines.append(
                f"- {record['case_id']}：{record['question']}，失败项={record['failed_checks']}，"
                f"actual_intent={record['actual_intent']}，actual_route={record['actual_route']}，"
                f"query_keys={record['actual_query_keys']}"
            )
    lines.extend(
        [
            "",
            "## 下一步建议",
            "",
            "- 继续保持 NLU Center 诊断模式，滚动扩大真实业务问法、极短问法、多问题和边界样本。",
            "- 公共 `slot_extractor` 已抽取；后续优先根据低命中样本补充统一 slot 规则和术语归一配置。",
            "- 只有当多轮 dry-run 与可选 live LLM 抽样都证明 B/C 边界不被破坏后，再评估小流量 candidate assist。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    """命令行入口。"""

    parser = argparse.ArgumentParser(description="物流域 NLU Center v1 评测")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="NLU 评测集路径")
    parser.add_argument("--output", default=str(REPORT_PATH), help="JSON 报告输出路径")
    parser.add_argument("--doc", default=str(DOC_PATH), help="Markdown 文档输出路径")
    parser.add_argument("--live-llm", "--with-live-llm", action="store_true", help="是否允许真实调用 LLM")
    parser.add_argument("--no-auto-expand", action="store_true", help="只运行人工种子样本，不从治理产物自动扩展")
    args = parser.parse_args()

    report = build_report(Path(args.config), use_llm=args.live_llm, auto_expand=not args.no_auto_expand)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    doc_path = Path(args.doc)
    doc_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
