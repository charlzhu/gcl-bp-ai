"""
多候选消歧 API 端点。

业务逻辑：
    提供 POST /api/v1/disambiguation/resolve 端点，
    接收用户消歧选择并返回解析后的候选实体。

    消歧流程：
    1. 前端调用业务问答 API，后端返回 needs_selection 状态 + 候选列表。
    2. 用户从候选列表中选择一项。
    3. 前端调用本端点确认选择，后端返回 resolved 状态 + 选中的实体值。
    4. 前端携带解析后的实体值重新发起业务问答。

约束：
    - 不暴露 SQL、表名、字段名、query_key 等内部技术内容。
    - 不直接执行查询——只解析候选选择。
    - 返回的响应中不包含 LLM 自由文本。
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.app.domains.semantic_catalog.disambiguation.schema import (
    DisambiguationCandidate,
    DisambiguationResolveRequest,
    DisambiguationResolveResponse,
)
from backend.app.domains.semantic_catalog.disambiguation.service import (
    DisambiguationService,
    DisambiguationError,
)

router = APIRouter(prefix="/disambiguation", tags=["Disambiguation"])


@router.post("/resolve", response_model=DisambiguationResolveResponse)
def resolve_disambiguation(
    request: DisambiguationResolveRequest,
) -> DisambiguationResolveResponse:
    """消歧确认端点。

    参数：
        request: 包含 session_id、selected_candidate_id 和原始问题。

    返回：
        DisambiguationResolveResponse，包含解析后的候选实体。

    业务逻辑：
        1. 从前端请求中提取用户选择的 candidate_id。
        2. 调用 DisambiguationService 解析选择。
        3. 返回 resolved 状态和选中的候选实体。

    注：
        当前 MVP 版本中候选列表由前端随请求传入。
        后续可扩展为服务端会话级候选存储。
    """
    svc = DisambiguationService()

    # 从请求中获取候选列表（前端随请求传入）
    candidates = request.candidates

    try:
        resolved = svc.resolve_selection(candidates, request.selected_candidate_id)
    except DisambiguationError as e:
        # 消歧错误：candidate_id 不存在或候选列表为空
        # 返回 400 给前端显示友好错误提示
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=e.message) from e

    return DisambiguationResolveResponse(
        session_id=request.session_id,
        status="resolved",
        selected=resolved,
        original_question=request.original_question,
    )
