from fastapi import APIRouter

from backend.app.domains.plan_bom.api.endpoints import import_excel, qa, query

router = APIRouter()

# 当前注册 Excel 入库、自然语言问答、基础查询和 compare 端点；仍复用既有 BOM 查询服务。
router.include_router(import_excel.router)
router.include_router(import_excel.router, prefix="/import")
router.include_router(qa.router, prefix="/qa")
router.include_router(query.router, prefix="/query")
