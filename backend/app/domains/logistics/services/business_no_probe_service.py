from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.domains.logistics.services.query_service import LogisticsQueryService


class LogisticsBusinessNoProbeService:
    """物流业务编号存在性探测服务（V10）。

    设计目标：
    1. 在明细查询返回空结果时，进一步判断“是真的无数据”，还是“编号本身不存在”；
    2. 给 no_result_analysis 和标准状态码提供更稳定的依据；
    3. 不改变当前主查询逻辑，只作为结果解释增强层使用。
    """

    def __init__(self, query_service: "LogisticsQueryService") -> None:
        self.query_service = query_service

    def probe(self, parsed: dict[str, Any]) -> dict[str, Any] | None:
        """探测当前明细查询里的业务编号是否存在。

        参数：
            parsed: 自然语言解析后的查询计划。

        返回：
            若当前不是业务编号明细场景，返回 None；
            否则返回存在性探测结果：
            {
                "field_name": "contract_no",
                "field_label": "合同编号",
                "field_value": "XXX",
                "exists": False,
            }
        """
        candidate_pairs = [
            ("contract_no", "合同编号"),
            ("inquiry_no", "询比价编号"),
            ("ship_instruction_no", "发货指令"),
            ("sap_order_no", "SAP 单号"),
            ("vehicle_no", "车牌号"),
            ("task_id", "任务ID"),
        ]

        field_name = None
        field_label = None
        field_value = None
        for name, label in candidate_pairs:
            value = parsed.get(name)
            if value:
                field_name = name
                field_label = label
                field_value = value
                break

        if not field_name or field_value is None:
            return None

        exists = False
        probe_method = getattr(self.query_service, "probe_detail_business_no", None)
        if callable(probe_method):
            try:
                exists = bool(
                    probe_method(
                        field_name=field_name,
                        field_value=field_value,
                        source_scope=parsed.get("source_scope", "all"),
                    )
                )
            except Exception:
                # 这里不抛异常，避免影响主查询结果。
                exists = False

        return {
            "field_name": field_name,
            "field_label": field_label,
            "field_value": field_value,
            "exists": exists,
        }
