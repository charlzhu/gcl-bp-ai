
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from backend.app.domains.logistics.schemas.query import LogisticsAggregateQuery, LogisticsCompareQuery, LogisticsDetailQuery

if TYPE_CHECKING:
    # 这里只在类型检查阶段导入，避免单元测试因为没有安装 SQLAlchemy 而在 import 阶段失败。
    from backend.app.domains.logistics.services.query_service import LogisticsQueryService


class LogisticsQueryExecutor:
    """统一查询执行器（V8）。

    V8 的优化点：
    1. 避免运行时硬依赖 query_service 模块导入，降低单元测试环境要求；
    2. 保持 aggregate / compare / detail 三类执行路线统一收口；
    3. 为后续真正引入 SQL 白名单直连执行预留位置。
    """

    def __init__(self, query_service: "LogisticsQueryService") -> None:
        self.query_service = query_service

    def execute(self, parsed: dict[str, Any], trace_id: str | None = None) -> dict[str, Any]:
        mode = parsed.get("mode", "aggregate")

        if mode == "compare":
            payload = {
                k: v
                for k, v in parsed.items()
                if k in {
                    "start_date",
                    "end_date",
                    "year_month_list",
                    "customer_name",
                    "logistics_company_name",
                    "region_name",
                    "warehouse_name",
                    "transport_mode",
                    "origin_place",
                    "contract_no",
                    "inquiry_no",
                    "ship_instruction_no",
                    "sap_order_no",
                    "vehicle_no",
                    "task_id",
                    "product_spec",
                    "metric_type",
                    "source_scope",
                    "left",
                    "right",
                    "compare_dim",
                }
            }
            return self.query_service.compare(LogisticsCompareQuery(**payload), trace_id=trace_id)

        if mode == "detail":
            payload = {
                k: v
                for k, v in parsed.items()
                if k in {
                    "start_date",
                    "end_date",
                    "year_month_list",
                    "customer_name",
                    "logistics_company_name",
                    "region_name",
                    "warehouse_name",
                    "transport_mode",
                    "origin_place",
                    "contract_no",
                    "inquiry_no",
                    "ship_instruction_no",
                    "sap_order_no",
                    "vehicle_no",
                    "task_id",
                    "product_spec",
                    "metric_type",
                    "source_scope",
                    "order_by",
                    "order_direction",
                    "page",
                    "page_size",
                }
            }
            return self.query_service.detail(LogisticsDetailQuery(**payload), trace_id=trace_id)

        payload = {
            k: v
            for k, v in parsed.items()
            if k in {
                "start_date",
                "end_date",
                "year_month_list",
                "customer_name",
                "logistics_company_name",
                "region_name",
                "warehouse_name",
                "transport_mode",
                "origin_place",
                "contract_no",
                "inquiry_no",
                "ship_instruction_no",
                "sap_order_no",
                "vehicle_no",
                "task_id",
                "product_spec",
                "metric_type",
                "source_scope",
                "group_by",
                "order_by",
                "order_direction",
                "limit",
            }
        }
        return self.query_service.aggregate(LogisticsAggregateQuery(**payload), trace_id=trace_id)
