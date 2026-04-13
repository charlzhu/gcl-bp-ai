
from __future__ import annotations

import re
from typing import Any


class LogisticsQueryParamValidator:
    """物流查询参数校验器（V8）。

    V8 的目标不是替代 Pydantic，而是在“自然语言解析完成后、真正执行查询前”
    再补一层业务安全校验，主要解决三类问题：

    1. 编号类字段内容异常，可能是脏值、拼接错误，或者潜在注入风险；
    2. 分页、limit、排序字段等虽然语法合法，但超出了系统希望允许的范围；
    3. source_scope / mode / group_by 等配置化内容需要做白名单限制。
    """

    # 允许的查询模式白名单
    ALLOWED_MODES = {"aggregate", "compare", "detail"}

    # 允许的来源范围白名单
    ALLOWED_SOURCE_SCOPE = {"hist", "sys", "all"}

    # 允许的 group_by / order_by 字段白名单
    ALLOWED_GROUP_FIELDS = {
        "biz_year",
        "biz_month",
        "logistics_company_name",
        "region_name",
        "warehouse_name",
        "transport_mode",
        "origin_place",
        "customer_name",
        "source_type",
    }
    ALLOWED_ORDER_FIELDS = ALLOWED_GROUP_FIELDS | {
        "biz_date",
        "shipment_watt",
        "shipment_count",
        "shipment_trip_count",
        "total_fee",
        "extra_fee",
    }

    # 编号类字段统一允许字符：字母、数字、下划线、横杠
    BUSINESS_NO_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
    VEHICLE_PATTERN = re.compile(r"^[A-Za-z0-9一-龥-]{1,64}$")
    MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

    def validate(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """校验并返回校验结果。

        返回结构统一，便于 nl2query_service 直接挂回 parsed。
        """
        issues: list[dict[str, Any]] = []
        normalized = dict(parsed)

        mode = normalized.get("mode", "aggregate")
        if mode not in self.ALLOWED_MODES:
            issues.append(self._issue("mode", "INVALID_MODE", f"不支持的查询模式：{mode}"))
            normalized["mode"] = "aggregate"

        source_scope = normalized.get("source_scope", "all")
        if source_scope not in self.ALLOWED_SOURCE_SCOPE:
            issues.append(self._issue("source_scope", "INVALID_SOURCE_SCOPE", f"不支持的来源范围：{source_scope}"))
            normalized["source_scope"] = "all"

        # group_by 只允许白名单字段，避免模板或解析错误把未知列带进后续查询。
        group_by = normalized.get("group_by") or []
        if isinstance(group_by, list):
            filtered_group_by = []
            for item in group_by:
                if item in self.ALLOWED_GROUP_FIELDS:
                    filtered_group_by.append(item)
                else:
                    issues.append(self._issue("group_by", "INVALID_GROUP_BY", f"group_by 字段不在白名单中：{item}"))
            if group_by and not filtered_group_by:
                filtered_group_by = ["biz_month"]
            normalized["group_by"] = filtered_group_by or group_by
        else:
            issues.append(self._issue("group_by", "INVALID_GROUP_BY_TYPE", "group_by 必须为列表"))
            normalized["group_by"] = ["biz_month"]

        order_by = normalized.get("order_by")
        if order_by and order_by not in self.ALLOWED_ORDER_FIELDS:
            issues.append(self._issue("order_by", "INVALID_ORDER_BY", f"order_by 字段不在白名单中：{order_by}"))
            normalized["order_by"] = "biz_date" if mode == "detail" else normalized.get("metric_type", "shipment_watt")

        # 限制 limit / page_size 的上限，避免大结果集误查。
        if "limit" in normalized:
            try:
                limit = int(normalized.get("limit") or 100)
                if limit < 1:
                    limit = 100
                    issues.append(self._issue("limit", "INVALID_LIMIT", "limit 小于 1，已重置为 100"))
                if limit > 1000:
                    limit = 1000
                    issues.append(self._issue("limit", "LIMIT_TRUNCATED", "limit 超过上限 1000，已截断"))
                normalized["limit"] = limit
            except Exception:
                normalized["limit"] = 100
                issues.append(self._issue("limit", "INVALID_LIMIT_TYPE", "limit 类型非法，已重置为 100"))

        if "page_size" in normalized:
            try:
                page_size = int(normalized.get("page_size") or 20)
                if page_size < 1:
                    page_size = 20
                    issues.append(self._issue("page_size", "INVALID_PAGE_SIZE", "page_size 小于 1，已重置为 20"))
                if page_size > 500:
                    page_size = 500
                    issues.append(self._issue("page_size", "PAGE_SIZE_TRUNCATED", "page_size 超过上限 500，已截断"))
                normalized["page_size"] = page_size
            except Exception:
                normalized["page_size"] = 20
                issues.append(self._issue("page_size", "INVALID_PAGE_SIZE_TYPE", "page_size 类型非法，已重置为 20"))

        # 校验月份列表。
        year_month_list = normalized.get("year_month_list") or []
        if isinstance(year_month_list, list):
            valid_months = []
            for item in year_month_list:
                if isinstance(item, str) and self.MONTH_PATTERN.match(item):
                    valid_months.append(item)
                else:
                    issues.append(self._issue("year_month_list", "INVALID_MONTH", f"非法月份值：{item}"))
            normalized["year_month_list"] = valid_months
        else:
            issues.append(self._issue("year_month_list", "INVALID_MONTH_LIST_TYPE", "year_month_list 必须为列表"))
            normalized["year_month_list"] = []

        # 校验编号类字段。这里只做字符集校验，不在这里判断业务存在性。
        for field_name in ("contract_no", "inquiry_no", "ship_instruction_no", "sap_order_no", "task_id"):
            value = normalized.get(field_name)
            if value and not self.BUSINESS_NO_PATTERN.match(str(value)):
                issues.append(self._issue(field_name, "INVALID_BUSINESS_NO", f"{field_name} 包含非法字符：{value}"))

        vehicle_no = normalized.get("vehicle_no")
        if vehicle_no and not self.VEHICLE_PATTERN.match(str(vehicle_no)):
            issues.append(self._issue("vehicle_no", "INVALID_VEHICLE_NO", f"车牌号包含非法字符：{vehicle_no}"))

        return {
            "ok": len([x for x in issues if x["severity"] == "error"]) == 0,
            "issues": issues,
            "normalized_parsed": normalized,
        }

    @staticmethod
    def _issue(field: str, code: str, message: str, severity: str = "warning") -> dict[str, Any]:
        return {
            "field": field,
            "code": code,
            "message": message,
            "severity": severity,
        }
