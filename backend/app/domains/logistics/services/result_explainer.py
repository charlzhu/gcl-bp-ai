from __future__ import annotations

from collections import Counter
from typing import Any

from backend.app.domains.logistics.services.result_count_helper import LogisticsResultCountHelper


class LogisticsResultExplainer:
    """物流查询结果解释器（V9）。

    设计目标：
    1. 把原始查询结果转换成更适合前端或联调阅读的解释信息；
    2. 当前重点不是做大模型总结，而是基于结构化结果生成稳定、可控的解释；
    3. 为后续接入大模型自动摘要预留统一输出结构。
    """

    def build(self, *, question: str, parsed: dict[str, Any], query_result: dict[str, Any]) -> dict[str, Any]:
        """生成查询结果解释。

        参数：
            question: 用户原始问题。
            parsed: 自然语言解析后的查询计划。
            query_result: 查询执行结果。

        返回：
            一个标准解释字典，包含摘要文本、关键事实、来源说明等。
        """
        # 统一提取结果数量，避免统计查询因 total 缺失或错写为 0 而误判为空结果。
        total = LogisticsResultCountHelper.extract_count(query_result)
        execution_mode = query_result.get("execution_mode") if isinstance(query_result, dict) else None
        query_type = query_result.get("query_type") if isinstance(query_result, dict) else parsed.get("mode")
        metric_type = parsed.get("metric_type") or query_result.get("metric_type")
        source_scope = parsed.get("source_scope") or query_result.get("source_scope")

        explanation: dict[str, Any] = {
            "question": question,
            "query_type": query_type,
            "metric_type": metric_type,
            "source_scope": source_scope,
            "execution_mode": execution_mode,
            "result_count": total,
            "summary": "",
            "highlights": [],
            "source_distribution": {},
            "notes": [],
        }

        # 无结果场景交给 no_result_analyzer 重点处理，这里只给一条轻量摘要。
        if total == 0:
            explanation["summary"] = "本次查询已执行完成，但未返回匹配数据。"
            explanation["notes"].append("建议结合 no_result_analysis 字段查看未命中原因与排查建议。")
            return explanation

        items = query_result.get("items") if isinstance(query_result, dict) else None
        if not isinstance(items, list):
            items = []

        # 统计来源分布，帮助判断结果来自历史、系统还是混合。
        source_counter = Counter()
        for item in items:
            if isinstance(item, dict):
                source_counter[str(item.get("source_type") or "UNKNOWN")] += 1
        explanation["source_distribution"] = dict(source_counter)

        # 生成不同查询类型的解释。
        if query_type == "detail":
            explanation["summary"] = f"本次明细查询共返回 {total} 条记录。"
            explanation["highlights"] = self._build_detail_highlights(items)
        elif query_type == "compare":
            explanation["summary"] = f"本次对比查询已完成，返回 {total} 条对比结果。"
            explanation["highlights"] = self._build_compare_highlights(items)
        else:
            explanation["summary"] = f"本次统计查询已完成，返回 {total} 条统计结果。"
            explanation["highlights"] = self._build_aggregate_highlights(items, metric_type)

        # 说明当前结果的执行方式。
        if execution_mode == "database":
            explanation["notes"].append("当前结果来自数据库查询。")
        elif execution_mode == "fallback":
            explanation["notes"].append("当前结果来自 fallback 模式，请确认数据库和服务层表已就绪。")
        elif execution_mode == "error_fallback":
            explanation["notes"].append("当前结果来自异常兜底模式，请优先查看 execution_error。")

        return explanation

    @staticmethod
    def _build_detail_highlights(items: list[dict[str, Any]]) -> list[str]:
        """构建明细查询高亮信息。"""
        if not items:
            return []
        first = items[0]
        highlights = []
        if isinstance(first, dict):
            if first.get("contract_no"):
                highlights.append(f"首条记录合同编号：{first.get('contract_no')}")
            if first.get("customer_name"):
                highlights.append(f"首条记录客户：{first.get('customer_name')}")
            if first.get("biz_date"):
                highlights.append(f"首条记录业务日期：{first.get('biz_date')}")
        return highlights

    @staticmethod
    def _build_compare_highlights(items: list[dict[str, Any]]) -> list[str]:
        """构建对比查询高亮信息。"""
        if not items:
            return []
        highlights: list[str] = []
        first = items[0]
        if isinstance(first, dict):
            left_value = first.get("left_value")
            right_value = first.get("right_value")
            diff_value = first.get("diff_value")
            if left_value is not None and right_value is not None:
                highlights.append(f"首条对比项左值：{left_value}，右值：{right_value}")
            if diff_value is not None:
                highlights.append(f"首条对比项差值：{diff_value}")
        return highlights

    @staticmethod
    def _build_aggregate_highlights(items: list[dict[str, Any]], metric_type: str | None) -> list[str]:
        """构建统计查询高亮信息。"""
        if not items:
            return []
        first = items[0]
        highlights: list[str] = []
        if isinstance(first, dict):
            # 优先使用查询指标对应的值，其次回退到常见字段。
            value = None
            if metric_type and metric_type in first:
                value = first.get(metric_type)
            if value is None:
                for candidate in ("metric_value", "shipment_watt", "total_fee", "shipment_trip_count"):
                    if candidate in first:
                        value = first.get(candidate)
                        break
            if value is not None:
                highlights.append(f"首条统计结果值：{value}")
            for dim_key in ("biz_month", "logistics_company_name", "region_name", "transport_mode"):
                if first.get(dim_key):
                    highlights.append(f"首条维度 {dim_key}：{first.get(dim_key)}")
                    break
        return highlights
