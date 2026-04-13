from fastapi import APIRouter

from backend.app.domains.logistics.api.endpoints import (
    import_history,
    nl2query,
    query,
    refresh_serving,
    sync_system,
)

router = APIRouter()
router.include_router(import_history.router, prefix="/history-import")
router.include_router(sync_system.router, prefix="/system-sync")
router.include_router(query.router, prefix="/query-service")
router.include_router(nl2query.router, prefix="/nl2query")
router.include_router(refresh_serving.router, prefix="/serving-refresh")
