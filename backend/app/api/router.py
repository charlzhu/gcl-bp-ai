from fastapi import APIRouter

from backend.app.api.v1 import business_qa, chat, etl, health, logistics_data, logistics_query, system, zg_query, nqe
from backend.app.domains.business_analysis.api import router as business_analysis_domain_router
from backend.app.domains.logistics.api import router as logistics_domain_router
from backend.app.domains.plan_bom.api import router as plan_bom_domain_router
from backend.app.domains.query_planning.api import router as query_planning_domain_router
from backend.app.domains.semantic_catalog.api import router as semantic_catalog_router

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(system.router, tags=["System"])
api_router.include_router(etl.router, tags=["ETL"])
api_router.include_router(logistics_query.router, tags=["Logistics Query"])
api_router.include_router(logistics_data.router, tags=["Logistics Data"])
api_router.include_router(chat.router, tags=["Chat"])
api_router.include_router(logistics_domain_router.router, prefix="/logistics", tags=["Logistics Domain"])
api_router.include_router(plan_bom_domain_router.router, prefix="/plan-bom", tags=["Plan BOM Domain"])
api_router.include_router(business_analysis_domain_router, prefix="/business-analysis", tags=["Business Analysis Domain"])
api_router.include_router(query_planning_domain_router, prefix="/query-planning", tags=["Query Planning V2"])
api_router.include_router(business_qa.router, prefix="/business-qa", tags=["Business QA"])
api_router.include_router(zg_query.zg_router, prefix="/v1", tags=["掌柜问数对齐版(ZG)"])
api_router.include_router(nqe.router, prefix="/nqe", tags=["NQE SQL Agent"])
