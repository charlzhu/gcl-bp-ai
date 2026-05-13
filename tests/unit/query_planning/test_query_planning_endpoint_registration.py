from __future__ import annotations

from fastapi.routing import APIRoute

from backend.app.api.deps import require_query_planning_internal_access
from backend.app.api.router import api_router


def test_query_planning_v2_diagnose_route_is_registered() -> None:
    """内部诊断接口必须注册，但不替换物流/BOM正式问答入口。"""
    paths = {route.path for route in api_router.routes}

    assert "/query-planning/v2/diagnose" in paths
    assert "/query-planning/v2/shadow-report" in paths
    assert "/query-planning/v2/shadow-report/logs" in paths
    assert "/logistics/data-qa/query" in paths
    assert "/plan-bom/qa/ask" in paths


def test_query_planning_v2_log_report_route_keeps_internal_access_guard() -> None:
    """真实日志灰度报表接口必须继续挂内部访问保护，生产环境等待正式权限模块接管。"""
    route = next(
        route
        for route in api_router.routes
        if isinstance(route, APIRoute) and route.path == "/query-planning/v2/shadow-report/logs"
    )

    dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
    assert require_query_planning_internal_access in dependency_calls
