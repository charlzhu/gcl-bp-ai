"""NQE-S2 presentation_node：将复合问题的子结果合并为统一业务答案。

职责：
1. 仅在 understanding_status=COMPOSITE_DECOMPOSED 时激活。
2. 读取 sub_plans 和 sub_results，合并为对比/趋势/综合型业务答案。
3. 写入 user_visible_message，不暴露 SQL/表名/字段名/query_key 等内部标识。
4. 非复合状态透传不修改。

不查库、不执行 SQL、不调用 LLM 自由生成、不计算业务事实。
"""

from __future__ import annotations

from backend.app.domains.business_qa_graph.schemas.event import BusinessQaGraphEvent
from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState


def presentation_node(
    state: BusinessQaGraphState,
) -> BusinessQaGraphState:
    """将复合问题的子结果合并为统一业务答案。

    参数：
        state: Graph 运行态，需包含 sub_plans/sub_results/composite_type。
    返回：
        写入合并后 user_visible_message 的新 state。
    业务逻辑：
        1. 仅 COMPOSITE_DECOMPOSED 状态激活。
        2. comparison 型：并排展示两个子结果，标注年份。
        3. trend 型：按时间顺序排列子结果。
        4. composite 型：分段展示各子结果。
        5. 非复合状态透传。
    """
    understanding_status = state.get("understanding_status", "UNSAFE")
    composite_type = state.get("composite_type", "none")
    sub_plans = state.get("sub_plans", [])
    sub_results = state.get("sub_results", [])
    trace = list(state.get("trace") or [])

    # ---- 门控：仅 COMPOSITE_DECOMPOSED 状态激活 ----
    if understanding_status != "COMPOSITE_DECOMPOSED":
        return dict(state)

    # ---- 空结果处理 ----
    if not sub_results:
        event = BusinessQaGraphEvent(
            node="presentation",
            event_type="presentation_empty",
            message="子查询均未返回有效结果。",
            payload={"composite_type": composite_type, "sub_result_count": 0},
        )
        next_state = dict(state)
        next_state["trace"] = [*trace, event.model_dump(mode="json")]
        next_state["user_visible_message"] = "抱歉，未能获取到您所查询的对比数据，请检查查询条件后重试。"
        return next_state

    # ---- 按复合类型合并 ----
    if composite_type == "comparison":
        merged_message = _merge_comparison(sub_plans, sub_results)
    elif composite_type == "trend":
        merged_message = _merge_trend(sub_plans, sub_results)
    else:
        merged_message = _merge_composite(sub_plans, sub_results)

    event = BusinessQaGraphEvent(
        node="presentation",
        event_type="presentation_merged",
        message=f"已合并 {len(sub_results)} 个子结果为统一业务答案，类型={composite_type}。",
        payload={
            "composite_type": composite_type,
            "sub_result_count": len(sub_results),
        },
    )

    next_state = dict(state)
    next_state["trace"] = [*trace, event.model_dump(mode="json")]
    next_state["user_visible_message"] = merged_message
    return next_state


def _merge_comparison(
    sub_plans: list[dict], sub_results: list[dict]
) -> str:
    """合并对比型子结果。

    参数：
        sub_plans: 子计划列表（含 question/source_clause）。
        sub_results: 子结果列表（含 answer_summary/columns/rows）。
    返回：
        合并后的业务化文本（不暴露 SQL/表名/字段名）。
    业务逻辑：
        1. 对每个子结果提取 answer_summary 和关键行数。
        2. 按子计划中的 source_clause（如"去年"/"今年"）标注。
        3. 构造对比型叙述。
    """
    parts = []
    for i, (plan, result) in enumerate(zip(sub_plans, sub_results)):
        label = plan.get("source_clause") or f"子查询 {i + 1}"
        summary = result.get("answer_summary", "")
        row_count = result.get("row_count", 0)

        if summary:
            parts.append(f"【{label}】{summary}")
        elif row_count > 0:
            rows = result.get("rows", [])
            rows_text = _format_rows_summary(result.get("columns", []), rows, max_rows=5)
            parts.append(f"【{label}】共 {row_count} 条记录：\n{rows_text}")
        else:
            parts.append(f"【{label}】无匹配记录")

    # 构造对比总结
    header = _build_comparison_header(sub_plans, sub_results)
    if header:
        parts.insert(0, header)

    return "\n\n".join(parts)


def _merge_trend(
    sub_plans: list[dict], sub_results: list[dict]
) -> str:
    """合并趋势型子结果。

    参数：
        sub_plans: 子计划列表。
        sub_results: 子结果列表。
    返回：
        合并后的业务化趋势描述。
    业务逻辑：
        按月份时间顺序展示子结果，构造趋势叙述。
    """
    parts = ["以下是您查询的趋势数据："]
    for i, (plan, result) in enumerate(zip(sub_plans, sub_results)):
        label = plan.get("source_clause") or f"时段 {i + 1}"
        summary = result.get("answer_summary", "")
        if summary:
            parts.append(f"· {label}：{summary}")
        else:
            row_count = result.get("row_count", 0)
            parts.append(f"· {label}：共 {row_count} 条记录")

    return "\n".join(parts)


def _merge_composite(
    sub_plans: list[dict], sub_results: list[dict]
) -> str:
    """合并综合型子结果（多独立子问）。

    参数：
        sub_plans: 子计划列表。
        sub_results: 子结果列表。
    返回：
        合并后的分段业务答案。
    业务逻辑：
        每个子结果独立成段。
    """
    parts = []
    for i, (plan, result) in enumerate(zip(sub_plans, sub_results)):
        question_text = plan.get("question", f"子问题 {i + 1}")
        summary = result.get("answer_summary", "")
        row_count = result.get("row_count", 0)

        if summary:
            parts.append(f"{i + 1}. {question_text}\n   回答：{summary}")
        elif row_count > 0:
            parts.append(f"{i + 1}. {question_text}\n   共 {row_count} 条记录")
        else:
            parts.append(f"{i + 1}. {question_text}\n   无匹配记录")

    return "\n\n".join(parts)


def _build_comparison_header(
    sub_plans: list[dict], sub_results: list[dict]
) -> str:
    """构造对比型标题。

    参数：
        sub_plans: 子计划列表。
        sub_results: 子结果列表。
    返回：
        对比标题文本。
    """
    labels = [sp.get("source_clause", f"项{i+1}") for i, sp in enumerate(sub_plans)]
    if len(labels) == 2:
        return f"{labels[0]}与{labels[1]}对比如下："

    return "多维度对比如下："


def _format_rows_summary(columns: list[str], rows: list[list], max_rows: int = 5) -> str:
    """将行列数据格式化为可读文本片段。

    参数：
        columns: 列名列表。
        rows: 行数据列表。
        max_rows: 最大展示行数。
    返回：
        格式化后的文本。
    业务逻辑：
        不暴露字段名，仅使用列标题。
    """
    if not rows:
        return "无数据"

    header = " | ".join(str(c) for c in columns) if columns else ""
    lines = []
    if header:
        lines.append(header)
        lines.append("-" * len(header))

    for row in rows[:max_rows]:
        lines.append(" | ".join(str(v) for v in row))

    if len(rows) > max_rows:
        lines.append(f"... 还有 {len(rows) - max_rows} 行")

    return "\n".join(lines)
