from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMPONENT_PATH = PROJECT_ROOT / "frontend" / "src" / "views" / "business-chat" / "BusinessChatPage.vue"
SESSION_UTIL_PATH = PROJECT_ROOT / "frontend" / "src" / "utils" / "businessChatSessions.ts"
API_PATH = PROJECT_ROOT / "frontend" / "src" / "api" / "inventorySalesProduction.ts"


def _read(path: Path) -> str:
    """读取前端源码文本。"""

    return path.read_text(encoding="utf-8")


def test_business_chat_has_business_analysis_domain_switch_and_examples() -> None:
    """统一智能问答必须展示经营分析/产销存入口，而不是只能选物流或 BOM。"""

    component = _read(COMPONENT_PATH)
    sessions = _read(SESSION_UTIL_PATH)

    assert "'business_analysis'" in sessions
    assert 'value="business_analysis"' in component
    assert 'data-testid="domain-business-analysis"' in component
    assert "产销存" in component
    assert "经营分析" in component


def test_business_chat_dispatches_inventory_sales_production_to_dedicated_stream_api() -> None:
    """产销存问题必须走独立流式接口，不能落入 BOM 的 else 分支。"""

    component = _read(COMPONENT_PATH)

    assert "streamInventorySalesProductionQuestion" in component
    assert "resolvedDomain === 'business_analysis'" in component
    business_branch = component.index("resolvedDomain === 'business_analysis'")
    plan_bom_branch = component.index("streamPlanBomQuestion")
    assert business_branch < plan_bom_branch


def test_inventory_sales_production_frontend_api_contract() -> None:
    """前端必须提供产销存问答 API 封装，并固定到经营分析后端路由。"""

    assert API_PATH.exists()
    api_text = _read(API_PATH)

    assert "InventorySalesProductionQaPayload" in api_text
    assert "InventorySalesProductionQaResponse" in api_text
    assert "streamInventorySalesProductionQuestion" in api_text
    assert "/business-analysis/inventory-sales-production/qa/ask" in api_text
    assert "/business-analysis/inventory-sales-production/qa/ask/stream" in api_text
