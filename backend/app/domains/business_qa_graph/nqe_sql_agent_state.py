"""NQE 统一 SQL Agent Graph 运行态定义。

本模块只定义独立骨架的状态字段，不接入正式问答入口、不连接数据库、
不调用真实模型，也不承载用户可见的内部执行细节。
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict


NqeMode = Literal["off", "shadow", "assist", "on"]
NqeTerminalStatus = Literal["clarify", "safety_reject", "error", "legacy_fallback", "completed"]


class NqeSqlAgentState(TypedDict, total=False):
    """NQE SQL Agent LangGraph 节点之间传递的状态。

    参数：
        所有字段均由 Graph 节点按阶段增量写入；调用方可传入 question、
        nqe_mode、retrieval_context_package 等测试态字段驱动骨架分支。
    返回：
        StateGraph 节点之间共享和更新的字典态。
    业务边界：
        本状态允许保存内部占位执行信息，但用户可见回答只能写入
        user_visible_response，且必须屏蔽内部技术词。
    """

    # 请求上下文：用户原始问题。
    question: str
    # 请求上下文：归一化后的业务问题文本。
    normalized_question: str
    # 请求上下文：调用方提供的业务域提示。
    domain_hint: str | None
    # 请求上下文：前端、渠道或会话侧非敏感上下文。
    client_context: dict[str, Any]
    # 请求上下文：用户身份、权限候选等非敏感上下文。
    user_context: dict[str, Any]
    # 请求上下文：本次请求的追踪号，不应暴露给用户。
    trace_id: str | None

    # trace：节点审计轨迹，只记录节点名、状态和业务摘要。
    trace_steps: list[dict[str, str]]
    # trace：脱敏查询日志记录，不包含内部候选查询文本。
    query_log_record: dict[str, Any]
    # trace：内部可重放记录，保存最小重放输入和期望摘要。
    replay_record: dict[str, Any]
    # trace：重放结果摘要，仅用于内部验收对比。
    replay_summary: dict[str, Any]

    # 运行模式：NQE 灰度总开关，off/shadow/assist/on。
    nqe_mode: NqeMode
    # 运行模式：领域级灰度模式，未设置时继承 nqe_mode。
    domain_mode: NqeMode
    # 运行模式：降级策略，例如 legacy_first 或 nqe_first。
    fallback_policy: str
    # 运行模式：Graph 骨架版本。
    graph_version: str
    # 运行模式：元数据版本标识，仅作追溯占位。
    metadata_version_id: str | None
    # 运行模式：表达模板版本标识，仅作追溯占位。
    prompt_version_id: str | None

    # 领域：已选择的业务域。
    selected_domain: str | None
    # 领域：已选择的业务能力。
    selected_capability: str | None
    # 领域：候选业务域列表。
    domain_candidates: list[dict[str, Any]]
    # 领域：候选业务能力列表。
    capability_candidates: list[dict[str, Any]]

    # 理解：关键词候选。
    keyword_terms: list[str]
    # 理解：实体候选。
    entity_terms: list[str]
    # 理解：指标候选。
    metric_terms: list[str]
    # 理解：时间候选。
    time_terms: list[str]
    # 理解：对比条件候选。
    compare_terms: list[str]

    # 召回：用于元数据召回的查询文本。
    retrieval_query: str
    # 召回：多路召回候选。
    retrieval_candidates: list[dict[str, Any]]
    # 召回：合并排序后的上下文包；本卡只支持测试注入占位包。
    retrieval_context_package: dict[str, Any]
    # 召回：上下文是否满足生成占位查询的要求。
    context_readiness: Literal["unknown", "pass", "fail"]
    # 召回：需要用户补充的信息提示。
    clarification_hints: list[str]
    # 召回：降级提示。
    fallback_hints: list[str]

    # SQL 生命周期：内部候选查询文本，禁止直接展示给用户。
    generated_sql: str
    # SQL 生命周期：通过安全预检后的内部候选文本。
    safe_sql_candidate: str
    # SQL 生命周期：安全预检结构化结果。
    sql_safety_result: dict[str, Any]
    # SQL 生命周期：解释校验占位结果。
    explain_result: dict[str, Any]
    # SQL 生命周期：当前修正轮次，最多 2 轮。
    sql_revision_round: int
    # SQL 生命周期：修正记录摘要，不记录用户可见技术细节。
    sql_revisions: list[dict[str, Any]]
    # SQL 生命周期：最近一次修正原因。
    correction_reason: str | None

    # 执行：内部执行结果占位，不连接真实数据库。
    execution_result_internal: dict[str, Any]
    # 执行：执行状态。
    execution_status: Literal["not_started", "skipped", "executed", "failed"]
    # 执行：结果行数占位。
    row_count: int
    # 执行：结果是否被截断。
    result_truncated: bool

    # 输出：用户可见的业务化回答。
    user_visible_response: str
    # 输出：Graph 终态。
    terminal_status: NqeTerminalStatus
    # 输出：降级或终止原因。
    fallback_reason: str | None
    # 输出：shadow 对比占位结果，不进入用户可见回答。
    shadow_compare_result: dict[str, Any]

    # 测试控制：强制安全预检拒绝，用于覆盖 safety_reject 终态。
    force_safety_reject: bool
    # 测试控制：强制解释校验失败，用于覆盖修正循环。
    force_explain_fail: bool
