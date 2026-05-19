from backend.app.api.router import api_router


def test_business_analysis_inventory_sales_production_qa_routes_registered() -> None:
    """经营分析产销存问答接口必须注册到统一 API 路由。"""

    paths = {getattr(route, "path", "") for route in api_router.routes}

    assert "/business-analysis/inventory-sales-production/qa/ask" in paths
    assert "/business-analysis/inventory-sales-production/qa/ask/stream" in paths
