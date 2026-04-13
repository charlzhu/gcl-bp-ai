from __future__ import annotations

from typing import Any


class LogisticsResultCountHelper:
    """物流查询结果数量辅助工具。

    设计目的：
    1. 统一 aggregate / detail / compare 三类查询结果的数量提取逻辑；
    2. 修复“items 已有数据，但 total 仍然为 0”时被误判为空结果的问题；
    3. 给执行审计、结果解释、空结果分析、响应标准化等多个环节共用，避免重复实现。
    """

    @staticmethod
    def extract_count(query_result: dict[str, Any] | None) -> int:
        """从查询结果中提取结果数量。

        参数：
            query_result: 查询执行后返回的结果字典。

        返回：
            结果条数。若无法识别，则返回 0。

        规则说明：
            1. 若 total > 0，则优先使用 total；
            2. 若 total == 0，但 items 非空，则以 items 长度为准；
            3. compare 总量对比场景下，虽然没有 total / summary，
               但会返回 left_value / right_value / diff_value，此时应视为 1 条有效结果；
            4. 若没有 total，但 items 非空，则以 items 长度为准；
            5. 若没有 items，但 summary 存在且非空，可视为 1 条聚合结果；
            6. 其他情况返回 0。
        """
        if not isinstance(query_result, dict):
            return 0

        items = query_result.get("items")
        items_count = len(items) if isinstance(items, list) else 0

        if "total" in query_result:
            try:
                total = int(query_result.get("total") or 0)
            except Exception:
                total = 0

            # 关键修复：当 total 误为 0、但 items 实际已有数据时，优先相信 items。
            if total <= 0 and items_count > 0:
                return items_count
            if total > 0:
                return total

        if items_count > 0:
            return items_count

        # compare 总量对比场景：
        # 当前 compare_dim 为空时，repository 会返回 left_value/right_value/diff_value，
        # 但不会返回 total、summary，items 也可能是空列表。
        # 如果不在这里兜底，会被误判为“空结果”。
        if (
            "left_label" in query_result
            and "right_label" in query_result
            and (
                "left_value" in query_result
                or "right_value" in query_result
                or "diff_value" in query_result
            )
        ):
            return 1

        summary = query_result.get("summary")
        if isinstance(summary, dict) and summary:
            return 1

        return 0

    @classmethod
    def is_empty(cls, query_result: dict[str, Any] | None) -> bool:
        """判断查询结果是否为空。"""
        return cls.extract_count(query_result) == 0
