"""LQG-4 plan_validate_node：统一安全校验门。

本节点对 shadow_plan_raw 执行策略校验，决定后续路由：
  - ok → 进入后续执行节点（plan_build / 执行）
  - clarify → 进入 clarify_node 生成业务化追问
  - unsupported → 进入 unsupported_node 生成业务化拒答
  - error → 进入 error_node 安全降级

本节点不查库、不执行 SQL、不调用 LLM，只做确定性校验。
"""

from __future__ import annotations

import json
from typing import Any

from backend.app.domains.business_qa_graph.schemas.event import BusinessQaGraphEvent
from backend.app.domains.business_qa_graph.schemas.policy import (
    PlanValidationResult,
    check_missing_slots,
    detect_safety_danger,
    detect_tech_leak,
    is_capability_allowed,
    is_domain_allowed,
)
from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState

# 技术泄露阻断时的业务化说明（不能包含 SQL/表名/字段名等）
_TECH_LEAK_CLARIFICATION = (
    "您的提问包含了系统不支持的操作方式。请使用业务语言描述您要查询的内容，"
    "例如：「2024 年合肥物流发运量是多少？」或「订单 00104 用了什么材料？」"
)

# 安全危险阻断时的业务化说明
_SAFETY_DANGER_UNSUPPORTED = (
    "您的提问涉及系统不支持的操作，无法继续处理。"
    "如需查询业务数据，请使用自然语言描述您的需求。"
)

# 域不在白名单时的业务化说明
_DOMAIN_UNSUPPORTED = (
    "您的问题暂不在当前系统覆盖的业务范围内。"
    "当前支持物流运输数据查询和计划 BOM 材料查询，如需其他业务支持请联系管理员。"
)


def plan_validate_node(state: BusinessQaGraphState) -> BusinessQaGraphState:
    """对 shadow_plan 执行统一安全校验，决定后续路由。

    参数：
        state: 包含 question、domain、shadow_plan_raw 的 Graph 运行态。
    返回：
        写入 validation_result 和 validation_details 的新 state。
    业务逻辑：
        1. 先对原始 question 做技术泄露 / 安全危险检测（最高优先级）。
        2. 检查 domain 是否在白名单内。
        3. 检查 understanding_status 是否为 UNSAFE/UNSUPPORTED/CLARIFY_NEEDED。
        4. 检查必填槽位是否缺失。
        5. 所有阻断都写入业务化消息，不暴露内部标识。
    """
    question = str(state.get("question") or "").strip()
    domain = state.get("domain", "unknown")
    trace = list(state.get("trace") or [])
    understanding_status = state.get("understanding_status", "UNSAFE")
    shadow_plan_raw = state.get("shadow_plan_raw") or {}
    capabilities = state.get("capabilities") or []

    # ---- 第一步：原始问题安全检测（最高优先级） ----
    # 1a. 技术泄露检测
    if detect_tech_leak(question):
        return _block_tech_leak(state, question, trace)

    # 1b. SQL 注入等安全危险检测
    if detect_safety_danger(question):
        return _block_safety_danger(state, question, trace)

    # ---- 第二步：domain 白名单校验 ----
    if not is_domain_allowed(domain):
        return _block_unsupported_domain(state, domain, trace)

    # ---- 第三步：understanding_status 分类处理 ----
    if understanding_status == "UNSAFE":
        return _block_unsafe(state, question, trace)

    if understanding_status == "UNSUPPORTED":
        unsupported_reason = shadow_plan_raw.get("unsupported_reason", _DOMAIN_UNSUPPORTED)
        return _block_unsupported(state, unsupported_reason, trace)

    if understanding_status == "CLARIFY_NEEDED":
        missing_slots = shadow_plan_raw.get("missing_slots", []) or []
        clarification_questions = shadow_plan_raw.get("clarification_questions", []) or []
        return _route_clarify(state, missing_slots, clarification_questions, trace)

    # NQE-S2：COMPOSITE_DECOMPOSED 状态是合法状态，跳过必填槽位校验
    # （每个子计划的完整性由 decomposition_node 保证）
    if understanding_status == "COMPOSITE_DECOMPOSED":
        return _route_ok(state, trace)

    # ---- 第四步：必填槽位校验 ----
    intent = shadow_plan_raw.get("intent", "")
    slots = shadow_plan_raw.get("slots", {}) or {}
    missing = check_missing_slots(intent, slots)
    if missing:
        # 将内部槽位名映射为业务化中文标签，避免暴露技术标识
        slot_labels = {
            "order_id": "订单号",
            "bom_file": "BOM 文件",
            "supplier_name": "供应商名称",
            "material_name": "物料名称",
        }
        missing_labels = [str(slot_labels.get(s, s)) for s in missing]
        clarification_questions = [f"请补充以下信息：{'、'.join(missing_labels)}"]
        return _route_clarify(state, missing, clarification_questions, trace)

    # ---- 第五步：通过所有校验 ----
    return _route_ok(state, trace)


def _block_tech_leak(state: BusinessQaGraphState, question: str, trace: list) -> BusinessQaGraphState:
    """技术泄露阻断：生成业务化拒答，不暴露检测规则。"""
    result = PlanValidationResult(
        validation_result="unsupported",
        unsupported_reason=_TECH_LEAK_CLARIFICATION,
        tech_leak_blocked=True,
        blocked_details={"trigger": "tech_leak_detected"},
    )
    return _finalize(state, result, trace, "plan_validate_tech_leak")


def _block_safety_danger(state: BusinessQaGraphState, question: str, trace: list) -> BusinessQaGraphState:
    """安全危险阻断：生成业务化拒答。"""
    result = PlanValidationResult(
        validation_result="unsupported",
        unsupported_reason=_SAFETY_DANGER_UNSUPPORTED,
        safety_blocked=True,
        blocked_details={"trigger": "safety_danger_detected"},
    )
    return _finalize(state, result, trace, "plan_validate_safety_block")


def _block_unsupported_domain(
    state: BusinessQaGraphState, domain: str, trace: list
) -> BusinessQaGraphState:
    """域不在白名单：返回 unsupported。"""
    result = PlanValidationResult(
        validation_result="unsupported",
        unsupported_reason=_DOMAIN_UNSUPPORTED,
        blocked_details={"domain": domain, "trigger": "domain_not_allowed"},
    )
    return _finalize(state, result, trace, "plan_validate_unsupported")


def _block_unsafe(state: BusinessQaGraphState, question: str, trace: list) -> BusinessQaGraphState:
    """UNSAFE 状态：视为不安全，返回 clarify 以便人工介入。"""
    result = PlanValidationResult(
        validation_result="clarify",
        clarification_reason="您的提问需要进一步确认，请提供更多业务信息。",
        blocked_details={"understanding_status": "UNSAFE"},
    )
    return _finalize(state, result, trace, "plan_validate_unsafe")


def _block_unsupported(
    state: BusinessQaGraphState, unsupported_reason: str, trace: list
) -> BusinessQaGraphState:
    """UNSUPPORTED 策略：返回 unsupported。"""
    result = PlanValidationResult(
        validation_result="unsupported",
        unsupported_reason=unsupported_reason or _DOMAIN_UNSUPPORTED,
        blocked_details={"understanding_status": "UNSUPPORTED"},
    )
    return _finalize(state, result, trace, "plan_validate_unsupported")


def _route_clarify(
    state: BusinessQaGraphState,
    missing_slots: list[str],
    clarification_questions: list[str],
    trace: list,
) -> BusinessQaGraphState:
    """CLARIFY_NEEDED 策略：返回 clarify。"""
    # 构造业务化追问文本（不暴露 slot 名称）
    if clarification_questions:
        reason = "; ".join(clarification_questions)
    else:
        reason = "缺少必要信息，请补充查询条件后再试。"
    result = PlanValidationResult(
        validation_result="clarify",
        missing_slots=missing_slots,
        clarification_reason=reason,
    )
    return _finalize(state, result, trace, "plan_validate_clarify")


def _route_ok(state: BusinessQaGraphState, trace: list) -> BusinessQaGraphState:
    """通过所有校验。"""
    result = PlanValidationResult(validation_result="ok")
    return _finalize(state, result, trace, "plan_validate_ok")


def _finalize(
    state: BusinessQaGraphState,
    result: PlanValidationResult,
    trace: list,
    event_type: str,
) -> BusinessQaGraphState:
    """写入校验结果到 state，添加 trace 事件。

    参数：
        state: 当前 Graph 运行态。
        result: PlanValidationResult 校验结果。
        trace: 已有 trace 列表。
        event_type: 事件类型标识。
    返回：
        写入 validation_result 和 validation_details 的新 state。
    """
    event = BusinessQaGraphEvent(
        node="plan_validate",
        event_type=event_type,
        message=f"校验结果: {result.validation_result}",
        payload={
            "validation_result": result.validation_result,
            "tech_leak_blocked": result.tech_leak_blocked,
            "safety_blocked": result.safety_blocked,
        },
    )

    next_state = dict(state)
    next_state["trace"] = [*trace, event.model_dump(mode="json")]
    next_state["validation_result"] = result.validation_result
    next_state["validation_details"] = result.model_dump(mode="json")
    return next_state
