
from __future__ import annotations

from typing import Any


class LogisticsSQLWhitelist:
    """SQL 模板白名单校验器（V8）。

    V7 已经把模板与 SQL 模板绑定起来了，但还缺一个“只允许执行哪些模板”的保护层。
    V8 先做轻量白名单：
    1. 只允许执行预先登记的 SQL 模板 ID；
    2. 明确区分“白名单通过”和“仅预览不允许执行”；
    3. 便于后续 V9/V10 再扩展成按角色、按环境控制。
    """

    DEFAULT_ALLOWED_TEMPLATE_IDS = {
        "logistics.monthly_metric_total",
        "logistics.monthly_compare",
        "logistics.carrier_month_rank",
        "logistics.detail_by_business_no",
    }

    def __init__(self, allowed_template_ids: set[str] | None = None) -> None:
        self.allowed_template_ids = allowed_template_ids or self.DEFAULT_ALLOWED_TEMPLATE_IDS

    def check(self, sql_template_id: str | None) -> dict[str, Any]:
        if not sql_template_id:
            return {
                "allowed": False,
                "reason": "未绑定 SQL 模板，当前只允许走 QueryService 执行链路。",
                "matched_rule": "empty_sql_template_id",
            }

        if sql_template_id in self.allowed_template_ids:
            return {
                "allowed": True,
                "reason": f"SQL 模板 {sql_template_id} 已命中白名单。",
                "matched_rule": "allow_by_template_id",
            }

        return {
            "allowed": False,
            "reason": f"SQL 模板 {sql_template_id} 不在白名单中，禁止进入直连 SQL 执行链路。",
            "matched_rule": "deny_by_template_id",
        }
