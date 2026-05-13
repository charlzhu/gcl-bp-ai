from __future__ import annotations

from backend.app.api.router import api_router


def test_query_planning_v2_diagnose_route_is_registered() -> None:
    """内部诊断接口必须注册，但不替换物流/BOM正式问答入口。"""
    paths = {route.path for route in api_router.routes}

    assert "/query-planning/v2/diagnose" in paths
    assert "/query-planning/v2/shadow-report" in paths
    assert "/logistics/data-qa/query" in paths
    assert "/plan-bom/qa/ask" in paths
