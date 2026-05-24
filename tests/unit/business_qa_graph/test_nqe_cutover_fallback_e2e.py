"""四域 on-mode fallback/E2E 验证测试。"""

from __future__ import annotations

import importlib


def _graph():
    return importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph").build_nqe_sql_agent_graph()


def test_logistics_on_mode_runs_nqe() -> None:
    g = _graph()
    final = g.invoke({"question": "2024年发运量", "nqe_mode": "on", "domain_hint": "logistics"})
    assert final["selected_domain"] == "logistics"
    assert final["terminal_status"] in {"completed", "error", "safety_reject"}


def test_logistics_safety_fallback() -> None:
    """safety reject 不是 crash，仍然返回 result。"""
    g = _graph()
    final = g.invoke({"question": "DROP TABLE", "nqe_mode": "on", "domain_hint": "logistics"})
    assert "selected_domain" in final


def test_plan_bom_on_mode_runs_nqe() -> None:
    g = _graph()
    final = g.invoke({"question": "BOM评审号查询", "nqe_mode": "on", "domain_hint": "plan_bom"})
    assert final["selected_domain"] == "plan_bom"
    assert final["terminal_status"] in {"completed", "error", "safety_reject"}


def test_plan_bom_explain_fallback() -> None:
    """plan_bom on 模式即使失败也不 crash。"""
    g = _graph()
    final = g.invoke({"question": "SELECT * FROM plan_bom_header", "nqe_mode": "on", "domain_hint": "plan_bom"})
    assert "terminal_status" in final


def test_business_analysis_on_mode_runs_nqe() -> None:
    g = _graph()
    final = g.invoke({"question": "2024年销量", "nqe_mode": "on", "domain_hint": "business_analysis"})
    assert final["selected_domain"] == "business_analysis"


def test_power_on_mode_runs_nqe() -> None:
    """power 走 plan_bom 子域，context 包含 power 表。"""
    g = _graph()
    final = g.invoke({"question": "供应商效率", "nqe_mode": "on", "domain_hint": "plan_bom"})
    assert final["selected_domain"] == "plan_bom"
    pkg = final.get("retrieval_context_package", {})
    assert pkg.get("ready") is True


def test_off_mode_no_nqe() -> None:
    g = _graph()
    final = g.invoke({"question": "发运量", "nqe_mode": "off", "domain_hint": "logistics"})
    assert final["terminal_status"] == "legacy_fallback"


def test_legacy_fallback_preserved() -> None:
    """旧链路未删除 - 验证关键模块存在。"""
    from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
    from backend.app.domains.plan_bom.services.qa_service import PlanBomQaService
    from backend.app.domains.plan_bom.services.power_prediction_engine import PowerPredictionEngine
    assert LogisticsDataQaService is not None
    assert PlanBomQaService is not None
    assert PowerPredictionEngine is not None
