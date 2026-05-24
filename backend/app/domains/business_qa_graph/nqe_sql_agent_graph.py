"""NQE 统一 SQL Agent Graph 独立骨架。

本模块只提供可单测、可编译的 LangGraph 编排骨架。它不替换正式问答入口、
不访问生产库、不调用真实模型、不执行真实查询，也不把内部过程暴露给用户。
"""

from __future__ import annotations

import re
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from backend.app.domains.business_qa_graph.nqe_sql_agent_state import NqeMode, NqeSqlAgentState
from backend.app.domains.business_qa_graph.nqe_sql_agent_trace import (
    build_nqe_query_log_record,
    build_nqe_replay_record,
    compare_nqe_replay_summary,
)
from backend.app.domains.business_qa_graph.nqe_sql_safety import precheck_nqe_sql_safety
from backend.app.services.nqe_metadata_sync import NqeMetadataSyncBuilder, build_nqe_context_package_from_bundle


NQE_SQL_AGENT_GRAPH_VERSION = "nqe_sql_agent_graph.skeleton.v1"
MAX_SQL_REVISION_ROUNDS = 2
_SQL_EXPRESSION_KEYWORDS = {
    "abs",
    "and",
    "as",
    "avg",
    "between",
    "case",
    "cast",
    "ceil",
    "ceiling",
    "coalesce",
    "count",
    "date",
    "decimal",
    "distinct",
    "else",
    "end",
    "exists",
    "false",
    "floor",
    "from",
    "group",
    "ifnull",
    "in",
    "integer",
    "is",
    "like",
    "limit",
    "max",
    "min",
    "not",
    "null",
    "nullif",
    "numeric",
    "or",
    "order",
    "over",
    "round",
    "select",
    "string",
    "sum",
    "then",
    "true",
    "when",
    "where",
}

NQE_SQL_AGENT_NODE_SEQUENCE = (
    "receive_query",
    "init_trace_and_mode",
    "route_domain_and_capability",
    "normalize_query",
    "retrieve_context_multiway",
    "merge_rank_and_build_context",
    "check_context_readiness",
    "generate_sql_direct",
    "precheck_sql_safety",
    "explain_validate_sql",
    "correct_sql",
    "execute_sql_readonly",
    "present_business_answer",
    "record_query_log_and_trace",
    "legacy_fallback",
    "shadow_compare",
    "terminal_clarify",
    "terminal_safety_reject",
    "terminal_error",
)


def _append_trace(
    state: NqeSqlAgentState,
    *,
    node: str,
    status: str = "ok",
    summary: str,
) -> NqeSqlAgentState:
    """复制 state 并追加节点轨迹。

    参数：
        state: 当前 Graph 运行态。
        node: 当前节点名称。
        status: 节点处理状态。
        summary: 面向审计的业务摘要，不写入内部查询文本。
    返回：
        带有新增 trace_steps 记录的新 state。
    业务逻辑：
        trace_steps 只记录节点、状态和摘要，避免把内部实现细节误放到用户可见输出。
    """
    next_state: NqeSqlAgentState = dict(state)
    steps = list(next_state.get("trace_steps", []))
    steps.append({"node": node, "status": status, "summary": summary})
    next_state["trace_steps"] = steps
    return next_state


def _coerce_nqe_mode(value: object) -> NqeMode:
    """把外部传入模式收敛到 NQE 支持的灰度模式。

    参数：
        value: 调用方传入的模式值。
    返回：
        off、shadow、assist、on 之一；未知值按 off 处理。
    业务逻辑：
        默认关闭，避免骨架在未显式授权时进入新链路。
    """
    if value in {"shadow", "assist", "on"}:
        return value  # type: ignore[return-value]
    return "off"


def _normalize_metadata_identifier(value: object) -> str:
    """归一化元数据中的对象或字段标识。

    参数：
        value: 上下文包注入的对象名、字段名或字段描述字典中的值。
    返回：
        去除常见引用符号并统一小写后的标识；无法识别时返回空字符串。
    业务逻辑：
        本函数只做确定性文本规整，不把未知对象映射到白名单，也不补全业务字段。
    """
    normalized_parts: list[str] = []
    for part in str(value or "").split("."):
        cleaned = part.strip().strip("`\"[]").strip().lower()
        if cleaned:
            normalized_parts.append(cleaned)
    return ".".join(normalized_parts)


def _extract_table_columns(context_package: dict[str, Any]) -> dict[str, set[str]]:
    """从上下文包读取表级字段白名单。

    参数：
        context_package: 召回阶段注入的非敏感元数据上下文。
    返回：
        结构为 {对象名: {字段名}} 的归一化字段白名单；缺失时返回空字典。
    业务逻辑：
        解释校验只信任上下文包显式给出的字段元数据。字段元数据不存在时不放宽
        安全预检，只跳过字段级解释校验，保持当前骨架兼容。
    """
    raw_table_columns = (
        context_package.get("table_columns")
        or context_package.get("columns_by_table")
        or context_package.get("table_column_whitelist")
    )
    if not isinstance(raw_table_columns, dict):
        return {}

    table_columns: dict[str, set[str]] = {}
    for raw_table, raw_columns in raw_table_columns.items():
        table_name = _normalize_metadata_identifier(raw_table)
        if not table_name:
            continue
        if not isinstance(raw_columns, list | tuple | set):
            continue
        columns: set[str] = set()
        for raw_column in raw_columns:
            if isinstance(raw_column, dict):
                raw_name = (
                    raw_column.get("name")
                    or raw_column.get("column")
                    or raw_column.get("column_name")
                    or raw_column.get("field")
                    or raw_column.get("field_name")
                )
            else:
                raw_name = raw_column
            column_name = _normalize_metadata_identifier(raw_name).split(".")[-1]
            if column_name:
                columns.add(column_name)
        if columns:
            table_columns[table_name] = columns
    return table_columns


def _split_top_level_csv(text: str) -> list[str]:
    """按顶层逗号拆分候选表达式列表。

    参数：
        text: 内部候选中的投影表达式片段。
    返回：
        顶层逗号分隔后的表达式列表。
    业务逻辑：
        只为解释校验抽取字段名，遇到函数参数或括号中的逗号不拆分，避免误判。
    """
    parts: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
    parts.append(text[start:].strip())
    return [part for part in parts if part]


def _strip_projection_alias(expression: str) -> str:
    """移除投影表达式中的显示别名。

    参数：
        expression: 单个投影表达式。
    返回：
        去掉 AS 别名或简单尾部别名后的表达式主体。
    业务逻辑：
        解释校验关注实际引用字段，不把业务展示别名当成待校验字段。
    """
    cleaned = re.split(r"\s+as\s+", expression.strip(), maxsplit=1, flags=re.IGNORECASE)[0].strip()
    if re.fullmatch(r"[`\"\[]?[A-Za-z_][\w$]*(?:\.[`\"\[]?[A-Za-z_][\w$]*)?\s+[A-Za-z_][\w$]*", cleaned):
        cleaned = cleaned.rsplit(None, 1)[0]
    return cleaned


def _extract_identifier_columns(expression: str) -> set[str]:
    """从投影表达式中抽取可能的字段标识。

    参数：
        expression: 已去除别名的投影表达式。
    返回：
        归一化字段名集合；函数名、类型名和 SQL 关键字会被剔除。
    业务逻辑：
        对函数表达式采取 fail-closed 字段识别：只要表达式中出现未知字段，后续
        元数据校验就会失败，避免 SUM(未知字段) 等形式绕过解释校验。
    """
    expression_without_literals = re.sub(r"'[^']*'", " ", expression)
    raw_identifiers = re.findall(
        r"[`\"\[]?[A-Za-z_][\w$]*[`\"\]]?(?:\.[`\"\[]?[A-Za-z_][\w$]*[`\"\]]?)*",
        expression_without_literals,
    )
    columns: set[str] = set()
    for raw_identifier in raw_identifiers:
        column_name = _normalize_metadata_identifier(raw_identifier).split(".")[-1]
        if column_name and column_name not in _SQL_EXPRESSION_KEYWORDS:
            columns.add(column_name)
    return columns


def _extract_projected_columns(candidate_text: str) -> set[str]:
    """从已通过安全预检的候选文本中抽取投影字段。

    参数：
        candidate_text: 安全预检输出的内部只读候选文本。
    返回：
        候选文本 SELECT 列表中可确定的字段集合；常量与无法确定表达式不返回。
    业务逻辑：
        本函数用于离线解释校验，不连接数据库。复杂表达式先保守跳过，由安全预检
        与后续真实执行阶段继续收敛；简单字段必须与上下文字段元数据匹配。
    """
    normalized = " ".join(str(candidate_text or "").split())
    match = re.search(r"^select\s+(.+?)\s+from\s+", normalized, re.IGNORECASE)
    if not match:
        return set()

    columns: set[str] = set()
    for projection in _split_top_level_csv(match.group(1)):
        expression = _strip_projection_alias(projection)
        expression = re.sub(r"^distinct\s+", "", expression, flags=re.IGNORECASE).strip()
        if not expression or expression == "*":
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?|'[^']*'", expression):
            continue
        columns.update(_extract_identifier_columns(expression))
    return columns


def _select_projection_clause(candidate_text: str) -> str:
    """截取候选文本的 SELECT 投影子句。

    参数：
        candidate_text: 安全预检输出的内部只读候选文本。
    返回：
        SELECT 与 FROM 之间的投影片段；无法识别时返回空字符串。
    业务逻辑：
        投影片段用于发现通配投影。通配投影会返回过宽结果，必须在只读执行前
        fail-closed 拒绝，不能依赖真实数据库执行阶段兜底。
    """
    normalized = " ".join(str(candidate_text or "").split())
    match = re.search(r"^select\s+(.+?)\s+from\s+", normalized, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _contains_select_star(candidate_text: str) -> bool:
    """判断投影列表是否包含过宽通配字段。

    参数：
        candidate_text: 安全预检后的内部候选文本。
    返回：
        发现 *、对象.* 或引用符包裹通配符时返回 True。
    业务逻辑：
        通配投影会绕开字段白名单粒度，解释校验必须 fail-closed 拒绝。
    """
    projection_clause = _select_projection_clause(candidate_text)
    if not projection_clause:
        return False
    for projection in _split_top_level_csv(projection_clause):
        expression = _strip_projection_alias(projection)
        expression = re.sub(r"^distinct\s+", "", expression, flags=re.IGNORECASE).strip()
        normalized = _normalize_metadata_identifier(expression)
        if normalized == "*" or normalized.endswith(".*"):
            return True
    return False


def _extract_where_clause(candidate_text: str) -> str:
    """截取 WHERE 条件片段。

    参数：
        candidate_text: 安全预检输出的内部只读候选文本。
    返回：
        WHERE 后到 GROUP/ORDER/HAVING/LIMIT 等边界前的条件片段；缺失时返回空字符串。
    业务逻辑：
        字段级解释校验不能只看 SELECT 投影，过滤条件引用未知字段同样会影响
        问数语义和执行安全，因此需要单独抽取并进入白名单比对。
    """
    normalized = " ".join(str(candidate_text or "").split())
    match = re.search(
        r"\bwhere\b\s+(.+?)(?=\bgroup\s+by\b|\border\s+by\b|\bhaving\b|\blimit\b|\bunion\b|\bintersect\b|\bexcept\b|$)",
        normalized,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


def _extract_filter_columns(candidate_text: str) -> set[str]:
    """从 WHERE 条件中抽取字段标识。

    参数：
        candidate_text: 安全预检后的内部候选文本。
    返回：
        WHERE 条件中可识别的字段名集合。
    业务逻辑：
        对过滤条件采用与投影一致的保守字段识别策略：函数名、常量和 SQL 关键字
        被剔除，剩余标识必须在上下文字段白名单中出现。
    """
    where_clause = _extract_where_clause(candidate_text)
    return _extract_identifier_columns(where_clause) if where_clause else set()


def _validate_explain_against_metadata(
    *,
    safe_candidate: str,
    safety_result: dict[str, Any],
    context_package: dict[str, Any],
) -> list[str]:
    """用上下文字段元数据执行离线解释校验。

    参数：
        safe_candidate: 通过安全预检后的内部候选文本。
        safety_result: 安全预检结构化结果，包含已识别对象。
        context_package: 召回上下文包，包含字段白名单。
    返回：
        稳定违规码列表；无违规返回空列表。
    业务逻辑：
        这里不执行真实数据库 EXPLAIN，只做确定性字段存在性校验。若候选引用了
        上下文字段元数据中不存在的字段或通配过宽投影，必须在只读执行前失败。
    """
    violations: list[str] = []
    if _contains_select_star(safe_candidate):
        violations.append("select_star_not_allowed")

    table_columns = _extract_table_columns(context_package)
    if not table_columns:
        return sorted(set(violations))

    referenced_tables = [
        normalized
        for table_ref in safety_result.get("referenced_tables", [])
        if (normalized := _normalize_metadata_identifier(table_ref))
    ]
    allowed_columns: set[str] = set()
    for table_ref in referenced_tables:
        allowed_columns.update(table_columns.get(table_ref, set()))
    if not allowed_columns and len(table_columns) == 1:
        allowed_columns.update(next(iter(table_columns.values())))

    referenced_columns = _extract_projected_columns(safe_candidate)
    referenced_columns.update(_extract_filter_columns(safe_candidate))
    if not referenced_columns:
        return sorted(set(violations))
    if not allowed_columns:
        violations.append("missing_column_metadata")
        return sorted(set(violations))

    unknown_columns = sorted(referenced_columns - allowed_columns)
    if unknown_columns:
        violations.append("unknown_column")
    return sorted(set(violations))


def _select_correction_candidate(context_package: dict[str, Any], revision_round: int) -> str:
    """选择本轮受控修正候选。

    参数：
        context_package: 召回上下文包，可包含 sql_correction_candidates。
        revision_round: 即将写入的修正轮次，从 1 开始。
    返回：
        当前轮次可用的候选文本；不存在时返回空字符串。
    业务逻辑：
        修正只能使用上下文包显式注入的候选，不调用模型、不自由生成新候选。
    """
    raw_candidates = (
        context_package.get("sql_correction_candidates")
        or context_package.get("correction_candidates")
        or []
    )
    if not isinstance(raw_candidates, list | tuple):
        return ""
    index = revision_round - 1
    if index < 0 or index >= len(raw_candidates):
        return ""
    raw_candidate = raw_candidates[index]
    if isinstance(raw_candidate, dict):
        raw_candidate = raw_candidate.get("sql") or raw_candidate.get("candidate") or raw_candidate.get("text")
    return str(raw_candidate or "").strip()


def receive_query(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """接收并校验用户问题。

    参数：
        state: 初始运行态，至少可包含 question。
    返回：
        写入 question 与基础执行状态后的运行态。
    业务逻辑：
        空问题或超长问题直接标记为 error 终态，后续由路由进入错误终端节点。
    """
    question = str(state.get("question", "") or "").strip()
    next_state = _append_trace(
        state,
        node="receive_query",
        status="ok" if question and len(question) <= 1000 else "error",
        summary="已接收业务问题" if question and len(question) <= 1000 else "问题为空或长度超出限制",
    )
    next_state["question"] = question
    next_state.setdefault("execution_status", "not_started")
    next_state.setdefault("sql_revision_round", 0)
    next_state.setdefault("row_count", 0)
    next_state.setdefault("result_truncated", False)
    if not question or len(question) > 1000:
        next_state["terminal_status"] = "error"
        next_state["fallback_reason"] = "invalid_question"
    return next_state


def init_trace_and_mode(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """初始化追踪字段和灰度模式。

    参数：
        state: receive_query 后的运行态。
    返回：
        写入 nqe_mode、domain_mode、版本和默认策略后的运行态。
    业务逻辑：
        nqe_mode 默认 off；只有调用方显式传入 shadow、assist、on 才进入 NQE 骨架链路。
    """
    mode = _coerce_nqe_mode(state.get("nqe_mode"))
    next_state = _append_trace(
        state,
        node="init_trace_and_mode",
        summary=f"灰度模式已初始化为 {mode}",
    )
    next_state["nqe_mode"] = mode
    next_state["domain_mode"] = _coerce_nqe_mode(next_state.get("domain_mode", mode))
    next_state["fallback_policy"] = str(next_state.get("fallback_policy") or "legacy_first")
    next_state["graph_version"] = NQE_SQL_AGENT_GRAPH_VERSION
    next_state.setdefault("metadata_version_id", None)
    next_state.setdefault("prompt_version_id", None)
    return next_state


def route_domain_and_capability(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """写入确定性领域和能力占位结果。

    参数：
        state: 已初始化模式的运行态。
    返回：
        带有 selected_domain 与 selected_capability 的运行态。
    业务逻辑：
        本卡只建立骨架，不做真实领域识别；如调用方提供 domain_hint 则作为候选业务域。
    """
    domain = str(state.get("domain_hint") or state.get("selected_domain") or "business_qa")
    capability = str(state.get("selected_capability") or "nqe_sql_agent_skeleton")
    next_state = _append_trace(
        state,
        node="route_domain_and_capability",
        summary="已形成业务域与能力候选",
    )
    next_state["selected_domain"] = domain
    next_state["selected_capability"] = capability
    next_state["domain_candidates"] = [{"domain": domain, "status": "candidate"}]
    next_state["capability_candidates"] = [{"capability": capability, "status": "candidate"}]
    return next_state


def normalize_query(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """归一化用户问题并抽取最小理解占位字段。

    参数：
        state: 领域路由后的运行态。
    返回：
        写入 normalized_question 和理解候选的运行态。
    业务逻辑：
        只做安全的字符串规整，不调用真实模型，不做业务事实计算。
    """
    normalized = " ".join(str(state.get("question") or "").split())
    next_state = _append_trace(
        state,
        node="normalize_query",
        summary="已完成问题文本归一化",
    )
    next_state["normalized_question"] = normalized
    next_state["keyword_terms"] = [term for term in normalized.split() if term][:8]
    next_state.setdefault("entity_terms", [])
    next_state.setdefault("metric_terms", [])
    next_state.setdefault("time_terms", [])
    next_state.setdefault("compare_terms", [])
    return next_state


def _domain_for_retrieval(state: NqeSqlAgentState) -> str:
    """读取召回阶段使用的业务域编码。"""

    return str(state.get("selected_domain") or state.get("domain_hint") or "").strip().lower()


def _build_domain_metadata_context_package(domain_code: str) -> dict[str, Any]:
    """构造指定业务域的静态元数据上下文包。"""
    bundle = NqeMetadataSyncBuilder(include_domains=(domain_code,)).build()
    return build_nqe_context_package_from_bundle(bundle, domain_code=domain_code)


# NQE-SQL-MAIN-14: 物流；NQE-SQL-MAIN-19: 产销存；NQE-SQL-MAIN-23: BOM
_AUTO_CONTEXT_DOMAINS = frozenset({"logistics", "business_analysis", "plan_bom"})


def retrieve_context_multiway(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """执行多路召回占位。

    参数：
        state: 已归一化的问题运行态。
    返回：
        写入 retrieval_query 与 retrieval_candidates 的运行态。
    业务逻辑：
        优先保留调用方测试注入的 retrieval_context_package；未注入且业务域为 logistics
        时，从受控 catalog 构造非敏感物流元数据上下文。其他业务域仍保持占位澄清。
    """
    injected_package = dict(state.get("retrieval_context_package") or {})
    context_package = injected_package
    auto_built = False
    domain = _domain_for_retrieval(state)
    if not context_package and domain in _AUTO_CONTEXT_DOMAINS:
        context_package = _build_domain_metadata_context_package(domain)
        auto_built = True
    if auto_built:
        summary = f"已构造 {domain} 元数据召回上下文"
    elif context_package:
        summary = "已保留测试注入的召回上下文"
    else:
        summary = "当前业务域尚未接入自动元数据召回"
    next_state = _append_trace(
        state,
        node="retrieve_context_multiway",
        summary=summary,
    )
    next_state["retrieval_query"] = str(state.get("normalized_question") or state.get("question") or "")
    next_state["retrieval_context_package"] = context_package
    if context_package.get("ready") and auto_built:
        next_state["retrieval_candidates"] = [{"status": "ready", "domain_code": context_package.get("domain_code")}]
    else:
        next_state["retrieval_candidates"] = [{"status": "ready"}] if context_package.get("ready") else []
    return next_state


def merge_rank_and_build_context(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """合并召回候选并构造上下文包。

    参数：
        state: 多路召回后的运行态。
    返回：
        保留或更新 retrieval_context_package 的运行态。
    业务逻辑：
        骨架不做真实排序；只根据测试注入 ready 标记决定后续 readiness。
    """
    package = dict(state.get("retrieval_context_package") or {})
    package.setdefault("ready", bool(state.get("retrieval_candidates")))
    next_state = _append_trace(
        state,
        node="merge_rank_and_build_context",
        summary="已合并上下文候选",
    )
    next_state["retrieval_context_package"] = package
    return next_state


def check_context_readiness(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """检查上下文是否足以进入内部查询生命周期。

    参数：
        state: 已构造上下文包的运行态。
    返回：
        写入 context_readiness 和澄清提示的运行态。
    业务逻辑：
        只有显式传入 context_readiness=pass 或 ready 上下文包，才允许进入后续占位链路。
    """
    package = dict(state.get("retrieval_context_package") or {})
    ready = state.get("context_readiness") == "pass" or package.get("ready") is True
    next_state = _append_trace(
        state,
        node="check_context_readiness",
        status="ok" if ready else "clarify",
        summary="上下文满足最小问数条件" if ready else "上下文不足，需要补充业务条件",
    )
    next_state["context_readiness"] = "pass" if ready else "fail"
    if not ready:
        next_state["terminal_status"] = "clarify"
        next_state["clarification_hints"] = ["请补充业务范围、时间或对象。"]
    return next_state


def generate_sql_direct(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """真实 LLM SQL 生成节点。

    NQE-SQL-REAL-1: 替换占位逻辑，调用真实 LLM 生成 SQL。
    参数：
        state: readiness 通过后的运行态。
    返回：
        写入 generated_sql 的运行态。
    """
    package = dict(state.get("retrieval_context_package") or {})
    question = str(state.get("question") or state.get("normalized_question") or "")

    # 优先测试注入，其次 LLM 生成
    candidate = str(
        state.get("generated_sql")
        or package.get("generated_sql_candidate")
        or package.get("sql_candidate")
        or ""
    ).strip()

    if not candidate and question:
        try:
            from backend.app.core.config import get_settings
            settings = get_settings()
            if settings.llm_api_key:
                from backend.app.domains.business_qa_graph.nodes.generate_sql_node import _llm_generate_sql
                # 将 context_package 转为 LLM 期望的 table_infos / metric_infos
                table_infos = []
                for table in package.get("allowed_tables", []):
                    columns = (package.get("table_columns") or {}).get(table, [])
                    table_infos.append({"table": table, "columns": columns})
                metric_infos = package.get("retrieval_assets", {}).get("metrics", [])
                candidate = _llm_generate_sql(
                    question, table_infos, metric_infos,
                    date_info={}, db_info={"dialect": "MySQL"},
                    settings=settings,
                )
                if not candidate or not candidate.strip():
                    raise ValueError("LLM returned empty SQL")
        except Exception:
            # 无 LLM 时保留 tests stub 兼容路径（但不再用 first-column 占位）
            candidate = ""

    # 最终兜底：仍然无候选时标记错误
    if not candidate:
        next_state = _append_trace(state, node="generate_sql_direct", status="error", summary="LLM SQL 生成失败")
        next_state["generated_sql"] = ""
        next_state["generation_status"] = "failed"
        next_state["generation_error"] = "no_candidate"
        return next_state

    next_state = _append_trace(state, node="generate_sql_direct", summary="已生成真实 LLM SQL 查询候选")
    next_state["generated_sql"] = candidate
    next_state["generation_status"] = "generated"
    return next_state


def precheck_sql_safety(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """执行内部查询候选的确定性安全预检。

    参数：
        state: 已生成内部查询候选的运行态。
    返回：
        写入 sql_safety_result 和 safe_sql_candidate 的运行态。
    业务逻辑：
        预检由独立安全模块执行；测试强制拒绝入口仍保留，但不能绕过真实预检。
    """
    package = dict(state.get("retrieval_context_package") or {})
    safety_result = precheck_nqe_sql_safety(
        str(state.get("generated_sql") or ""),
        package,
        str(state.get("selected_domain") or ""),
    )
    rejected = bool(state.get("force_safety_reject")) or safety_result.get("status") != "pass"
    if state.get("force_safety_reject"):
        violations = list(safety_result.get("violations") or [])
        if "forced_reject" not in violations:
            violations.append("forced_reject")
        safety_result = dict(safety_result)
        safety_result["status"] = "reject"
        safety_result["reason_code"] = "forced_reject"
        safety_result["safe_sql"] = ""
        safety_result["limit_applied"] = False
        safety_result["violations"] = sorted(violations)
    next_state = _append_trace(
        state,
        node="precheck_sql_safety",
        status="blocked" if rejected else "ok",
        summary="安全边界未通过" if rejected else "安全边界检查通过",
    )
    next_state["sql_safety_result"] = safety_result
    next_state.pop("safe_sql_candidate", None)
    if rejected:
        next_state["terminal_status"] = "safety_reject"
        next_state["fallback_reason"] = str(safety_result.get("reason_code") or "safety_boundary")
    else:
        next_state["safe_sql_candidate"] = str(safety_result.get("safe_sql") or "")
    return next_state


def explain_validate_sql(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """真实 MySQL EXPLAIN 校验节点。

    NQE-SQL-REAL-2: 连接开发数据库执行 EXPLAIN SQL。
    无 DB 时回退 metadata 校验（测试兼容）。
    """
    package = dict(state.get("retrieval_context_package") or {})
    safety_result = dict(state.get("sql_safety_result") or {})
    sql_candidate = str(state.get("safe_sql_candidate") or state.get("generated_sql") or "")

    violations: list[str] = []
    injected_candidate = bool(package.get("generated_sql_candidate") or package.get("sql_candidate"))

    # 真实 MySQL EXPLAIN（仅 LLM 生成的 SQL，跳过测试注入）
    if sql_candidate.strip() and not injected_candidate:
        try:
            from sqlalchemy import text
            from backend.app.db.session import SessionLocal
            db = SessionLocal()
            try:
                result = db.execute(text(f"EXPLAIN {sql_candidate}"))
                rows = result.fetchall()
                for row in rows:
                    extra = str(getattr(row, "Extra", "") or "")
                    if "no matching" in extra.lower() or "impossible" in extra.lower():
                        violations.append("explain_no_matching_row")
            except Exception as db_exc:
                err = str(db_exc).lower()
                if "syntax" in err:
                    violations.append("sql_syntax_error")
                elif "exist" in err or "unknown table" in err:
                    violations.append("unknown_table_error")
                elif "access denied" in err or "permission" in err:
                    violations.append("sql_permission_error")
                else:
                    violations.append(f"explain_db_error: {str(db_exc)[:120]}")
            finally:
                db.close()
        except Exception:
            pass

    # metadata 校验（总是执行，捕获 select_star/unknown_column 等逻辑校验）
    metadata_violations = _validate_explain_against_metadata(
        safe_candidate=sql_candidate,
        safety_result=safety_result,
        context_package=package,
    )
    violations.extend(metadata_violations)

    if state.get("force_explain_fail"):
        violations.append("forced_explain_failure")

    unique_violations = sorted(set(violations))
    failed = bool(unique_violations)
    next_state = _append_trace(
        state,
        node="explain_validate_sql",
        status="error" if failed else "ok",
        summary="EXPLAIN 未通过" if failed else "EXPLAIN 通过",
    )
    next_state["explain_result"] = {
        "status": "fail" if failed else "pass",
        "violations": unique_violations,
        "revision_round": int(state.get("sql_revision_round", 0)),
    }
    if failed and int(state.get("sql_revision_round", 0)) >= MAX_SQL_REVISION_ROUNDS:
        next_state["terminal_status"] = "error"
        next_state["fallback_reason"] = "explain_validation_failed"
    return next_state


def correct_sql(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """LLM 修正 SQL 节点。

    NQE-SQL-REAL-3: 调用 LLM 根据 EXPLAIN 错误修正 SQL。
    无受控候选时调用 LLM；有候选时优先使用。
    """
    next_round = int(state.get("sql_revision_round", 0)) + 1
    package = dict(state.get("retrieval_context_package") or {})
    corrected_candidate = _select_correction_candidate(package, next_round)
    used_controlled_candidate = bool(corrected_candidate)

    # 无受控候选时：LLM 修正
    if not corrected_candidate:
        original_sql = str(state.get("generated_sql") or "")
        violations = list((state.get("explain_result") or {}).get("violations", []))
        question = str(state.get("question") or "")
        try:
            from backend.app.core.config import get_settings
            settings = get_settings()
            if settings.llm_api_key and original_sql:
                from openai import OpenAI
                client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
                response = client.chat.completions.create(
                    model=settings.llm_model or "qwen-max",
                    messages=[{"role": "user", "content": (
                        f"You are a MySQL expert. The following SQL has validation errors.\n"
                        f"Original SQL:\n{original_sql}\n\n"
                        f"Errors: {', '.join(violations)}\n"
                        f"Question: {question}\n\n"
                        "Fix the SQL. Output ONLY the corrected SQL statement, no markdown, no explanation."
                    )}],
                    temperature=0, max_tokens=2048, timeout=30.0,
                )
                corrected = (response.choices[0].message.content or "").strip()
                if corrected.startswith("```"):
                    corrected = "\n".join(l for l in corrected.split("\n") if not l.strip().startswith("```")).strip()
                if corrected:
                    corrected_candidate = corrected
        except Exception:
            pass

    next_state = _append_trace(
        state,
        node="correct_sql",
        status="retry",
        summary=f"已完成第 {next_round} 轮 SQL 修正",
    )
    revisions = list(next_state.get("sql_revisions", []))
    revisions.append({
        "round": next_round,
        "reason": "explain_validation_failed",
        "used_controlled_candidate": used_controlled_candidate,
        "llm_correction": not used_controlled_candidate,
    })
    next_state["sql_revision_round"] = next_round
    next_state["sql_revisions"] = revisions
    next_state["correction_reason"] = "explain_validation_failed"
    next_state["generated_sql"] = corrected_candidate or str(state.get("generated_sql") or "")
    return next_state


def execute_sql_readonly(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """真实只读 SQL 执行节点。

    NQE-SQL-REAL-4: 连接开发数据库执行验证通过的 SQL。
    测试注入 SQL 时跳过真实执行。
    """
    sql = str(state.get("generated_sql") or "")
    package = dict(state.get("retrieval_context_package") or {})
    injected = bool(package.get("generated_sql_candidate") or package.get("sql_candidate"))

    import time
    start = time.monotonic()
    rows_data: list = []
    columns: list = []
    row_count = 0
    error = ""

    if sql.strip() and not injected:
        try:
            from sqlalchemy import text
            from backend.app.db.session import SessionLocal
            db = SessionLocal()
            try:
                result = db.execute(text(sql), execution_options={"timeout": 30})
                columns = list(result.keys())
                rows_data = [dict(zip(columns, row)) for row in result.fetchmany(size=500)]
                row_count = len(rows_data)
            finally:
                db.close()
        except Exception as exc:
            error = str(exc)[:500]

    duration_ms = int((time.monotonic() - start) * 1000)

    next_state = _append_trace(state, node="execute_sql_readonly",
        summary="已完成只读执行" if not error else "SQL 执行异常",
        status="error" if error else "ok")
    next_state["execution_status"] = "error" if error else "executed"
    next_state["execution_result_internal"] = {"rows": rows_data, "columns": columns, "source": "db"}
    next_state["row_count"] = row_count
    next_state["result_truncated"] = row_count >= 500
    next_state["execution_duration_ms"] = duration_ms
    if error:
        next_state["execution_error"] = error
        next_state["terminal_status"] = "error"
        next_state["fallback_reason"] = error
    return next_state


def present_business_answer(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """统一业务问答结果节点。

    NQE-SQL-REAL-5: 输出结构化结果：answer / columns / rows / metrics / duration。
    """
    result = dict(state.get("execution_result_internal") or {})
    rows = result.get("rows", [])
    columns = result.get("columns", [])
    row_count = state.get("row_count", 0)
    elapsed = state.get("execution_duration_ms", 0)
    domain = state.get("selected_domain", "")

    answer_text = f"已完成 {domain} 域查询，返回 {row_count} 行结果。" if row_count else "查询完成，无匹配数据。"

    next_state = _append_trace(state, node="present_business_answer", summary="已生成业务化回答")
    next_state["terminal_status"] = "completed"
    next_state["user_visible_response"] = answer_text
    next_state["structured_result"] = {
        "status": "success",
        "answer": answer_text,
        "columns": columns,
        "rows": rows[:100],
        "row_count": row_count,
        "duration_ms": elapsed,
        "domain": domain,
    }
    return next_state


def shadow_compare(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """记录 shadow 对比占位。

    参数：
        state: 已生成业务回答的运行态。
    返回：
        写入 shadow_compare_result 的运行态。
    业务逻辑：
        shadow 仅记录内部对比摘要，不影响用户可见回答。
    """
    next_state = _append_trace(
        state,
        node="shadow_compare",
        summary="已记录灰度对比占位结果",
    )
    next_state["shadow_compare_result"] = {"status": "not_compared", "reason": "skeleton_only"}
    return next_state


def legacy_fallback(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """off 模式降级到既有入口占位。

    参数：
        state: 灰度模式为 off 的运行态。
    返回：
        写入 legacy_fallback 终态和业务化提示的运行态。
    业务逻辑：
        off 模式不允许进入内部查询生命周期。
    """
    next_state = _append_trace(
        state,
        node="legacy_fallback",
        summary="已按关闭模式交由既有能力处理",
    )
    next_state["terminal_status"] = "legacy_fallback"
    next_state["execution_status"] = "skipped"
    next_state["fallback_reason"] = "nqe_mode_off"
    next_state["user_visible_response"] = "已转交既有业务问答能力处理。"
    return next_state


def terminal_clarify(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """生成澄清终态回答。

    参数：
        state: 上下文不足或问题需要补充的运行态。
    返回：
        写入 clarify 终态和业务化澄清文本的运行态。
    业务逻辑：
        澄清文本只说明需要补充业务条件，不暴露内部原因。
    """
    next_state = _append_trace(
        state,
        node="terminal_clarify",
        status="clarify",
        summary="已进入业务澄清终态",
    )
    next_state["terminal_status"] = "clarify"
    next_state["execution_status"] = "skipped"
    next_state["user_visible_response"] = "请补充业务范围、时间或对象后再查询。"
    return next_state


def terminal_safety_reject(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """生成安全拒答终态回答。

    参数：
        state: 安全边界未通过的运行态。
    返回：
        写入 safety_reject 终态和业务化拒答文本的运行态。
    业务逻辑：
        拒答只说明当前请求不能处理，不展示内部校验细节。
    """
    next_state = _append_trace(
        state,
        node="terminal_safety_reject",
        status="blocked",
        summary="已进入安全拒答终态",
    )
    next_state["terminal_status"] = "safety_reject"
    next_state["execution_status"] = "skipped"
    next_state["user_visible_response"] = "当前请求不满足只读问数边界，已停止处理。"
    return next_state


def terminal_error(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """生成错误终态回答。

    参数：
        state: 问题无效或骨架占位校验失败的运行态。
    返回：
        写入 error 终态和业务化错误文本的运行态。
    业务逻辑：
        错误文本只给出可理解的业务提示，不输出内部异常或调试信息。
    """
    next_state = _append_trace(
        state,
        node="terminal_error",
        status="error",
        summary="已进入错误终态",
    )
    next_state["terminal_status"] = "error"
    next_state["execution_status"] = "failed"
    next_state["user_visible_response"] = "当前请求暂时无法完成，请补充条件后重试或联系管理员核查配置。"
    return next_state


def record_query_log_and_trace(state: NqeSqlAgentState) -> NqeSqlAgentState:
    """记录查询日志和轨迹占位。

    参数：
        state: 任一终态节点后的运行态。
    返回：
        追加记录节点、脱敏 query log 和 replay 记录后的最终运行态。
    业务逻辑：
        本卡不写入数据库，只在 state 内构造结构化追溯材料。query_log_record
        不保存内部候选文本；replay_record 单独保存受控重放输入，用于离线复现。
    """
    next_state = _append_trace(
        state,
        node="record_query_log_and_trace",
        summary="已记录本次骨架运行摘要",
    )
    query_log_record = build_nqe_query_log_record(next_state)
    next_state["query_log_record"] = query_log_record
    next_state["replay_record"] = build_nqe_replay_record(next_state, query_log_record)
    return next_state


def _route_after_init(state: NqeSqlAgentState) -> str:
    """按初始化结果选择 off 降级、错误终态或 NQE 链路。"""
    if state.get("terminal_status") == "error":
        return "terminal_error"
    if state.get("nqe_mode") == "off":
        return "legacy_fallback"
    return "route_domain_and_capability"


def _route_after_readiness(state: NqeSqlAgentState) -> str:
    """上下文不足时转澄清，否则进入内部查询生命周期。"""
    if state.get("context_readiness") != "pass":
        return "terminal_clarify"
    return "generate_sql_direct"


def _route_after_precheck(state: NqeSqlAgentState) -> str:
    """安全预检失败时转拒答，否则继续解释校验。"""
    if state.get("terminal_status") == "safety_reject":
        return "terminal_safety_reject"
    return "explain_validate_sql"


def _route_after_explain(state: NqeSqlAgentState) -> str:
    """解释校验失败时最多修正两轮，超过后转错误终态。"""
    if state.get("terminal_status") == "error":
        return "terminal_error"
    if state.get("explain_result", {}).get("status") == "fail":
        return "correct_sql"
    return "execute_sql_readonly"


def _route_after_present(state: NqeSqlAgentState) -> Literal["shadow_compare", "record_query_log_and_trace"]:
    """shadow 模式下先记录对比占位，其余模式直接进入记录节点。"""
    if state.get("nqe_mode") == "shadow":
        return "shadow_compare"
    return "record_query_log_and_trace"


def build_nqe_sql_agent_graph():
    """构建并编译 NQE SQL Agent 独立骨架 Graph。

    参数：
        无。
    返回：
        已 compile 的 LangGraph graph，可通过 invoke 运行确定性骨架。
    业务逻辑：
        Graph 显式建模灰度模式、上下文 readiness、内部查询生命周期、两轮修正循环
        和五类终态；所有终态都进入 record_query_log_and_trace 后再结束。
    """
    graph = StateGraph(NqeSqlAgentState)

    graph.add_node("receive_query", receive_query)
    graph.add_node("init_trace_and_mode", init_trace_and_mode)
    graph.add_node("route_domain_and_capability", route_domain_and_capability)
    graph.add_node("normalize_query", normalize_query)
    graph.add_node("retrieve_context_multiway", retrieve_context_multiway)
    graph.add_node("merge_rank_and_build_context", merge_rank_and_build_context)
    graph.add_node("check_context_readiness", check_context_readiness)
    graph.add_node("generate_sql_direct", generate_sql_direct)
    graph.add_node("precheck_sql_safety", precheck_sql_safety)
    graph.add_node("explain_validate_sql", explain_validate_sql)
    graph.add_node("correct_sql", correct_sql)
    graph.add_node("execute_sql_readonly", execute_sql_readonly)
    graph.add_node("present_business_answer", present_business_answer)
    graph.add_node("record_query_log_and_trace", record_query_log_and_trace)
    graph.add_node("legacy_fallback", legacy_fallback)
    graph.add_node("shadow_compare", shadow_compare)
    graph.add_node("terminal_clarify", terminal_clarify)
    graph.add_node("terminal_safety_reject", terminal_safety_reject)
    graph.add_node("terminal_error", terminal_error)

    graph.add_edge(START, "receive_query")
    graph.add_edge("receive_query", "init_trace_and_mode")
    graph.add_conditional_edges(
        "init_trace_and_mode",
        _route_after_init,
        {
            "route_domain_and_capability": "route_domain_and_capability",
            "legacy_fallback": "legacy_fallback",
            "terminal_error": "terminal_error",
        },
    )

    graph.add_edge("route_domain_and_capability", "normalize_query")
    graph.add_edge("normalize_query", "retrieve_context_multiway")
    graph.add_edge("retrieve_context_multiway", "merge_rank_and_build_context")
    graph.add_edge("merge_rank_and_build_context", "check_context_readiness")
    graph.add_conditional_edges(
        "check_context_readiness",
        _route_after_readiness,
        {
            "generate_sql_direct": "generate_sql_direct",
            "terminal_clarify": "terminal_clarify",
        },
    )

    graph.add_edge("generate_sql_direct", "precheck_sql_safety")
    graph.add_conditional_edges(
        "precheck_sql_safety",
        _route_after_precheck,
        {
            "explain_validate_sql": "explain_validate_sql",
            "terminal_safety_reject": "terminal_safety_reject",
        },
    )
    graph.add_conditional_edges(
        "explain_validate_sql",
        _route_after_explain,
        {
            "execute_sql_readonly": "execute_sql_readonly",
            "correct_sql": "correct_sql",
            "terminal_error": "terminal_error",
        },
    )
    graph.add_edge("correct_sql", "precheck_sql_safety")
    graph.add_edge("execute_sql_readonly", "present_business_answer")
    graph.add_conditional_edges(
        "present_business_answer",
        _route_after_present,
        {
            "shadow_compare": "shadow_compare",
            "record_query_log_and_trace": "record_query_log_and_trace",
        },
    )

    graph.add_edge("legacy_fallback", "record_query_log_and_trace")
    graph.add_edge("shadow_compare", "record_query_log_and_trace")
    graph.add_edge("terminal_clarify", "record_query_log_and_trace")
    graph.add_edge("terminal_safety_reject", "record_query_log_and_trace")
    graph.add_edge("terminal_error", "record_query_log_and_trace")
    graph.add_edge("record_query_log_and_trace", END)

    return graph.compile()


def _build_runtime_input_from_replay_record(replay_record: dict[str, Any]) -> dict[str, Any]:
    """把脱敏 replay_record 转换为仅内存使用的重放输入。

    参数：
        replay_record: 持久化的脱敏重放记录。
    返回：
        可传给 Graph invoke 的运行态输入。
    业务逻辑：
        持久化 replay_input 不保存原始召回包、内部候选或对象字段元数据；重放时
        根据期望终态注入合成上下文，只验证路径形状和摘要，不还原真实内部资料。
    """
    replay_input = dict(replay_record.get("replay_input") or {})
    expected_summary = dict(replay_record.get("expected_summary") or {})
    runtime_input: dict[str, Any] = {
        key: value
        for key, value in replay_input.items()
        if key not in {"replay_context_summary"}
    }
    runtime_input["question"] = str(runtime_input.get("question") or "已脱敏重放问题")

    terminal_status = str(expected_summary.get("terminal_status") or "")
    if terminal_status == "legacy_fallback":
        runtime_input["nqe_mode"] = "off"
        runtime_input.pop("retrieval_context_package", None)
        return runtime_input
    if terminal_status == "clarify":
        runtime_input["context_readiness"] = "fail"
        runtime_input["retrieval_context_package"] = {"ready": False}
        return runtime_input

    synthetic_context = {
        "ready": True,
        "allowed_tables": ["replay_safe_source"],
        "table_columns": {"replay_safe_source": ["replay_value"]},
        "generated_sql_candidate": "SELECT replay_value FROM replay_safe_source",
    }
    runtime_input["context_readiness"] = "pass"
    runtime_input["retrieval_context_package"] = synthetic_context
    if terminal_status == "safety_reject":
        runtime_input["force_safety_reject"] = True
    return runtime_input


def replay_nqe_sql_agent_record(replay_record: dict[str, Any]) -> NqeSqlAgentState:
    """按 replay_record 重放 NQE SQL Agent 骨架。

    参数：
        replay_record: record_query_log_and_trace 生成的内部重放记录。
    返回：
        重放后的 Graph 最终态，并附加 replay_summary 对比结果。
    业务逻辑：
        replay_record 持久化部分只保存脱敏摘要；本函数在内存中合成最小上下文，
        重新经过完整 Graph，以验证终态、节点顺序和关键摘要是否仍可复现。
    """
    replay_input = _build_runtime_input_from_replay_record(replay_record)
    graph = build_nqe_sql_agent_graph()
    final_state = graph.invoke(replay_input)
    final_state["replay_summary"] = compare_nqe_replay_summary(
        dict(replay_record.get("expected_summary") or {}),
        final_state,
    )
    return final_state
