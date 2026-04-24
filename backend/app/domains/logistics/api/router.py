from fastapi import APIRouter

from backend.app.domains.logistics.api.endpoints import (
    data_qa,
    import_history,
    nl2query,
    query,
    rag,
    refresh_serving,
    sync_system,
)

router = APIRouter()
router.include_router(import_history.router, prefix="/history-import")
router.include_router(sync_system.router, prefix="/system-sync")
router.include_router(query.router, prefix="/query-service")
router.include_router(nl2query.router, prefix="/nl2query")
router.include_router(data_qa.router, prefix="/data-qa")
router.include_router(rag.router, prefix="/rag")
router.include_router(refresh_serving.router, prefix="/serving-refresh")
