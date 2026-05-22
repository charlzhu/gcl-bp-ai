from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from backend.app.api.deps import get_inventory_sales_production_qa_service
from backend.app.domains.business_analysis.schemas.inventory_sales_production_qa import (
    InventorySalesProductionQaRequest,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.qa_service import (
    InventorySalesProductionQaService,
)
from backend.app.schemas.common import ApiResponse
from backend.app.services.business_answer_stream_service import BusinessAnswerStreamService, build_json_line_event

router = APIRouter()


@router.post("/ask", response_model=ApiResponse)
def ask_inventory_sales_production(
    payload: InventorySalesProductionQaRequest,
    request: Request,
    service: InventorySalesProductionQaService = Depends(get_inventory_sales_production_qa_service),
) -> ApiResponse:
    """产销存自然语言问答入口。

    说明：
        1. 接收用户自然语言问题；
        2. 先由 M4 临时规划器生成受控 QueryPlan；
        3. 再复用 M3 QueryExecutor 查询中间库并计算结果；
        4. 用户响应不暴露 SQL、表名、字段名、query_key、planner 等内部实现。
    """

    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", payload.trace_id or ""))
    result = service.ask_with_live_gate(payload.question, trace_id=trace_id)
    return ApiResponse.success(result.model_dump(mode="json"), trace_id=trace_id)


@router.post("/ask/stream")
def ask_inventory_sales_production_stream(
    payload: InventorySalesProductionQaRequest,
    request: Request,
    service: InventorySalesProductionQaService = Depends(get_inventory_sales_production_qa_service),
) -> StreamingResponse:
    """产销存自然语言问答流式入口。

    说明：
        1. 确定性产销存查询先执行，事实和表格不由 LLM 改写；
        2. LLM 仅负责在确定性结果上做中文表达增强；
        3. LLM 不可用或输出不安全时，退回 QA 服务给出的业务化确定性摘要。
    """

    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", payload.trace_id or ""))
    stream_service = BusinessAnswerStreamService()

    def iter_events():
        """逐行输出 NDJSON 事件，供前端 fetch ReadableStream 增量消费。"""

        yield build_json_line_event(
            "meta",
            {
                "trace_id": trace_id,
                "domain": "business_analysis",
                "sub_domain": "inventory_sales_production",
                "stage": "received",
            },
        )
        try:
            result = service.ask_with_live_gate(payload.question, trace_id=trace_id)
            result_payload = result.model_dump(mode="json")
            yield build_json_line_event(
                "meta",
                {
                    "trace_id": trace_id,
                    "domain": "business_analysis",
                    "sub_domain": "inventory_sales_production",
                    "stage": "deterministic_result_ready",
                    "status_code": (result_payload.get("status") or {}).get("code"),
                },
            )
            chunks: list[str] = []
            fallback_answer = result_payload.get("answer_summary")
            presentation = result_payload.get("presentation")
            if isinstance(presentation, dict) and presentation.get("answer"):
                fallback_answer = presentation.get("answer")
            for chunk in stream_service.stream_answer(
                domain="business_analysis",
                question=payload.question,
                deterministic_payload=result_payload,
                fallback_answer=fallback_answer,
            ):
                chunks.append(chunk)
                yield build_json_line_event("delta", {"text": chunk})
            final_answer = "".join(chunks).strip()
            final_payload = stream_service.apply_streamed_answer(
                domain="business_analysis",
                deterministic_payload=result_payload,
                streamed_answer=final_answer,
            )
            yield build_json_line_event(
                "done",
                {
                    "trace_id": trace_id,
                    "domain": "business_analysis",
                    "sub_domain": "inventory_sales_production",
                    "answer": final_answer,
                    "data": final_payload,
                },
            )
        except Exception as exc:  # noqa: BLE001
            # 异常仅写内部失败快照；用户可见事件保持业务化，不返回栈、SQL 或表字段。
            service.write_error_log(question=payload.question, trace_id=trace_id, message=str(exc))
            yield build_json_line_event(
                "error",
                {
                    "trace_id": trace_id,
                    "domain": "business_analysis",
                    "sub_domain": "inventory_sales_production",
                    "message": "当前产销存问答执行失败，请稍后重试；如持续失败，请联系管理员。",
                },
            )

    return StreamingResponse(
        iter_events(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


__all__ = ["router"]
