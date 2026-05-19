"""产销存服务包。

说明：
    子模块之间存在 parser -> repository -> import_service 的分层依赖，
    因此包初始化只导出轻量问答服务，避免导入解析器造成循环依赖。
"""

from backend.app.domains.business_analysis.services.inventory_sales_production.qa_service import (
    InventorySalesProductionQaService,
)

__all__ = ["InventorySalesProductionQaService"]
