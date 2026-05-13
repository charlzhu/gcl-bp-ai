from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from backend.app.domains.query_planning.services.shadow_report_service import QueryPlanningV2ShadowReportService


class _NoExecutionPlanningService:
    """测试占位 planning service，真实日志运营验收不应重新执行诊断规划。"""

    def plan(self, **_: Any) -> None:
        raise AssertionError("Phase 5.4 运营验收只能基于真实日志报表，不允许重新执行 Query Planning。")


class _FakeGrayLogRepository:
    """测试用只读日志仓储。"""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def list_query_logs_for_query_planning_gray(
        self,
        db: object,
        *,
        domain: str = "all",
        limit: int = 200,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        return self.rows


def _row(
    log_id: int,
    *,
    domain: str,
    status: str,
    formal_query_key: str | None,
    shadow_strategy: str | None,
    shadow_query_key: str | None,
    execution_policy: dict[str, Any] | None = None,
    guardrail_decision: dict[str, Any] | None = None,
    payload_override: str | None = None,
) -> dict[str, Any]:
    """构造最小 sys_query_log 行，便于测试运营验收指标。"""

    if payload_override is None:
        payload: dict[str, Any] = {
            "question": f"问题{log_id}",
            "response_meta": {"domain": domain, "metric_type": formal_query_key},
            "query_result": {"query_plan": {"query_key": formal_query_key}},
        }
        if shadow_strategy is not None:
            payload["query_plan_v2_shadow"] = {
                "schema_version": "query_plan_v2.0",
                "domain": domain,
                "original_question": f"问题{log_id}",
                "strategy": shadow_strategy,
                "intent": "aggregate",
                "query_key": shadow_query_key,
                "slots": {"filters": {"year": 2025}},
                "guardrail_decision": guardrail_decision or {"accepted": True, "blocked_reason": None},
                "execution_policy": execution_policy
                or {"shadow_only": True, "llm_can_execute": False, "sql_generation_allowed": False},
            }
        request_payload = json.dumps(payload, ensure_ascii=False)
    else:
        request_payload = payload_override

    return {
        "id": log_id,
        "trace_id": f"trace-{log_id}",
        "query_type": "DATA_QA" if domain == "logistics" else "PLAN_BOM_QA",
        "question_text": f"问题{log_id}",
        "request_payload": request_payload,
        "route_type": "data_qa" if domain == "logistics" else "plan_bom_qa",
        "metric_type": formal_query_key,
        "result_count": 1,
        "status": status,
        "message": "ok",
        "created_at": datetime(2026, 5, 13, 10, log_id, 0),
    }


def _service(rows: list[dict[str, Any]]) -> QueryPlanningV2ShadowReportService:
    return QueryPlanningV2ShadowReportService(
        planning_service=_NoExecutionPlanningService(),
        query_log_repository=_FakeGrayLogRepository(rows),
        db=object(),
    )


def test_gray_log_report_acceptance_gate_passes_when_operational_thresholds_are_met() -> None:
    """Phase 5.4 应在真实日志报表中给出可运营验收的 PASS 门槛结论。"""
    report = _service(
        [
            _row(
                1,
                domain="logistics",
                status="SUCCESS",
                formal_query_key="hist_mw_by_carrier",
                shadow_strategy="DIRECT_RETRIEVAL",
                shadow_query_key="hist_mw_by_carrier",
            ),
            _row(
                2,
                domain="plan_bom",
                status="SUCCESS",
                formal_query_key="single_order_material_specs",
                shadow_strategy="DIRECT_RETRIEVAL",
                shadow_query_key="single_order_material_specs",
            ),
            _row(
                3,
                domain="logistics",
                status="CLARIFICATION",
                formal_query_key=None,
                shadow_strategy="CLARIFY",
                shadow_query_key=None,
            ),
            _row(
                4,
                domain="logistics",
                status="UNSUPPORTED",
                formal_query_key=None,
                shadow_strategy="UNSUPPORTED",
                shadow_query_key=None,
            ),
        ]
    ).build_log_report(domain="all", limit=20, days=7)

    assert report.acceptance_gate.status == "PASS"
    assert report.acceptance_gate.passed is True
    assert report.acceptance_gate.eligible_for_controlled_rollout is True
    assert report.acceptance_gate.blocking_reasons == []
    assert report.acceptance_gate.thresholds.min_shadow_coverage_rate == 0.95
    assert report.acceptance_gate.thresholds.min_query_key_match_rate == 0.98
    assert any(check.metric == "shadow_coverage_rate" and check.passed for check in report.acceptance_gate.checks)
    assert any(check.metric == "query_key_match_rate" and check.passed for check in report.acceptance_gate.checks)


def test_gray_log_report_acceptance_gate_blocks_when_thresholds_or_bc_boundaries_fail() -> None:
    """Phase 5.4 应把覆盖率不足、B/C 边界分歧和危险执行策略列为运营验收阻断。"""
    report = _service(
        [
            _row(
                1,
                domain="logistics",
                status="SUCCESS",
                formal_query_key="hist_mw_by_carrier",
                shadow_strategy="DIRECT_RETRIEVAL",
                shadow_query_key="hist_total_fee_by_carrier",
            ),
            _row(
                2,
                domain="logistics",
                status="UNSUPPORTED",
                formal_query_key=None,
                shadow_strategy="DIRECT_RETRIEVAL",
                shadow_query_key="hist_mw_summary",
            ),
            _row(
                3,
                domain="plan_bom",
                status="SUCCESS",
                formal_query_key="single_order_material_specs",
                shadow_strategy=None,
                shadow_query_key=None,
            ),
            _row(
                4,
                domain="logistics",
                status="SUCCESS",
                formal_query_key="hist_mw_summary",
                shadow_strategy="DIRECT_RETRIEVAL",
                shadow_query_key="hist_mw_summary",
                execution_policy={"shadow_only": False, "llm_can_execute": True, "sql_generation_allowed": True},
            ),
        ]
    ).build_log_report(domain="all", limit=20, days=7)

    assert report.acceptance_gate.status == "BLOCKED"
    assert report.acceptance_gate.passed is False
    assert report.acceptance_gate.eligible_for_controlled_rollout is False
    assert "shadow_coverage_rate 未达到 95.00%" in report.acceptance_gate.blocking_reasons
    assert "query_key_match_rate 未达到 98.00%" in report.acceptance_gate.blocking_reasons
    assert "unsupported_disagreement_count 超过允许值 0" in report.acceptance_gate.blocking_reasons
    assert "unsafe_execution_policy_count 超过允许值 0" in report.acceptance_gate.blocking_reasons
    assert any("先修复 BLOCKED" in action for action in report.acceptance_gate.recommended_actions)


def test_gray_log_report_contains_chart_ready_visualization_without_raw_payload() -> None:
    """Phase 5.4 报表应直接提供运营看板可用的 KPI/图表数据，且不暴露原始 payload。"""
    report = _service(
        [
            _row(
                1,
                domain="logistics",
                status="SUCCESS",
                formal_query_key="hist_mw_by_carrier",
                shadow_strategy="DIRECT_RETRIEVAL",
                shadow_query_key="hist_mw_by_carrier",
            ),
            _row(
                2,
                domain="plan_bom",
                status="CLARIFICATION",
                formal_query_key=None,
                shadow_strategy="CLARIFY",
                shadow_query_key=None,
            ),
        ]
    ).build_log_report(domain="all", limit=20, days=7)

    kpi_keys = {card.key for card in report.visualization.kpi_cards}
    assert {"shadow_coverage_rate", "query_key_match_rate", "risk_blocker_count"}.issubset(kpi_keys)
    chart_keys = {chart.key for chart in report.visualization.charts}
    assert {"strategy_distribution", "domain_distribution", "status_distribution", "risk_bucket_counts"}.issubset(
        chart_keys
    )
    strategy_chart = next(chart for chart in report.visualization.charts if chart.key == "strategy_distribution")
    assert {point.name: point.value for point in strategy_chart.points} == {"DIRECT_RETRIEVAL": 1, "CLARIFY": 1}
    risk_chart = next(chart for chart in report.visualization.charts if chart.key == "risk_bucket_counts")
    assert all(point.value == 0 for point in risk_chart.points)
    assert all(sample.raw_payload is None for sample in report.samples)
    assert report.visualization.raw_payload is None


def test_gray_log_report_visualization_marks_query_key_kpi_neutral_when_no_comparable_query_keys() -> None:
    """没有可比 query_key 时，运营看板不应把 query_key 一致率误标为危险。"""
    report = _service(
        [
            _row(
                1,
                domain="logistics",
                status="CLARIFICATION",
                formal_query_key=None,
                shadow_strategy="CLARIFY",
                shadow_query_key=None,
            ),
            _row(
                2,
                domain="plan_bom",
                status="UNSUPPORTED",
                formal_query_key=None,
                shadow_strategy="UNSUPPORTED",
                shadow_query_key=None,
            ),
        ]
    ).build_log_report(domain="all", limit=20, days=7)

    query_key_card = next(card for card in report.visualization.kpi_cards if card.key == "query_key_match_rate")
    assert query_key_card.value == "N/A"
    assert query_key_card.status == "neutral"
    assert report.acceptance_gate.status == "PASS"


def test_gray_log_report_guardrail_blocked_is_watch_not_blocked() -> None:
    """guardrail 阻断候选应进入 WATCH 观察，不应自动等同于可执行受控接入。"""
    report = _service(
        [
            _row(
                1,
                domain="logistics",
                status="SUCCESS",
                formal_query_key="hist_mw_summary",
                shadow_strategy="DIRECT_RETRIEVAL",
                shadow_query_key="hist_mw_summary",
                guardrail_decision={"accepted": False, "blocked_reason": "候选超出白名单"},
            )
        ]
    ).build_log_report(domain="all", limit=20, days=7)

    assert report.acceptance_gate.status == "WATCH"
    assert report.acceptance_gate.blocking_reasons == []
    assert "guardrail_blocked_count 超过允许值 0" in report.acceptance_gate.watch_reasons
    assert [item.log_id for item in report.risk_buckets["guardrail_blocked"]] == [1]


def test_gray_log_report_corrupt_payload_and_clarify_disagreement_block_operational_acceptance() -> None:
    """损坏 payload 与澄清边界分歧必须作为运营验收阻断项。"""
    report = _service(
        [
            _row(
                1,
                domain="logistics",
                status="SUCCESS",
                formal_query_key="hist_mw_summary",
                shadow_strategy=None,
                shadow_query_key=None,
                payload_override="{bad json",
            ),
            _row(
                2,
                domain="plan_bom",
                status="CLARIFICATION",
                formal_query_key=None,
                shadow_strategy="DIRECT_RETRIEVAL",
                shadow_query_key="single_order_material_specs",
            ),
        ]
    ).build_log_report(domain="all", limit=20, days=7)

    assert report.acceptance_gate.status == "BLOCKED"
    assert "corrupt_payload_count 超过允许值 0" in report.acceptance_gate.blocking_reasons
    assert "clarify_disagreement_count 超过允许值 0" in report.acceptance_gate.blocking_reasons
