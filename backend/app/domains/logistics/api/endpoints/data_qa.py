from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from backend.app.api.deps import get_logistics_data_qa_service
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.domains.query_planning.services.response_meta_exposure_service import QueryPlanningV2ResponseMetaExposureService
from backend.app.schemas.common import ApiResponse
from backend.app.services.business_answer_stream_service import BusinessAnswerStreamService, build_json_line_event

router = APIRouter()


@router.post("/query", response_model=ApiResponse)
def logistics_data_qa_query(
    payload: LogisticsDataQaQueryRequest,
    request: Request,
    service: LogisticsDataQaService = Depends(get_logistics_data_qa_service),
) -> ApiResponse:
    """物流数据问答入口。"""
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    try:
        result = service.query(payload, trace_id=trace_id)
        result_payload = result.model_dump(mode="json")
        query_plan_v2_meta = QueryPlanningV2ResponseMetaExposureService().build_logistics_meta(
            requested=payload.include_query_plan_v2_meta,
            question=payload.question,
            result=result,
            trace_id=trace_id,
        )
        if query_plan_v2_meta:
            result_payload["query_plan_v2_meta"] = query_plan_v2_meta
        return ApiResponse.success(result_payload, trace_id=trace_id)
    except Exception as exc:  # noqa: BLE001
        # 物流数据问答正式页需要把错误态也纳入查询历史，便于业务回看。
        service.write_error_log(question=payload.question, trace_id=trace_id, message=str(exc))
        raise


@router.post("/query/stream")
def logistics_data_qa_query_stream(
    payload: LogisticsDataQaQueryRequest,
    request: Request,
    service: LogisticsDataQaService = Depends(get_logistics_data_qa_service),
) -> StreamingResponse:
    """物流数据问答流式入口。

    说明：
        1. 先执行原有确定性查询链路，保证计算和表格仍来自后端；
        2. 再把用户问题和确定性结果送入 LLM 表达层，流式输出自然语言答案；
        3. 最终 done 事件返回完整结构化结果，前端据此渲染表格、卡片和追问。
    """

    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    stream_service = BusinessAnswerStreamService()

    def iter_events():
        """逐行输出 NDJSON 事件，便于 fetch ReadableStream 解析。"""

        yield build_json_line_event("meta", {"trace_id": trace_id, "domain": "logistics", "stage": "received"})
        try:
            result = service.query(payload, trace_id=trace_id)
            result_payload = result.model_dump(mode="json")
            yield build_json_line_event(
                "meta",
                {
                    "trace_id": trace_id,
                    "domain": "logistics",
                    "stage": "deterministic_result_ready",
                    "status_code": (result_payload.get("status") or {}).get("code"),
                },
            )
            chunks: list[str] = []
            fallback_answer = result_payload.get("answer_summary")
            presentation = result_payload.get("presentation")
            if isinstance(presentation, dict) and presentation.get("answer"):
                # 流式表达的降级文本优先使用展示层已增强的 narrative，避免 LLM 不可用时退回潦草摘要。
                fallback_answer = presentation.get("answer")
            for chunk in stream_service.stream_answer(
                domain="logistics",
                question=payload.question,
                deterministic_payload=result_payload,
                fallback_answer=fallback_answer,
            ):
                chunks.append(chunk)
                yield build_json_line_event("delta", {"text": chunk})
            final_answer = "".join(chunks).strip()
            final_payload = stream_service.apply_streamed_answer(
                domain="logistics",
                deterministic_payload=result_payload,
                streamed_answer=final_answer,
            )
            query_plan_v2_meta = QueryPlanningV2ResponseMetaExposureService().build_logistics_meta(
                requested=payload.include_query_plan_v2_meta,
                question=payload.question,
                result=result,
                trace_id=trace_id,
            )
            if query_plan_v2_meta:
                final_payload["query_plan_v2_meta"] = query_plan_v2_meta
            yield build_json_line_event(
                "done",
                {"trace_id": trace_id, "domain": "logistics", "answer": final_answer, "data": final_payload},
            )
        except Exception as exc:  # noqa: BLE001
            service.write_error_log(question=payload.question, trace_id=trace_id, message=str(exc))
            yield build_json_line_event(
                "error",
                {
                    "trace_id": trace_id,
                    "domain": "logistics",
                    "message": "当前物流问答执行失败，请稍后重试；如持续失败，请联系管理员。",
                },
            )

    return StreamingResponse(
        iter_events(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
