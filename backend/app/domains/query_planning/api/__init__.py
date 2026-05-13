from __future__ import annotations

from fastapi import APIRouter

from backend.app.domains.query_planning.api.endpoints import query_plan_v2

router = APIRouter()
router.include_router(query_plan_v2.router, tags=["Query Planning V2"])

__all__ = ["router"]
