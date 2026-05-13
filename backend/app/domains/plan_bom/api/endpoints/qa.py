from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from backend.app.api.deps import get_plan_bom_qa_service
from backend.app.domains.plan_bom.schemas.qa import PlanBomQaRequest
from backend.app.domains.plan_bom.services.qa_service import PlanBomQaService
from backend.app.domains.query_planning.services.response_meta_exposure_service import QueryPlanningV2ResponseMetaExposureService
from backend.app.schemas.common import ApiResponse
from backend.app.services.business_answer_stream_service import BusinessAnswerStreamService, build_json_line_event

router = APIRouter()


def _plan_bom_fallback_has_technical_leak(answer: str) -> bool:
    """检查计划 BOM 流式兜底候选是否包含前端不可见的技术痕迹。"""

    patterns = (
        r"槽位",
        r"字段",
        r"表定义",
        r"库定义",
        r"数据库",
        r"\bSQL\b",
        r"\bquery(?:[-_ ]?(?:plan|key)|_key)?\b",
        r"\bqueryKey\b",
        r"\bplanner\b",
        r"\bguard\s*rail\b",
        r"\bguardrail\b",
        r"\braw_result\b",
        r"\bschema\b",
        r"\bLLM\b",
        r"\b[a-z]+_[a-z0-9_]+\b",
    )
    return any(re.search(pattern, answer or "", flags=re.I) for pattern in patterns)


def _resolve_plan_bom_stream_fallback_answer(result_payload: dict) -> str:
    """解析 Plan BOM 流式回答的确定性兜底文案。

    参数：
        result_payload: `PlanBomQaResponse.model_dump` 后的确定性响应快照。

    返回：
        可直接流式输出给业务员的安全兜底文本。

    业务逻辑：
        Plan BOM 的 `answer_summary` 可能携带槽位名等内部口径；若展示层已经生成
        `presentation.answer`，流式降级应优先使用业务化表达，避免前端看到内部术语。
    """

    presentation = result_payload.get("presentation") if isinstance(result_payload, dict) else None
    candidates: list[str] = []
    if isinstance(presentation, dict) and presentation.get("answer"):
        candidates.append(str(presentation["answer"]))
    if isinstance(result_payload, dict) and result_payload.get("answer_summary"):
        candidates.append(str(result_payload["answer_summary"]))
    status = result_payload.get("status") if isinstance(result_payload, dict) else None
    if isinstance(status, dict) and status.get("message"):
        candidates.append(str(status["message"]))
    for candidate in candidates:
        if candidate and not _plan_bom_fallback_has_technical_leak(candidate):
            return candidate
    return "当前计划 BOM 查询已完成，我会基于已导入的数据整理结论；请查看下方数据依据。"


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
    try:
        result = service.ask(payload.question, use_llm=True, trace_id=trace_id)
        result_payload = result.model_dump(mode="json")
        query_plan_v2_meta = QueryPlanningV2ResponseMetaExposureService().build_plan_bom_meta(
            requested=payload.include_query_plan_v2_meta,
            question=payload.question,
            response=result,
            trace_id=trace_id,
        )
        if query_plan_v2_meta:
            result_payload["query_plan_v2_meta"] = query_plan_v2_meta
        return ApiResponse.success(result_payload, trace_id=trace_id)
    except Exception as exc:  # noqa: BLE001
        # 计划 BOM 问答与物流问答使用同一张 sys_query_log；异常也要留存，便于业务回看失败问题。
        service.write_error_log(question=payload.question, trace_id=trace_id, message=str(exc))
        raise


@router.post("/ask/stream")
def ask_plan_bom_stream(
    payload: PlanBomQaRequest,
    request: Request,
    service: PlanBomQaService = Depends(get_plan_bom_qa_service),
) -> StreamingResponse:
    """计划 BOM 自然语言问答流式入口。

    说明：
        1. 确定性 BOM/NLU/功率模型链路先执行，保证事实和数值可追溯；
        2. 把用户原问题和确定性响应快照交给 LLM，只生成更自然的答案表达；
        3. done 事件返回完整结构化结果，表格和状态不由 LLM 改写。
    """

    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", payload.trace_id or ""))
    stream_service = BusinessAnswerStreamService()

    def iter_events():
        """逐行输出 NDJSON 事件，供前端 fetch 流式消费。"""

        yield build_json_line_event("meta", {"trace_id": trace_id, "domain": "plan_bom", "stage": "received"})
        try:
            result = service.ask(payload.question, use_llm=True, trace_id=trace_id)
            result_payload = result.model_dump(mode="json")
            yield build_json_line_event(
                "meta",
                {
                    "trace_id": trace_id,
                    "domain": "plan_bom",
                    "stage": "deterministic_result_ready",
                    "status_code": (result_payload.get("status") or {}).get("code"),
                },
            )
            chunks: list[str] = []
            fallback_answer = _resolve_plan_bom_stream_fallback_answer(result_payload)
            for chunk in stream_service.stream_answer(
                domain="plan_bom",
                question=payload.question,
                deterministic_payload=result_payload,
                fallback_answer=fallback_answer,
            ):
                chunks.append(chunk)
                yield build_json_line_event("delta", {"text": chunk})
            final_answer = "".join(chunks).strip()
            final_payload = stream_service.apply_streamed_answer(
                domain="plan_bom",
                deterministic_payload=result_payload,
                streamed_answer=final_answer,
            )
            query_plan_v2_meta = QueryPlanningV2ResponseMetaExposureService().build_plan_bom_meta(
                requested=payload.include_query_plan_v2_meta,
                question=payload.question,
                response=result,
                trace_id=trace_id,
            )
            if query_plan_v2_meta:
                final_payload["query_plan_v2_meta"] = query_plan_v2_meta
            yield build_json_line_event(
                "done",
                {"trace_id": trace_id, "domain": "plan_bom", "answer": final_answer, "data": final_payload},
            )
        except Exception as exc:  # noqa: BLE001
            service.write_error_log(question=payload.question, trace_id=trace_id, message=str(exc))
            yield build_json_line_event(
                "error",
                {
                    "trace_id": trace_id,
                    "domain": "plan_bom",
                    "message": "当前计划 BOM 问答执行失败，请稍后重试；如持续失败，请联系管理员。",
                },
            )

    return StreamingResponse(
        iter_events(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


__all__ = ["router", "_resolve_plan_bom_stream_fallback_answer"]
