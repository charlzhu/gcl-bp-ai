from __future__ import annotations

from typing import Any

from backend.app.domains.logistics.services.result_count_helper import LogisticsResultCountHelper


class LogisticsNoResultAnalyzer:
    """物流查询无结果分析器（V9）。

    设计目标：
    1. 当查询返回空结果时，给出尽量可执行的排查建议；
    2. 避免用户只看到空列表，不知道问题是“无数据”还是“过滤条件过严”；
    3. 先做规则化解释，后续如需大模型解释，可以复用这一层的结构。
    """

    def analyze(self, *, question: str, parsed: dict[str, Any], query_result: dict[str, Any]) -> dict[str, Any] | None:
        """分析空结果原因。

        只有在结果为空时才返回分析内容；若有结果则返回 None。
        """
        # 统一提取结果数量，避免 aggregate 场景误判为空。
        total = LogisticsResultCountHelper.extract_count(query_result)
        if total > 0:
            return None

        suggestions: list[str] = []
        possible_reasons: list[str] = []
        filters = query_result.get("filters", {}) if isinstance(query_result, dict) else {}
        execution_mode = query_result.get("execution_mode") if isinstance(query_result, dict) else None

        if execution_mode == "fallback":
            possible_reasons.append("当前查询走了 fallback 模式，说明数据库或服务层表可能未完全就绪。")
            suggestions.append("请优先确认 dws_logistics_monthly_metric、dws_logistics_detail_union、sys_query_log 已存在并有数据。")

        if execution_mode == "error_fallback":
            possible_reasons.append("当前查询走了异常兜底模式，主查询链路执行时发生异常。")
            suggestions.append("请查看 execution_error 字段和服务日志，确认数据库连接、SQL 模板、参数绑定是否正常。")

        # 编号类查询未命中，是当前最常见的无结果原因之一。
        for field_label, field_name in [
            ("合同编号", "contract_no"),
            ("询比价编号", "inquiry_no"),
            ("发货指令", "ship_instruction_no"),
            ("SAP 单号", "sap_order_no"),
            ("任务编号", "task_id"),
        ]:
            value = filters.get(field_name) or parsed.get(field_name)
            if value:
                possible_reasons.append(f"当前已按{field_label}“{value}”过滤，但中间层中没有匹配记录。")
                suggestions.append(f"建议先在 dws_logistics_detail_union 中直接核对 {field_name} 是否存在该值。")
                break

        if filters.get("warehouse_name"):
            possible_reasons.append("当前仓库维度在一期第一阶段尚未完全纳入可靠主链路，可能导致过滤过严。")
            suggestions.append("若当前版本未补仓库链路，建议先移除 warehouse_name 条件重试。")

        if filters.get("transport_mode"):
            possible_reasons.append("运输方式已参与过滤，请确认枚举映射后的标准值与数据库中保持一致。")
            suggestions.append("可先去掉运输方式条件重试，判断是数据不存在还是枚举映射未命中。")

        year_month_list = filters.get("year_month_list") or parsed.get("year_month_list") or []
        if year_month_list:
            possible_reasons.append("当前查询限定了月份范围，可能导致结果被时间条件过滤掉。")
            suggestions.append("建议放宽月份范围，或先仅按编号/维度查询，再逐步加时间条件。")

        source_scope = parsed.get("source_scope") or filters.get("source_scope")
        if source_scope in {"hist", "sys"}:
            possible_reasons.append(f"当前来源范围限定为 {source_scope}，另一侧数据不会被纳入查询。")
            suggestions.append("如需同时覆盖历史与系统数据，可尝试把来源范围切换为 all。")

        if not possible_reasons:
            possible_reasons.append("当前结果为空，但未识别到明显的异常条件，可能是数据本身不存在。")
            suggestions.append("建议缩小问题复杂度，先按单一编号或单一月份验证数据是否存在。")

        return {
            "question": question,
            "is_empty_result": True,
            "execution_mode": execution_mode,
            "possible_reasons": possible_reasons,
            "suggestions": suggestions,
        }

