from __future__ import annotations

from typing import Any, Literal, TypedDict

from backend.app.domains.business_qa_graph.schemas.domain import BusinessQaCapabilityId, BusinessQaDomainId
from backend.app.domains.business_qa_graph.schemas.request import BusinessQaGraphRequest

DEFAULT_BUSINESS_QA_GRAPH_VERSION = "business_qa_graph.v0"
DEFAULT_BUSINESS_QA_GRAPH_BOUNDARY_NOTES = [
    "本卡仅建立 LangGraph 外层编排骨架，不替代受控 NL2SQL/QueryPlanningV2/SQLPlan。",
    "当前 Graph 只经过 receive 与 domain_route 节点，不进行查数、业务计算、SQL 生成或正式业务执行。",
]


class BusinessQaGraphState(TypedDict, total=False):
    """LangGraph 运行态。

    参数：
        question: 用户原始问题。
        domain_hint: 可选业务域提示。
        trace_id: 请求追踪号。
        trace: 节点事件列表。
        status: 当前骨架状态。
        graph_version: Graph 版本。
        execution_mode: 当前执行模式。
        metadata: 非敏感扩展上下文。
        boundary_notes: 安全边界说明。
        domain: 领域路由结果，无法识别时为 unknown。
        capabilities: 本轮允许进入的 capability 白名单。
        domain_route: 领域路由节点写入的完整审计结构。
    返回：
        StateGraph 节点之间传递的字典态。
    业务逻辑：
        state 只承载编排控制信息，不承载内部 SQL、表字段、raw/debug 或 LLM 自由执行结果。
    """

    question: str
    domain_hint: str | None
    trace_id: str | None
    trace: list[dict[str, Any]]
    status: Literal[
        "PENDING", "RECEIVED", "DOMAIN_ROUTED", "PLAN_BUILT", "UNSUPPORTED", "CLARIFY", "DISABLED", "ERROR", "EXECUTED",
    ]
    graph_version: str
    execution_mode: Literal["graph_skeleton_only", "domain_routing_only", "disabled"]
    metadata: dict[str, Any]
    boundary_notes: list[str]
    domain: BusinessQaDomainId
    capabilities: list[BusinessQaCapabilityId]
    domain_route: dict[str, Any]
    # LQG-3 新增：问题理解和计划构建阶段字段
    shadow_plan_raw: dict[str, Any]
    understanding_status: Literal["PLANNED", "CLARIFY_NEEDED", "UNSUPPORTED", "UNSAFE"]
    # LQG-4 新增：统一校验和边界状态分支字段
    validation_result: Literal["ok", "clarify", "unsupported", "no_answer", "error"]
    """统一校验结果：ok 表示通过，clarify/unsupported/no_answer/error 表示需进入对应终端节点。"""
    validation_details: dict[str, Any]
    """校验详情：包含 missing_slots、unsupported_reason、error_type 等，供终端节点构造业务化消息。"""
    user_visible_message: str
    """用户可见的业务化消息，由终端节点（clarify/unsupported/error）写入。
    必须不包含 SQL、表名、字段名、query_key、planner、guardrail、schema、raw/debug、LLM 等技术细节。"""
    # LQG-5 新增：执行结果字段
    execution_status: Literal["NOT_STARTED", "EXECUTED", "EXECUTION_ERROR"]
    """执行状态：NOT_STARTED 表示尚未执行，EXECUTED 表示执行成功，EXECUTION_ERROR 表示执行异常。"""
    execution_result: dict[str, Any]
    """领域服务执行后的结果快照（不含 SQL/表名/raw/debug）。
    包含 answer_summary、result_table、warnings、needs_clarification 等业务化字段。"""


def build_business_qa_initial_state(request: BusinessQaGraphRequest) -> BusinessQaGraphState:
    """把入口请求转换成 LangGraph 初始 state。

    参数：
        request: 已通过入口校验的 Graph 请求。
    返回：
        可直接传入 compiled graph.invoke 的初始 state。
    业务逻辑：
        初始态显式标注 skeleton-only，避免后续误读为已执行正式业务问数。
    """

    return {
        "question": request.question,
        "domain_hint": request.domain_hint,
        "trace_id": request.trace_id,
        "trace": [],
        "status": "PENDING",
        "graph_version": DEFAULT_BUSINESS_QA_GRAPH_VERSION,
        "execution_mode": "graph_skeleton_only",
        "metadata": dict(request.metadata),
        "boundary_notes": list(DEFAULT_BUSINESS_QA_GRAPH_BOUNDARY_NOTES),
        "domain": "unknown",
        "capabilities": [],
        "domain_route": {},
        # LQG-3 初始字段
        "shadow_plan_raw": {},
        "understanding_status": "UNSAFE",
        # LQG-4 初始字段
        "validation_result": "error",
        "validation_details": {},
        "user_visible_message": "",
        # LQG-5 初始字段
        "execution_status": "NOT_STARTED",
        "execution_result": {},
    }
