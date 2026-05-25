"""LQG-8：统一业务问数流式接口端点。

本端点将物流、计划 BOM（含功率预测/推荐/影响值对比）三条链路统一到
POST /api/v1/business-qa/stream，前端 BusinessChatPage 的
auto/logistics/plan_bom 模式均走本入口。

经营分析/产销存暂不纳入本轮统一入口（继续使用原有独立接口）。

统一流式事件序列：
    received → understanding → plan_ready →
    deterministic_result_ready → answer_streaming (delta) → done

异常时发送 error 事件并终止流。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from backend.app.api.deps import get_logistics_data_qa_service, get_plan_bom_qa_service
from backend.app.domains.business_qa_graph.domain_registry import BusinessQaDomainRegistry
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.domains.plan_bom.schemas.qa import PlanBomQaRequest
from backend.app.domains.plan_bom.services.qa_service import PlanBomQaService
from backend.app.domains.query_planning.services.response_meta_exposure_service import (
    QueryPlanningV2ResponseMetaExposureService,
)
from backend.app.schemas.business_qa import BusinessQaStreamRequest
from backend.app.services.business_answer_stream_service import (
    BusinessAnswerStreamService,
    build_json_line_event,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _nqe_shadow_attach(
    final_payload: dict[str, Any],
    question: str,
    trace_id: str,
    old_result_payload: dict[str, Any],
) -> None:
    """NQE SQL Agent 灰度接入：执行 shadow compare 并附加结果。

    off 模式下直接返回；shadow/assist/on 模式下执行 NQE Graph 并记录。
    执行异常时只记录 warning 日志，不中断用户响应。
    """
    try:
        from backend.app.domains.business_qa_graph.nqe_logistics_gray import (
            build_nqe_shadow_compare_record,
            get_nqe_logistics_mode,
        )

        mode = get_nqe_logistics_mode()
        if mode == "off":
            return

        shadow_record = build_nqe_shadow_compare_record(
            question=question,
            trace_id=trace_id,
            old_result=old_result_payload,
        )
        final_payload["_nqe_shadow"] = {"mode": mode, "record": shadow_record}
    except Exception:
        logger.warning("NQE shadow attach failed (non-blocking), trace_id=%s", trace_id, exc_info=True)


def _nqe_on_mode_query(question: str, trace_id: str, domain: str) -> dict[str, Any] | None:
    """NQE SQL Agent on 模式主链路查询，按域读取独立配置。

    返回 NQE Graph 执行结果；失败时返回 None 触发旧链路 fallback。
    """
    try:
        from backend.app.core.config import settings

        # production 环境强制 off
        if settings.IS_PRODUCTION:
            return None

        # 按域映射独立配置项
        domain_mode_map = {
            "logistics": settings.nqe_logistics_mode,
            "plan_bom": settings.nqe_plan_bom_mode,
            "business_analysis": settings.nqe_business_analysis_mode,
            "power_prediction": settings.nqe_power_prediction_mode,
        }
        mode = domain_mode_map.get(domain, "off")
        if mode != "on":
            return None

        from backend.app.domains.business_qa_graph.nqe_logistics_gray import run_nqe_logistics_graph

        nqe_result = run_nqe_logistics_graph(question, trace_id, nqe_mode="on", domain_hint=domain)
        if nqe_result.get("terminal_status") == "completed":
            structured = nqe_result.get("structured_result", {})
            return {
                "status": structured.get("status", "success"),
                "answer": structured.get("answer", nqe_result.get("user_visible_response", "")),
                "columns": structured.get("columns", []),
                "rows": structured.get("rows", []),
                "row_count": nqe_result.get("row_count", 0),
                "duration_ms": structured.get("duration_ms", 0),
                "domain": domain,
                "trace_id": trace_id,
                "fallback_used": False,
            }
    except Exception:
        logger.warning("NQE on-mode query failed, fallback to legacy, trace_id=%s", trace_id, exc_info=True)
    return None


# ---- 统一流式事件 stage 常量 ----
STAGE_RECEIVED = "received"
STAGE_UNDERSTANDING = "understanding"
STAGE_PLAN_READY = "plan_ready"
STAGE_DETERMINISTIC_RESULT_READY = "deterministic_result_ready"
STAGE_ANSWER_STREAMING = "answer_streaming"
STAGE_DONE = "done"
STAGE_ERROR = "error"


def _logistics_stream_fallback_has_technical_leak(answer: str) -> bool:
    """检查物流流式兜底候选是否包含前端不可见的技术痕迹。"""
    patterns = (
        r"槽位", r"字段", r"表定义", r"库定义", r"数据库",
        r"\bSQL\b", r"\bquery(?:[-_ ]?(?:plan|key)|_key)?\b", r"\bqueryKey\b",
        r"\bplanner\b", r"\bguard\s*rail\b", r"\bguardrail\b",
        r"\braw_result\b", r"\bschema\b", r"\bLLM\b",
        r"\b[a-z]+_[a-z0-9_]+\b",
    )
    return any(re.search(pattern, answer or "", flags=re.I) for pattern in patterns)


def _plan_bom_fallback_has_technical_leak(answer: str) -> bool:
    """检查计划 BOM 流式兜底候选是否包含前端不可见的技术痕迹。"""
    patterns = (
        r"槽位", r"字段", r"表定义", r"库定义", r"数据库",
        r"\bSQL\b", r"\bquery(?:[-_ ]?(?:plan|key)|_key)?\b", r"\bqueryKey\b",
        r"\bplanner\b", r"\bguard\s*rail\b", r"\bguardrail\b",
        r"\braw_result\b", r"\bschema\b", r"\bLLM\b",
        r"\b[a-z]+_[a-z0-9_]+\b",
    )
    return any(re.search(pattern, answer or "", flags=re.I) for pattern in patterns)


def _resolve_logistics_fallback(result_payload: dict) -> str:
    """解析物流确定性兜底文案。"""
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
        if candidate and not _logistics_stream_fallback_has_technical_leak(candidate):
            return candidate
    return "当前物流查询已完成，请查看下方数据依据。"


def _resolve_plan_bom_fallback(result_payload: dict) -> str:
    """解析计划 BOM 确定性兜底文案。"""
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


@router.post("/stream")
def business_qa_stream(
    payload: BusinessQaStreamRequest,
    request: Request,
    logistics_service: LogisticsDataQaService = Depends(get_logistics_data_qa_service),
    plan_bom_service: PlanBomQaService = Depends(get_plan_bom_qa_service),
) -> StreamingResponse:
    """统一业务问数流式入口。

    说明：
        1. 接收用户问题，通过确定性领域路由选择 logistics 或 plan_bom 域；
        2. 调用既有领域服务执行确定性查询；
        3. 将用户问题与确定性结果交给 LLM 流式表达；
        4. done 事件返回完整结构化结果。

    事件序列（NDJSON）：
        - meta / stage=received         ：请求已接收
        - meta / stage=understanding    ：领域识别完成
        - meta / stage=plan_ready       ：查询计划就绪
        - meta / stage=deterministic_result_ready : 确定性查询完成
        - delta / text                  ：LLM 流式表达增量文本
        - done                          ：全部完成，含完整结构化数据
        - error                         ：异常终止
    """

    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    stream_service = BusinessAnswerStreamService()

    def iter_events():
        """逐行输出 NDJSON 事件。"""

        # ---- Stage 1: received ----
        yield build_json_line_event("meta", {
            "stage": STAGE_RECEIVED,
            "trace_id": trace_id,
            "question": payload.question,
            "domain_hint": payload.domain_hint,
        })

        # ---- Stage 2: understanding（领域路由）----
        registry = BusinessQaDomainRegistry.default()
        route_result = registry.route(payload.question, domain_hint=payload.domain_hint)

        yield build_json_line_event("meta", {
            "stage": STAGE_UNDERSTANDING,
            "trace_id": trace_id,
            "domain": route_result.domain,
            "confidence": route_result.confidence,
            "route_status": route_result.status,
        })

        # 无法路由或需要澄清：直接结束，不执行领域服务
        if route_result.status == "CLARIFY":
            yield build_json_line_event("done", {
                "stage": STAGE_DONE,
                "trace_id": trace_id,
                "domain": "unknown",
                "answer": "当前问题无法确定业务域，请选择“物流数据”或“计划 BOM”。",
                "data": {
                    "status": {"code": "needs_domain", "message": "无法确定业务域"},
                    "presentation": {
                        "display_type": "clarification",
                        "title": "需要选择业务域",
                        "answer": "当前问题无法确定业务域，请选择“物流数据”或“计划 BOM”后重试。",
                    },
                },
            })
            return

        # ---- Stage 3: plan_ready ----
        yield build_json_line_event("meta", {
            "stage": STAGE_PLAN_READY,
            "trace_id": trace_id,
            "domain": route_result.domain,
        })

        domain = route_result.domain

        try:
            # ---- Stage 4: 执行领域服务 ----
            if domain == "logistics":
                # NQE-SQL-CUTOVER-2: on 模式优先 NQE SQL Agent
                nqe_on = _nqe_on_mode_query(payload.question, trace_id, domain)
                if nqe_on:
                    yield build_json_line_event("done", nqe_on)
                    return

                result = logistics_service.query(
                    LogisticsDataQaQueryRequest(question=payload.question),
                    trace_id=trace_id,
                )
                result_payload = result.model_dump(mode="json")
                fallback_answer = _resolve_logistics_fallback(result_payload)
                domain_label = "logistics"

                yield build_json_line_event("meta", {
                    "stage": STAGE_DETERMINISTIC_RESULT_READY,
                    "trace_id": trace_id,
                    "domain": domain,
                    "status_code": (result_payload.get("status") or {}).get("code"),
                })

                # ---- Stage 5: LLM 流式表达 ----
                chunks: list[str] = []
                for chunk in stream_service.stream_answer(
                    domain=domain_label,
                    question=payload.question,
                    deterministic_payload=result_payload,
                    fallback_answer=fallback_answer,
                ):
                    chunks.append(chunk)
                    yield build_json_line_event("delta", {"text": chunk})

                final_answer = "".join(chunks).strip()
                final_payload = stream_service.apply_streamed_answer(
                    domain=domain_label,
                    deterministic_payload=result_payload,
                    streamed_answer=final_answer,
                )

                # 附加 query_plan_v2_meta（如果需要）
                query_plan_v2_meta = QueryPlanningV2ResponseMetaExposureService().build_logistics_meta(
                    requested=False,
                    question=payload.question,
                    result=result,
                    trace_id=trace_id,
                )
                if query_plan_v2_meta:
                    final_payload["query_plan_v2_meta"] = query_plan_v2_meta

                # ---- NQE SQL Agent 物流灰度接入 (NQE-SQL-MAIN-16) ----
                # 在 shadow / assist / on 模式下执行 NQE Graph 并记录对比
                _nqe_shadow_attach(final_payload, payload.question, trace_id, result_payload)

            elif domain == "plan_bom":
                # NQE-SQL-CUTOVER-4/5: on 模式优先 NQE SQL Agent
                nqe_on = _nqe_on_mode_query(payload.question, trace_id, "plan_bom")
                if nqe_on:
                    yield build_json_line_event("done", nqe_on)
                    return

                result = plan_bom_service.ask(payload.question, use_llm=True, trace_id=trace_id)
                result_payload = result.model_dump(mode="json")
                fallback_answer = _resolve_plan_bom_fallback(result_payload)
                domain_label = "plan_bom"

                yield build_json_line_event("meta", {
                    "stage": STAGE_DETERMINISTIC_RESULT_READY,
                    "trace_id": trace_id,
                    "domain": domain,
                    "status_code": (result_payload.get("status") or {}).get("code"),
                })

                # ---- Stage 5: LLM 流式表达 ----
                chunks = []
                for chunk in stream_service.stream_answer(
                    domain=domain_label,
                    question=payload.question,
                    deterministic_payload=result_payload,
                    fallback_answer=fallback_answer,
                ):
                    chunks.append(chunk)
                    yield build_json_line_event("delta", {"text": chunk})

                final_answer = "".join(chunks).strip()
                final_payload = stream_service.apply_streamed_answer(
                    domain=domain_label,
                    deterministic_payload=result_payload,
                    streamed_answer=final_answer,
                )

                # 附加 query_plan_v2_meta（如果需要）
                query_plan_v2_meta = QueryPlanningV2ResponseMetaExposureService().build_plan_bom_meta(
                    requested=False,
                    question=payload.question,
                    response=result,
                    trace_id=trace_id,
                )
                if query_plan_v2_meta:
                    final_payload["query_plan_v2_meta"] = query_plan_v2_meta

                # ---- NQE SQL Agent BOM 灰度接入 (NQE-SQL-MAIN-27) ----
                _nqe_shadow_attach(final_payload, payload.question, trace_id, result_payload)

            else:
                # 兜底：未知域（不应到达这里，因为路由已过滤）
                yield build_json_line_event("error", {
                    "stage": STAGE_ERROR,
                    "trace_id": trace_id,
                    "message": "当前问题暂不支持在统一入口查询，请切换到对应业务域页面。",
                })
                return

            # ---- Stage 6: done ----
            yield build_json_line_event("done", {
                "stage": STAGE_DONE,
                "trace_id": trace_id,
                "domain": domain,
                "answer": final_answer,
                "data": final_payload,
            })

        except Exception as exc:  # noqa: BLE001
            logger.exception("统一业务问数流执行异常: domain=%s question=%s", domain, payload.question[:100])

            # 异常时尝试写错误日志（复用领域服务的写日志能力）
            try:
                if domain == "logistics":
                    logistics_service.write_error_log(
                        question=payload.question,
                        trace_id=trace_id,
                        message=str(exc),
                    )
                elif domain == "plan_bom":
                    plan_bom_service.write_error_log(
                        question=payload.question,
                        trace_id=trace_id,
                        message=str(exc),
                    )
            except Exception:
                logger.warning("写错误日志失败，忽略", exc_info=True)

            yield build_json_line_event("error", {
                "stage": STAGE_ERROR,
                "trace_id": trace_id,
                "domain": domain,
                "message": "系统处理您的请求时遇到问题，请稍后重试或联系管理员。",
            })

    return StreamingResponse(
        iter_events(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


__all__ = ["router"]
