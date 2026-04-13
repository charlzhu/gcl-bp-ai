
from __future__ import annotations

from typing import Any


class LogisticsSQLRenderer:
    """SQL 模板渲染器（V8）。

    V7 的 render_preview 只是简单 str(value) 替换，主要问题有：
    1. 字符串没有自动加引号；
    2. None 会被替换成 Python 的 'None'，不是 SQL 的 NULL；
    3. 列表不会转成更直观的 SQL 预览形式。

    V8 先把“预览 SQL”做得更接近真实 SQL，便于排查与联调。
    注意：
    - 当前仍然是预览渲染，不直接拿这段 SQL 去执行；
    - 真正执行仍由 QueryService 负责。
    """

    def render_preview(self, sql_text: str | None, parsed: dict[str, Any]) -> dict[str, Any]:
        if not sql_text:
            return {"rendered": None, "placeholders": {}}

        placeholders = {
            "metric_type": parsed.get("metric_type"),
            "source_scope": parsed.get("source_scope"),
            "group_by": parsed.get("group_by"),
            "start_date": parsed.get("start_date"),
            "end_date": parsed.get("end_date"),
            "year_month_list": parsed.get("year_month_list"),
            "compare_dim": parsed.get("compare_dim"),
            "contract_no": parsed.get("contract_no"),
            "task_id": parsed.get("task_id"),
            "logistics_company_name": parsed.get("logistics_company_name"),
            "region_name": parsed.get("region_name"),
            "transport_mode": parsed.get("transport_mode"),
        }

        rendered = sql_text
        for key, value in placeholders.items():
            sql_literal = self._to_sql_literal(value)
            rendered = rendered.replace("{{ " + key + " }}", sql_literal)
            rendered = rendered.replace("{{" + key + "}}", sql_literal)

        return {"rendered": rendered, "placeholders": placeholders}

    def _to_sql_literal(self, value: Any) -> str:
        """把 Python 值转换成更接近真实 SQL 的预览字面量。"""
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, list):
            # 这里只用于预览，列表统一渲染为 ('a','b','c') 形式。
            if not value:
                return "()"
            return "(" + ", ".join(self._to_sql_literal(item) for item in value) + ")"
        # 字符串走单引号，并把单引号转义。
        text = str(value).replace("'", "''")
        return f"'{text}'"
