from fastapi import APIRouter

from backend.app.api.v1 import chat, etl, health, logistics_data, logistics_query, system
from backend.app.domains.logistics.api import router as logistics_domain_router
from backend.app.domains.plan_bom.api import router as plan_bom_domain_router

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(system.router, tags=["System"])
api_router.include_router(etl.router, tags=["ETL"])
api_router.include_router(logistics_query.router, tags=["Logistics Query"])
api_router.include_router(logistics_data.router, tags=["Logistics Data"])
api_router.include_router(chat.router, tags=["Chat"])
api_router.include_router(logistics_domain_router.router, prefix="/logistics", tags=["Logistics Domain"])
api_router.include_router(plan_bom_domain_router.router, prefix="/plan-bom", tags=["Plan BOM Domain"])
