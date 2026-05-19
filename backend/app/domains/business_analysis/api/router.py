from fastapi import APIRouter

from backend.app.domains.business_analysis.api.endpoints import inventory_sales_production_qa

router = APIRouter()

# 经营分析域当前先接入产销存问答；保持独立前缀，避免影响物流与计划 BOM。
router.include_router(
    inventory_sales_production_qa.router,
    prefix="/inventory-sales-production/qa",
    tags=["Business Analysis - Inventory Sales Production QA"],
)
