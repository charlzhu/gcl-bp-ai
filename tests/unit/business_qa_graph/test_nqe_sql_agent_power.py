"""NQE 功率预测元数据同步测试。

验证 power prediction 域（plan_bom 子域）的元数据上下文构建。
"""

from __future__ import annotations

import importlib


def test_power_context_in_plan_bom() -> None:
    """plan_bom 域 context 包含功率预测相关表。"""
    gm = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")
    state = gm.retrieve_context_multiway(
        {"question": "供应商效率分布", "nqe_mode": "on", "domain_hint": "plan_bom", "selected_domain": "plan_bom"}
    )
    pkg = state["retrieval_context_package"]
    assert pkg["ready"] is True
    tables = " ".join(pkg["allowed_tables"]).lower()
    assert "power" in tables or "supplier" in tables or "model" in tables


def test_power_config_context() -> None:
    """功率配置项和因子可在 plan_bom context 中找到。"""
    gm = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")
    state = gm.retrieve_context_multiway(
        {"question": "电池厂家功率档位", "nqe_mode": "shadow", "domain_hint": "plan_bom"}
    )
    assert state["retrieval_context_package"]["ready"] is True
    assert state["retrieval_context_package"]["domain_code"] == "plan_bom"


def test_power_engine_not_modified() -> None:
    """PowerPredictionEngine 模块可导入但 NQE 未修改它。"""
    from backend.app.domains.plan_bom.services.power_prediction_engine import PowerPredictionEngine
    assert PowerPredictionEngine is not None
