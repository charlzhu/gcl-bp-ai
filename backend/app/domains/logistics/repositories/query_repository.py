from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class LogisticsQueryRepository:
    """物流查询仓储层。

    风险说明：
    1. 该实现直接依赖一期查询服务表 `dws_logistics_monthly_metric`
       和 `dws_logistics_detail_union`；
    2. 当前 repository 走原生 SQL，字段名变化会直接影响运行期；
    3. 如果数据库表尚未初始化，service 层会自动回退到 demo 查询实现。
    """

    MONTHLY_TABLE = "dws_logistics_monthly_metric"
    DETAIL_TABLE = "dws_logistics_detail_union"

    # group_by 只允许使用白名单字段，避免前端直接拼接任意列名造成 SQL 注入。
    AGGREGATE_GROUP_BY_MAP = {
        "biz_year": "biz_year",
        "biz_month": "biz_month",
        "customer_name": "customer_name",
        "logistics_company_name": "logistics_company_name",
        "region_name": "region_name",
        "warehouse_name": "warehouse_name",
        "transport_mode": "transport_mode",
        "origin_place": "origin_place",
        "source_type": "source_type",
    }

    DETAIL_ORDER_BY_MAP = {
        "biz_date": "biz_date",
        "biz_month": "biz_month",
        "shipment_watt": "shipment_watt",
        "shipment_count": "shipment_count",
        "shipment_trip_count": "shipment_trip_count",
        "total_fee": "total_fee",
        "extra_fee": "extra_fee",
        "customer_name": "customer_name",
        "logistics_company_name": "logistics_company_name",
        "warehouse_name": "warehouse_name",
        "task_id": "task_id",
    }

    # 明细查询支持的业务编号字段白名单。V10 用于“编号存在性预检查”，避免动态拼接任意列名。
    DETAIL_SEARCHABLE_FIELDS = {
        "contract_no": "contract_no",
        "inquiry_no": "inquiry_no",
        "ship_instruction_no": "ship_instruction_no",
        "sap_order_no": "sap_order_no",
        "vehicle_no": "plate_number",
        "task_id": "task_id",
    }


    def aggregate(
        self,
        db: Session,
        filters: dict[str, Any],
        metric_field: str,
        group_by: list[str],
        order_by: str,
        order_direction: str,
        limit: int,
    ) -> dict[str, Any]:
        """统计查询。

        返回两段数据：
        1. summary: 全量过滤条件下的汇总值；
        2. items: 按 group_by 聚合后的分组结果。
        """
        params: dict[str, Any] = {"limit": limit}
        source_sql = self._build_source_filter(filters.get("source_scope", "all"), params)
        where_sql = self._build_common_filters(filters, params)

        # group_by 为空或包含非法字段时，默认退化为按业务月份统计。
        valid_group_by = [self.AGGREGATE_GROUP_BY_MAP[g] for g in group_by if g in self.AGGREGATE_GROUP_BY_MAP]
        if not valid_group_by:
            valid_group_by = ["biz_month"]

        # order_by 同样只允许出现在白名单字段或指标字段里。
        allowed_order_columns = set(self.AGGREGATE_GROUP_BY_MAP.values()) | {
            metric_field,
            "shipment_watt",
            "shipment_count",
            "shipment_trip_count",
            "total_fee",
            "extra_fee",
        }
        order_col = self.AGGREGATE_GROUP_BY_MAP.get(order_by or "", order_by or metric_field)
        if order_col not in allowed_order_columns:
            order_col = metric_field
        direction = "ASC" if str(order_direction).lower() == "asc" else "DESC"

        select_group = ", ".join(valid_group_by)
        group_clause = ", ".join(valid_group_by)

        summary_sql = f"""
            SELECT
                COALESCE(SUM(shipment_watt), 0) AS shipment_watt,
                COALESCE(SUM(shipment_count), 0) AS shipment_count,
                COALESCE(SUM(shipment_trip_count), 0) AS shipment_trip_count,
                COALESCE(SUM(total_fee), 0) AS total_fee,
                COALESCE(SUM(extra_fee), 0) AS extra_fee,
                COUNT(1) AS row_count
            FROM {self.MONTHLY_TABLE}
            WHERE 1 = 1
            {source_sql}
            {where_sql}
        """
        detail_sql = f"""
            SELECT
                {select_group},
                COALESCE(SUM(shipment_watt), 0) AS shipment_watt,
                COALESCE(SUM(shipment_count), 0) AS shipment_count,
                COALESCE(SUM(shipment_trip_count), 0) AS shipment_trip_count,
                COALESCE(SUM(total_fee), 0) AS total_fee,
                COALESCE(SUM(extra_fee), 0) AS extra_fee,
                COUNT(1) AS row_count
            FROM {self.MONTHLY_TABLE}
            WHERE 1 = 1
            {source_sql}
            {where_sql}
            GROUP BY {group_clause}
            ORDER BY {order_col} {direction}
            LIMIT :limit
        """
        summary = db.execute(text(summary_sql), params).mappings().first()
        items = list(db.execute(text(detail_sql), params).mappings().all())
        return {"summary": dict(summary or {}), "items": [dict(item) for item in items]}

    def detail(
        self,
        db: Session,
        filters: dict[str, Any],
        order_by: str,
        order_direction: str,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        """明细查询，分页返回汇总表下钻后的明细视图。"""
        params: dict[str, Any] = {"offset": (page - 1) * page_size, "page_size": page_size}
        source_sql = self._build_source_filter(filters.get("source_scope", "all"), params)
        where_sql = self._build_common_filters(filters, params)

        direction = "ASC" if str(order_direction).lower() == "asc" else "DESC"
        order_col = self.DETAIL_ORDER_BY_MAP.get(order_by, "biz_date")

        count_sql = f"""
            SELECT COUNT(1) AS total
            FROM {self.DETAIL_TABLE}
            WHERE 1 = 1
            {source_sql}
            {where_sql}
        """
        list_sql = f"""
            SELECT
                id, source_type, biz_date, biz_year, biz_month, task_id, contract_no, inquiry_no,
                ship_instruction_no, sap_order_no, customer_name, logistics_company_name, warehouse_name,
                region_name, origin_place, transport_mode, plate_number, product_spec, product_power,
                shipment_count, shipment_watt, shipment_trip_count, total_fee, extra_fee, source_ref
            FROM {self.DETAIL_TABLE}
            WHERE 1 = 1
            {source_sql}
            {where_sql}
            ORDER BY {order_col} {direction}, id DESC
            LIMIT :page_size OFFSET :offset
        """
        total = db.execute(text(count_sql), params).scalar() or 0
        items = list(db.execute(text(list_sql), params).mappings().all())
        return {"total": int(total), "page": page, "page_size": page_size, "items": [dict(item) for item in items]}

    def exists_detail_business_no(
        self,
        db: Session,
        *,
        field_name: str,
        field_value: Any,
        source_scope: str = "all",
    ) -> bool:
        """检查某个业务编号是否存在于明细服务层表中。

        参数：
            db: SQLAlchemy Session。
            field_name: 业务字段名，只允许白名单中的字段。
            field_value: 业务编号值。
            source_scope: 来源范围，支持 hist / sys / all。

        返回：
            True 表示至少存在一条匹配记录，False 表示不存在。
        """
        column = self.DETAIL_SEARCHABLE_FIELDS.get(field_name)
        if not column:
            return False
        if field_value is None or str(field_value).strip() == "":
            return False

        params: dict[str, Any] = {"field_value": field_value}
        source_sql = self._build_source_filter(source_scope, params)
        sql = f"""
            SELECT 1
            FROM {self.DETAIL_TABLE}
            WHERE 1 = 1
            {source_sql}
              AND {column} = :field_value
            LIMIT 1
        """
        row = db.execute(text(sql), params).first()
        return row is not None


    def compare(
        self,
        db: Session,
        base_filters: dict[str, Any],
        metric_field: str,
        compare_dim: str | None,
        left: dict[str, Any],
        right: dict[str, Any],
    ) -> dict[str, Any]:
        """对比查询。

        compare_dim 为空时返回总量对比；
        compare_dim 不为空时返回按维度展开的左右值、差值和差异率。
        """
        compare_col = self.AGGREGATE_GROUP_BY_MAP.get(compare_dim or "", compare_dim or "")
        if compare_dim and not compare_col:
            raise ValueError(f"不支持的 compare_dim: {compare_dim}")

        if compare_col:
            rows = {
                left["label"]: self._aggregate_for_side_by_dim(db, base_filters, metric_field, compare_col, left),
                right["label"]: self._aggregate_for_side_by_dim(db, base_filters, metric_field, compare_col, right),
            }
            return self._merge_compare_rows_by_dim(metric_field, compare_col, rows, left["label"], right["label"])

        left_value = self._aggregate_for_side_total(db, base_filters, metric_field, left)
        right_value = self._aggregate_for_side_total(db, base_filters, metric_field, right)
        diff = right_value - left_value
        diff_rate = (diff / left_value) if left_value else None
        return {
            "metric_type": metric_field,
            "left_label": left["label"],
            "right_label": right["label"],
            "left_value": left_value,
            "right_value": right_value,
            "diff_value": diff,
            "diff_rate": diff_rate,
            "items": [],
        }

    def write_query_log(self, db: Session, payload: dict[str, Any]) -> None:
        """写入查询日志表。

        这里不在 repository 内部 commit，由 service 统一控制事务和失败回滚。
        """
        sql = text(
            """
            INSERT INTO sys_query_log (
                trace_id, query_type, question_text, request_payload, route_type,
                metric_type, result_count, status, message
            )
            VALUES (
                :trace_id, :query_type, :question_text, :request_payload, :route_type,
                :metric_type, :result_count, :status, :message
            )
            """
        )
        db.execute(sql, payload)

    def list_query_logs(
        self,
        db: Session,
        *,
        limit: int = 100,
        query_type: str | None = None,
        status: str | None = None,
        trace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """读取查询日志列表。

        说明：
        1. 当前前端查询历史页主要依赖这份数据；
        2. 这里仍然走白名单字段和绑定参数，避免拼接任意 where 条件；
        3. 优先按最新时间倒序返回，便于联调时快速看到最近一次查询。
        """
        params: dict[str, Any] = {"limit": limit}
        where_parts: list[str] = []

        if query_type:
            where_parts.append("query_type = :query_type")
            params["query_type"] = query_type
        if status:
            where_parts.append("status = :status")
            params["status"] = status
        if trace_id:
            where_parts.append("trace_id = :trace_id")
            params["trace_id"] = trace_id

        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        sql = text(
            f"""
            SELECT
                id,
                trace_id,
                query_type,
                question_text,
                request_payload,
                route_type,
                metric_type,
                result_count,
                status,
                message,
                created_at
            FROM sys_query_log
            {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT :limit
            """
        )
        rows = db.execute(sql, params).mappings().all()
        return [dict(row) for row in rows]

    def get_query_log_detail(
        self,
        db: Session,
        *,
        log_id: int,
    ) -> dict[str, Any] | None:
        """读取单条查询日志详情。

        说明：
        1. 当前详情接口与列表接口复用同一张 `sys_query_log`；
        2. 这里不新增复杂关联，只返回原始日志行；
        3. 具体的结构化整理交由 service 层完成，避免 repository 承担展示逻辑。
        """
        sql = text(
            """
            SELECT
                id,
                trace_id,
                query_type,
                question_text,
                request_payload,
                route_type,
                metric_type,
                result_count,
                status,
                message,
                created_at
            FROM sys_query_log
            WHERE id = :log_id
            LIMIT 1
            """
        )
        row = db.execute(sql, {"log_id": log_id}).mappings().first()
        return dict(row) if row else None

    def _aggregate_for_side_total(
        self,
        db: Session,
        base_filters: dict[str, Any],
        metric_field: str,
        side: dict[str, Any],
    ) -> float:
        """对某个 side 执行总量聚合。"""
        params: dict[str, Any] = {}
        merged = {**base_filters, **side}
        source_sql = self._build_source_filter(merged.get("source_scope", "all"), params)
        where_sql = self._build_common_filters(merged, params)
        sql = f"""
            SELECT COALESCE(SUM({metric_field}), 0) AS metric_value
            FROM {self.MONTHLY_TABLE}
            WHERE 1 = 1
            {source_sql}
            {where_sql}
        """
        value = db.execute(text(sql), params).scalar() or 0
        return float(value)

    def _aggregate_for_side_by_dim(
        self,
        db: Session,
        base_filters: dict[str, Any],
        metric_field: str,
        compare_col: str,
        side: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """对某个 side 按 compare_dim 聚合，为 compare 查询的二维拼装做准备。"""
        params: dict[str, Any] = {}
        merged = {**base_filters, **side}
        source_sql = self._build_source_filter(merged.get("source_scope", "all"), params)
        where_sql = self._build_common_filters(merged, params)
        sql = f"""
            SELECT {compare_col} AS compare_value, COALESCE(SUM({metric_field}), 0) AS metric_value
            FROM {self.MONTHLY_TABLE}
            WHERE 1 = 1
            {source_sql}
            {where_sql}
            GROUP BY {compare_col}
        """
        rows = db.execute(text(sql), params).mappings().all()
        return [dict(row) for row in rows]

    def _merge_compare_rows_by_dim(
        self,
        metric_field: str,
        compare_col: str,
        row_map: dict[str, list[dict[str, Any]]],
        left_label: str,
        right_label: str,
    ) -> dict[str, Any]:
        """把左右两侧按维度聚合后的结果合并成前端可直接展示的 compare 结构。"""
        left_rows = {str(row.get("compare_value") or ""): float(row.get("metric_value") or 0) for row in row_map[left_label]}
        right_rows = {str(row.get("compare_value") or ""): float(row.get("metric_value") or 0) for row in row_map[right_label]}
        all_keys = sorted(set(left_rows.keys()) | set(right_rows.keys()))
        items = []
        for key in all_keys:
            left_value = left_rows.get(key, 0.0)
            right_value = right_rows.get(key, 0.0)
            diff = right_value - left_value
            items.append(
                {
                    compare_col: key,
                    "left_value": left_value,
                    "right_value": right_value,
                    "diff_value": diff,
                    "diff_rate": (diff / left_value) if left_value else None,
                }
            )
        return {
            "metric_type": metric_field,
            "left_label": left_label,
            "right_label": right_label,
            "items": items,
        }

    def _build_source_filter(
        self,
        source_scope: str,
        params: dict[str, Any],
        table_alias: str = "",
    ) -> str:
        """根据 hist/sys/all 构造来源过滤条件。

        约定：
        - hist -> HIST
        - sys  -> SYS
        - all  -> HIST + SYS + MIXED
        """
        prefix = f"{table_alias}." if table_alias else ""
        if source_scope == "hist":
            source_types = ["HIST"]
        elif source_scope == "sys":
            source_types = ["SYS"]
        else:
            source_types = ["HIST", "SYS", "MIXED"]

        placeholders = []
        for index, value in enumerate(source_types):
            key = f"source_type_{index}"
            params[key] = value
            placeholders.append(f":{key}")
        return f" AND {prefix}source_type IN ({', '.join(placeholders)}) "

    def _build_common_filters(
        self,
        filters: dict[str, Any],
        params: dict[str, Any],
        table_alias: str = "",
    ) -> str:
        """构造公共 where 条件。

        业务规则：
        - 日期范围按 biz_date 过滤；
        - year_month_list 优先命中 biz_month；
        - 名称类字段按 LIKE 模糊匹配；
        - 编号类字段按精确值匹配。
        """
        prefix = f"{table_alias}." if table_alias else ""
        sql_parts: list[str] = []

        if filters.get("start_date"):
            sql_parts.append(f"{prefix}biz_date >= :start_date")
            params["start_date"] = filters["start_date"]
        if filters.get("end_date"):
            sql_parts.append(f"{prefix}biz_date <= :end_date")
            params["end_date"] = filters["end_date"]

        year_month_list = filters.get("year_month_list") or []
        if year_month_list:
            placeholders = []
            for index, year_month in enumerate(year_month_list):
                key = f"ym_{index}"
                params[key] = year_month
                placeholders.append(f":{key}")
            sql_parts.append(f"{prefix}biz_month IN ({', '.join(placeholders)})")

        like_fields = [
            "customer_name",
            "logistics_company_name",
            "region_name",
            "warehouse_name",
            "transport_mode",
            "origin_place",
            "product_spec",
        ]
        exact_fields = [
            "contract_no",
            "inquiry_no",
            "ship_instruction_no",
            "sap_order_no",
            "vehicle_no",
            "task_id",
        ]

        for field in like_fields:
            value = filters.get(field)
            if value:
                sql_parts.append(f"{prefix}{field} LIKE :{field}")
                params[field] = f"%{value}%"
        for field in exact_fields:
            value = filters.get(field)
            if value:
                sql_parts.append(f"{prefix}{field} = :{field}")
                params[field] = value

        return (" AND " + " AND ".join(sql_parts)) if sql_parts else ""
