"""LQG-5/LQG-6 execute_node：领域服务执行节点。

本节点根据 domain 和校验结果，调用对应领域服务执行业务查询。
当前支持 logistics 域（LogisticsDataQaService）和 plan_bom 域（PlanBomQaService）。
不直接 SQL、不绕过 service/repository 安全边界。
"""

from __future__ import annotations

import logging
from typing import Any

from backend.app.domains.business_qa_graph.schemas.event import BusinessQaGraphEvent
from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState

logger = logging.getLogger(__name__)


def execute_node(
    state: BusinessQaGraphState,
    *,
    logistics_service: Any = None,
    plan_bom_service: Any = None,
) -> BusinessQaGraphState:
    """根据 domain 路由调用对应领域服务执行业务查询。

    参数：
        state: 经过 plan_build 节点（status=PLAN_BUILT）的 Graph 运行态。
        logistics_service: 可注入的物流领域服务，默认构造 LogisticsDataQaService 实例。
        plan_bom_service: 可注入的计划 BOM 领域服务，默认构造 PlanBomQaService 实例。
    返回：
        包含 execution_result 的新 state。
    业务逻辑：
        1. logistics 域且 validation_result=ok 且 understanding_status=PLANNED 时调用 LogisticsDataQaService.query。
        2. plan_bom 域且 validation_result=ok 且 understanding_status=PLANNED 时调用 PlanBomQaService.ask。
        3. 将结果清洗后写入 execution_result，移除 SQL/表名/字段名/raw/debug 等技术细节。
        4. 异常时安全降级为 ERROR 状态，不崩溃。
    """
    # ---- 执行门控：仅 logistics/plan_bom 域且已通过校验且已规划可执行 ----
    # 中文注释：question 由各域执行函数内部从 state 中提取
    domain = state.get("domain", "unknown")
    validation_result = state.get("validation_result", "error")
    understanding_status = state.get("understanding_status", "UNSAFE")
    capabilities = list(state.get("capabilities") or [])
    trace = list(state.get("trace") or [])
    if domain not in ("logistics", "plan_bom"):
        event = BusinessQaGraphEvent(
            node="execute",
            event_type="execution_skipped",
            message=f"业务域 {domain} 非 logistics/plan_bom 域，跳过执行节点。",
            payload={"domain": domain, "reason": "unsupported_domain"},
        )
        next_state: BusinessQaGraphState = dict(state)
        next_state["trace"] = [*trace, event.model_dump(mode="json")]
        return next_state

    if validation_result != "ok":
        event = BusinessQaGraphEvent(
            node="execute",
            event_type="execution_skipped",
            message=f"校验结果={validation_result}，拒绝执行。",
            payload={"validation_result": validation_result, "reason": "validation_not_ok"},
        )
        next_state = dict(state)
        next_state["trace"] = [*trace, event.model_dump(mode="json")]
        return next_state

    if understanding_status != "PLANNED":
        event = BusinessQaGraphEvent(
            node="execute",
            event_type="execution_skipped",
            message=f"understanding_status={understanding_status}，拒绝执行。",
            payload={"understanding_status": understanding_status, "reason": "not_planned"},
        )
        next_state = dict(state)
        next_state["trace"] = [*trace, event.model_dump(mode="json")]
        return next_state

    # ---- 按业务域分支执行 ---- 中文注释：根据 domain 选择对应的领域服务，并传递 capability 信息
    if domain == "logistics":
        return _execute_logistics(state, trace, capabilities, logistics_service)
    if domain == "plan_bom":
        return _execute_plan_bom(state, trace, capabilities, plan_bom_service)

    # 兜底：不应到达这里（门控已拦截非 logistics/plan_bom 域）
    next_state = dict(state)
    next_state["execution_status"] = "NOT_STARTED"
    return next_state


def _execute_logistics(
    state: BusinessQaGraphState,
    trace: list[dict[str, Any]],
    capabilities: list[str],
    logistics_service: Any,
) -> BusinessQaGraphState:
    """执行物流域查询（LQG-5 原有逻辑，提取为独立函数）。

    参数：
        state: Graph 运行态。
        trace: 已有 trace 事件列表。
        capabilities: 当前执行的 capability 列表。
        logistics_service: 注入或默认构造的物流服务实例。
    返回：
        经物流领域服务执行后的新 state。
    """
    domain = state.get("domain", "unknown")

    # ---- 构造或使用已注入的 logistics_service ----
    if logistics_service is None:
        logistics_service = _default_logistics_service()
        if logistics_service is None:
            event = BusinessQaGraphEvent(
                node="execute",
                event_type="execution_skipped",
                message="无法构造 LogisticsDataQaService（可能缺少数据库连接），跳过执行。",
                payload={"domain": domain, "reason": "no_service_available"},
            )
            next_state: BusinessQaGraphState = dict(state)
            next_state["trace"] = [*trace, event.model_dump(mode="json")]
            next_state["execution_status"] = "NOT_STARTED"
            return next_state

    # ---- 执行查询 ----
    try:
        from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest

        result = logistics_service.query(
            LogisticsDataQaQueryRequest(question=str(state.get("question") or "").strip()),
        )
    except Exception as exc:
        logger.exception("execute_node 调用 LogisticsDataQaService 异常")
        return _build_error_state(state, trace, domain, exc, capabilities=capabilities)

    # ---- 清洗结果并写入 state ----
    sanitized = _sanitize_logistics_result(result)

    event = BusinessQaGraphEvent(
        node="execute",
        event_type="execution_complete",
        message=f"物流领域服务执行完成，结果类型={sanitized.get('display_type')}。",
        payload={
            "domain": domain,
            "capabilities": capabilities,  # LQG-7：记录当前执行的 capability 列表
            "row_count": sanitized.get("row_count"),
            "supported": sanitized.get("supported"),
            "needs_clarification": sanitized.get("needs_clarification"),
        },
    )

    next_state = dict(state)
    next_state["trace"] = [*trace, event.model_dump(mode="json")]
    next_state["status"] = "EXECUTED"
    next_state["execution_status"] = "EXECUTED"
    # LQG-7：在执行结果中附加 capability 信息
    sanitized["executed_capabilities"] = capabilities
    next_state["execution_result"] = sanitized
    # 将业务化回答写入 user_visible_message（用于终端展示）
    answer_summary = sanitized.get("answer_summary") or ""
    if sanitized.get("needs_clarification"):
        clarifications = sanitized.get("clarification_questions") or []
        clar_text = "\n".join(f"· {q}" for q in clarifications)
        next_state["user_visible_message"] = f"{answer_summary}\n{clar_text}" if clar_text else answer_summary
    elif not sanitized.get("supported", True):
        next_state["user_visible_message"] = (
            sanitized.get("warnings", [""])[0] if sanitized.get("warnings") else "当前问题暂不支持查询。"
        )
    else:
        next_state["user_visible_message"] = answer_summary

    return next_state


def _execute_plan_bom(
    state: BusinessQaGraphState,
    trace: list[dict[str, Any]],
    capabilities: list[str],
    plan_bom_service: Any,
) -> BusinessQaGraphState:
    """执行计划 BOM 域查询（LQG-6 新增），调用 PlanBomQaService.ask。

    参数：
        state: Graph 运行态。
        trace: 已有 trace 事件列表。
        capabilities: 当前执行的 capability 列表（如 plan_power_prediction）。
        plan_bom_service: 注入或默认构造的计划 BOM 服务实例。
    返回：
        经计划 BOM 领域服务执行后的新 state。
    业务逻辑：
        - 调用 PlanBomQaService.ask(question) 获取 PlanBomQaResponse。
        - 结果经 _sanitize_plan_bom_result 清洗，移除技术细节。
        - user_visible_message 优先使用 presentation.answer（业务化表达），
          避免 answer_summary 泄露槽位/内部字段。
        - LQG-7：trace 事件和执行结果中记录当前 capability，便于审计追踪。
    """
    domain = state.get("domain", "unknown")
    question = str(state.get("question") or "").strip()

    # ---- 构造或使用已注入的 plan_bom_service ----
    if plan_bom_service is None:
        plan_bom_service = _default_plan_bom_service()
        if plan_bom_service is None:
            event = BusinessQaGraphEvent(
                node="execute",
                event_type="execution_skipped",
                message="无法构造 PlanBomQaService（可能缺少数据库连接），跳过执行。",
                payload={"domain": domain, "reason": "no_service_available"},
            )
            next_state: BusinessQaGraphState = dict(state)
            next_state["trace"] = [*trace, event.model_dump(mode="json")]
            next_state["execution_status"] = "NOT_STARTED"
            return next_state

    # ---- 执行查询 ----
    try:
        result = plan_bom_service.ask(question)
    except Exception as exc:
        logger.exception("execute_node 调用 PlanBomQaService 异常")
        return _build_error_state(state, trace, domain, exc, capabilities=capabilities)

    # ---- 清洗结果并写入 state ----
    sanitized = _sanitize_plan_bom_result(result)

    event = BusinessQaGraphEvent(
        node="execute",
        event_type="execution_complete",
        message=f"计划 BOM 领域服务执行完成，capability={capabilities[0] if capabilities else 'unknown'}，结果类型={sanitized.get('display_type')}。",
        payload={
            "domain": domain,
            "capabilities": capabilities,  # LQG-7：记录当前执行的 capability 列表
            "row_count": sanitized.get("row_count"),
            "classification": sanitized.get("classification"),
            "needs_clarification": sanitized.get("needs_clarification"),
        },
    )

    next_state = dict(state)
    next_state["trace"] = [*trace, event.model_dump(mode="json")]
    next_state["status"] = "EXECUTED"
    next_state["execution_status"] = "EXECUTED"
    # LQG-7：在执行结果中附加 capability 信息，便于下游审计
    sanitized["executed_capabilities"] = capabilities
    next_state["execution_result"] = sanitized

    # ---- 用户可见消息：优先 presentation.answer，fallback 到 answer_summary ----
    # 中文注释：Plan BOM 的 answer_summary 可能携带槽位名等内部口径；
    # presentation.answer 是经展示编排层处理后的业务化表达，优先使用
    presentation_answer = sanitized.get("presentation_answer") or ""
    answer_summary = sanitized.get("answer_summary") or ""
    if sanitized.get("needs_clarification"):
        clarifications = sanitized.get("clarification_questions") or []
        clar_text = "\n".join(f"· {q}" for q in clarifications)
        base_text = presentation_answer or answer_summary
        next_state["user_visible_message"] = f"{base_text}\n{clar_text}" if clar_text else base_text
    elif not sanitized.get("supported", True):
        next_state["user_visible_message"] = (
            sanitized.get("warnings", [""])[0] if sanitized.get("warnings") else "当前问题暂不支持查询。"
        )
    else:
        # 正常回答：优先 presentation_answer
        next_state["user_visible_message"] = presentation_answer or answer_summary

    return next_state


def _build_error_state(
    state: BusinessQaGraphState,
    trace: list[dict[str, Any]],
    domain: str,
    exc: Exception,
    *,
    capabilities: list[str] | None = None,
) -> BusinessQaGraphState:
    """构造异常时的安全降级 state。

    参数：
        state: 当前 state。
        trace: 已有 trace 事件列表。
        domain: 当前业务域。
        exc: 捕获的异常。
        capabilities: LQG-7：失败时记录当前 capability，便于审计追踪。
    返回：
        ERROR 状态的新 state。
    业务逻辑：
        用户可见消息不泄露异常类名、traceback 或内部细节。
    """
    event = BusinessQaGraphEvent(
        node="execute",
        event_type="execution_failed",
        message=f"调用领域服务失败：{type(exc).__name__}。",
        payload={
            "domain": domain,
            "error_type": type(exc).__name__,
            "capabilities": capabilities or [],  # LQG-7：记录失败时的 capability
        },
    )
    next_state = dict(state)
    next_state["trace"] = [*trace, event.model_dump(mode="json")]
    next_state["status"] = "ERROR"
    next_state["execution_status"] = "EXECUTION_ERROR"
    # 用户可见消息：业务化表达，不泄露异常细节
    next_state["user_visible_message"] = "系统处理您的请求时遇到问题，请稍后重试或联系管理员。"
    next_state["execution_result"] = {
        "error": True,
        "message": "系统处理请求时遇到问题，请稍后重试。",
        "executed_capabilities": capabilities or [],  # LQG-7：错误结果中也记录 capability
    }
    return next_state


def _sanitize_logistics_result(result: Any) -> dict[str, Any]:
    """从 LogisticsDataQaResult 中提取业务化字段，剔除技术细节（原 _sanitize_result）。

    参数：
        result: LogisticsDataQaService.query 的返回结果。
    返回：
        仅包含业务化字段的字典，不含 SQL/表名/字段名/query_key/raw/debug/planner/guardrail/schema。
    业务逻辑：
        只暴露 answer_summary、result_table（columns/rows/row_count）、
        warnings、needs_clarification、clarification_questions、supported、
        status、display_type、title 等面向用户的字段。
    """
    # 提取 result_table
    result_table = getattr(result, "result_table", None)
    if result_table is not None:
        columns = getattr(result_table, "columns", []) or []
        rows = getattr(result_table, "rows", []) or []
        row_count = getattr(result_table, "row_count", len(rows))
    else:
        columns, rows, row_count = [], [], 0

    # 提取 status
    status_obj = getattr(result, "status", None)
    status_code = getattr(status_obj, "code", "unknown") if status_obj else "unknown"
    status_success = getattr(status_obj, "success", False) if status_obj else False

    # 提取 presentation
    presentation = getattr(result, "presentation", None)
    display_type = getattr(presentation, "display_type", "narrative") if presentation else "narrative"
    title = getattr(presentation, "title", "") if presentation else ""

    # 提取 warnings
    warnings = list(getattr(result, "warnings", []) or [])

    # 提取 clarification_questions
    clarification_questions = list(getattr(result, "clarification_questions", []) or [])

    # 提取 calculation_logic
    calculation_logic = list(getattr(result, "calculation_logic", []) or [])

    # 提取 trace_events（仅保留数量，不暴露细节）
    trace_events = getattr(result, "trace_events", None)
    trace_count = len(trace_events) if trace_events else 0

    return {
        "answer_summary": str(getattr(result, "answer_summary", "") or ""),
        "columns": list(columns),
        "rows": list(rows),
        "row_count": row_count,
        "warnings": warnings,
        "needs_clarification": bool(getattr(result, "needs_clarification", False)),
        "clarification_questions": clarification_questions,
        "supported": bool(getattr(result, "supported", True)),
        "status_code": status_code,
        "status_success": status_success,
        "display_type": display_type,
        "title": title,
        "calculation_logic": calculation_logic,
        "history_log_id": getattr(result, "history_log_id", None),
        "history_ready": bool(getattr(result, "history_ready", False)),
        "trace_count": trace_count,
    }


def _default_logistics_service() -> Any:
    """构造默认 LogisticsDataQaService 实例。

    参数：无。
    返回：
        LogisticsDataQaService 实例，或 None（构造失败时）。
    业务逻辑：
        默认构造需要数据库连接；若环境不可达（测试/缺 .env/DB 不可达）则返回 None，
        由 execute_node 的安全降级机制处理。
        注意：构造成功后 DB session 生命周期由 execute_node 调用者管理。
    """
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService

        db = SessionLocal()
        return LogisticsDataQaService(db=db)
    except Exception:
        logger.warning("无法构造默认 LogisticsDataQaService（可能缺少数据库连接），将跳过执行。", exc_info=True)
        return None


def _sanitize_plan_bom_result(result: Any) -> dict[str, Any]:
    """从 PlanBomQaResponse 中提取业务化字段，剔除技术细节（LQG-6 新增）。

    参数：
        result: PlanBomQaService.ask 的返回结果（PlanBomQaResponse）。
    返回：
        仅包含业务化字段的字典，不含 SQL/表名/字段名/query_key/planner/raw/debug/nlu。
    业务逻辑：
        - 只暴露 answer_summary、presentation_answer、result_table（columns/rows）、
          warnings、needs_clarification、clarification_questions、classification、
          status_code、display_type、title 等面向用户的字段。
        - nlu（含 slots/missing_slots/guardrail_notes）、raw_result、
          trace_events 等技术细节不暴露。
    """
    # 提取 result_table
    result_table = getattr(result, "result_table", None)
    if result_table is not None:
        columns = getattr(result_table, "columns", []) or []
        rows = getattr(result_table, "rows", []) or []
    else:
        columns, rows = [], []

    # 提取 status
    status_obj = getattr(result, "status", None)
    status_code = getattr(status_obj, "code", "unknown") if status_obj else "unknown"

    # 提取 presentation（优先获取 presentation.answer 作为业务化表达）
    presentation = getattr(result, "presentation", None)
    display_type = getattr(presentation, "display_type", "narrative") if presentation else "narrative"
    title = getattr(presentation, "title", "") if presentation else ""
    # 中文注释：presentation.answer 是业务化表达，优先于 answer_summary
    presentation_answer = getattr(presentation, "answer", "") if presentation else ""

    # 提取 warnings
    warnings = list(getattr(result, "warnings", []) or [])

    # 提取 clarification_questions
    clarification_questions = list(getattr(result, "clarification_questions", []) or [])

    # 提取 calculation_logic（BOM 域通常无此字段，保留用于一致性）
    calculation_logic = list(getattr(result, "calculation_logic", []) or [])

    return {
        "answer_summary": str(getattr(result, "answer_summary", "") or ""),
        "presentation_answer": str(presentation_answer or ""),
        "columns": list(columns),
        "rows": list(rows),
        "row_count": len(rows),
        "warnings": warnings,
        "needs_clarification": bool(getattr(result, "needs_clarification", False)),
        "clarification_questions": clarification_questions,
        "classification": str(getattr(result, "classification", "") or ""),
        "status_code": status_code,
        "display_type": display_type,
        "title": title,
        "calculation_logic": calculation_logic,
        # 不暴露的字段：nlu、raw_result、trace_events、query_key
        "supported": True,  # PlanBomQaResponse 隐含 supported=True
    }


def _default_plan_bom_service() -> Any:
    """构造默认 PlanBomQaService 实例（LQG-6 新增）。

    参数：无。
    返回：
        PlanBomQaService 实例，或 None（构造失败时）。
    业务逻辑：
        默认构造需要数据库连接；若环境不可达（测试/缺 .env/DB 不可达）则返回 None，
        由 execute_node 的安全降级机制处理。
        注意：构造成功后 DB session 生命周期由 execute_node 调用者管理。
    """
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.domains.plan_bom.repositories.query_repository import PlanBomQueryRepository
        from backend.app.domains.plan_bom.services.nlu_center_service import PlanBomNluCenterService
        from backend.app.domains.plan_bom.services.answer_presentation_service import PlanBomAnswerPresentationService
        from backend.app.domains.plan_bom.services.query_service import PlanBomQueryService
        from backend.app.domains.plan_bom.services.qa_service import PlanBomQaService

        db = SessionLocal()
        repository = PlanBomQueryRepository(db)
        return PlanBomQaService(
            repository=repository,
            query_service=PlanBomQueryService(repository=repository),
            nlu_service=PlanBomNluCenterService(repository=repository),
            presentation_service=PlanBomAnswerPresentationService(),
        )
    except Exception:
        logger.warning("无法构造默认 PlanBomQaService（可能缺少数据库连接），将跳过执行。", exc_info=True)
        return None
