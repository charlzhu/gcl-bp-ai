from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from backend.app.api.deps import get_plan_bom_qa_service
from backend.app.domains.plan_bom.schemas.qa import PlanBomQaRequest
from backend.app.domains.plan_bom.services.qa_service import PlanBomQaService
from backend.app.schemas.common import ApiResponse

router = APIRouter()


@router.post("/ask", response_model=ApiResponse)
def ask_plan_bom(
    payload: PlanBomQaRequest,
    request: Request,
    service: PlanBomQaService = Depends(get_plan_bom_qa_service),
) -> ApiResponse:
    """计划 BOM 自然语言问答入口。

    说明：
        1. 接收用户自然语言问题；
        2. 先执行 BOM NLU Center，再复用已有 detail / compare 查询服务；
        3. 最终返回受控 QA 响应和 presentation；
        4. LLM 只做理解候选与表达优化，不直接生成 BOM 事实。
    """

    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", payload.trace_id or ""))
    result = service.ask(payload.question, use_llm=True, trace_id=trace_id)
    return ApiResponse.success(result.model_dump(mode="json"), trace_id=trace_id)


__all__ = ["router"]
