from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class LogisticsDataQaRepository:
    """物流数据问答仓储。

    设计原则：
        1. 只访问白名单表；
        2. 所有 SQL 都使用参数绑定；
        3. 不允许任意自然语言直接拼接 SQL。
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.ensure_runtime_columns()

    REGION_CASE_SQL = """
        CASE
            WHEN NULLIF(TRIM(st.delivery_area), '') IS NOT NULL THEN TRIM(st.delivery_area)
            WHEN st.delivery_province IN ('上海市', '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省') THEN '华东'
            WHEN st.delivery_province IN ('广东省', '广西壮族自治区', '海南省') THEN '华南'
            WHEN st.delivery_province IN ('河南省', '湖北省', '湖南省') THEN '华中'
            WHEN st.delivery_province IN ('北京市', '天津市', '河北省', '山西省', '内蒙古自治区') THEN '华北'
            WHEN st.delivery_province IN ('重庆市', '四川省', '贵州省', '云南省', '西藏自治区') THEN '西南'
            WHEN st.delivery_province IN ('陕西省', '甘肃省', '青海省', '宁夏回族自治区', '新疆维吾尔自治区') THEN '西北'
            WHEN st.delivery_province IN ('辽宁省', '吉林省', '黑龙江省') THEN '东北'
            ELSE '其他'
        END
    """

    REGION_SOURCE_SQL = """
        CASE
            WHEN NULLIF(TRIM(st.delivery_area), '') IS NOT NULL THEN 'delivery_area'
            WHEN st.delivery_province IS NOT NULL AND st.delivery_province <> '' THEN 'delivery_province'
            ELSE 'other'
        END
    """

    PROJECT_TOTAL_TRUCKS_SQL = """
        CASE
            WHEN st.project_name IS NULL OR st.project_name = '' THEN NULL
            WHEN SUBSTRING_INDEX(SUBSTRING_INDEX(st.project_name, '-', 3), '-', -1) REGEXP '^[0-9]+(\\.[0-9]+)?$'
                THEN CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(st.project_name, '-', 3), '-', -1) AS DECIMAL(18,2))
            ELSE NULL
        END
    """

    PICKUP_DATE_SQL = "COALESCE(st.pickup_date, STR_TO_DATE(JSON_UNQUOTE(JSON_EXTRACT(ost.raw_json, '$.pickup_date')), '%Y-%m-%d'))"

    def ensure_runtime_columns(self) -> None:
        """确保物流数据问答 MVP 需要的扩展列存在。

        说明：
            1. 当前本地库里的 2026 数据链路最初未预留这些字段；
            2. 这里补齐结构，不伪造字段值；
            3. 后续同步可把真实值灌进这些列。
        """
        column_specs = [
            ("ods_logistic_ship_task", "project_name", "VARCHAR(255) NULL AFTER company_id"),
            ("ods_logistic_ship_task", "pickup_date", "DATE NULL AFTER project_name"),
            ("ods_logistic_ship_task", "expand_dept", "VARCHAR(128) NULL AFTER ship_type"),
            ("ods_logistic_ship_task", "entrusted_person", "VARCHAR(128) NULL AFTER expand_dept"),
            ("ods_logistic_ship_product", "price", "DECIMAL(18,2) NULL AFTER quantity"),
            ("dwd_logistics_ship_task", "project_name", "VARCHAR(255) NULL AFTER company_name"),
            ("dwd_logistics_ship_task", "pickup_date", "DATE NULL AFTER project_name"),
            ("dwd_logistics_ship_task", "expand_dept", "VARCHAR(128) NULL AFTER ship_type"),
            ("dwd_logistics_ship_task", "entrusted_person", "VARCHAR(128) NULL AFTER expand_dept"),
            ("dwd_logistics_ship_task", "normalized_region_name", "VARCHAR(32) NULL AFTER delivery_area"),
            ("dwd_logistics_ship_task", "region_resolve_source", "VARCHAR(32) NULL AFTER normalized_region_name"),
            ("dwd_logistics_ship_product", "price", "DECIMAL(18,2) NULL AFTER quantity"),
        ]
        for table_name, column_name, column_sql in column_specs:
            self._ensure_column(table_name=table_name, column_name=column_name, column_sql=column_sql)
        self.db.execute(
            text(
                f"""
                UPDATE dwd_logistics_ship_task st
                SET normalized_region_name = {self.REGION_CASE_SQL},
                    region_resolve_source = {self.REGION_SOURCE_SQL}
                WHERE normalized_region_name IS NULL OR region_resolve_source IS NULL
                """
            )
        )
        self.db.commit()

    def _ensure_column(self, *, table_name: str, column_name: str, column_sql: str) -> None:
        """按“先查列、后增列”的方式兼容补字段。

        说明：
            1. 当前本机 MySQL 版本不支持 ADD COLUMN IF NOT EXISTS；
            2. 这里先查 information_schema，避免重复加列报错；
            3. 该方法只负责结构补齐，不负责字段值回填。
        """
        exists = self.db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = :table_name
                  AND COLUMN_NAME = :column_name
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        ).scalar()
        if exists:
            return
        self.db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"))

    def verify_assets(self) -> dict[str, Any]:
        """核验当前真实数据资产。

        返回：
            各关键表是否存在、记录数、来源范围等信息。
        """
        tables = {
            "hist_detail": "dwd_logistics_hist_shipment_detail",
            "sys_ship_task": "dwd_logistics_ship_task",
            "sys_ship_product": "dwd_logistics_ship_product",
            "sys_assign_task": "dwd_logistics_assign_task",
            "sys_assign_detail": "dwd_logistics_assign_detail",
            "detail_union": "dws_logistics_detail_union",
            "monthly_metric": "dws_logistics_monthly_metric",
            "carrier_master": "dwd_logistics_company",
        }
        result: dict[str, Any] = {}
        for key, table in tables.items():
            count = self.db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
            result[key] = {"table": table, "row_count": int(count)}
        source_ranges = self.db.execute(
            text(
                """
                SELECT source_type, MIN(biz_date) AS min_date, MAX(biz_date) AS max_date, COUNT(*) AS row_count
                FROM dws_logistics_detail_union
                GROUP BY source_type
                ORDER BY source_type
                """
            )
        ).mappings().all()
        result["detail_union_ranges"] = [dict(row) for row in source_ranges]
        result["source_field_availability"] = dict(
            self.db.execute(
                text(
                    """
                    SELECT
                        SUM(CASE WHEN project_name IS NOT NULL AND project_name <> '' THEN 1 ELSE 0 END) AS project_name_count,
                        SUM(CASE WHEN pickup_date IS NOT NULL THEN 1 ELSE 0 END) AS pickup_date_count,
                        SUM(CASE WHEN expand_dept IS NOT NULL AND expand_dept <> '' THEN 1 ELSE 0 END) AS expand_dept_count,
                        SUM(CASE WHEN entrusted_person IS NOT NULL AND entrusted_person <> '' THEN 1 ELSE 0 END) AS entrusted_person_count
                    FROM ods_logistic_ship_task
                    """
                )
            )
            .mappings()
            .first()
        )
        product_field_availability = dict(
            self.db.execute(
                text(
                    """
                    SELECT
                        SUM(CASE WHEN price IS NOT NULL THEN 1 ELSE 0 END) AS price_count,
                        SUM(CASE WHEN power IS NOT NULL THEN 1 ELSE 0 END) AS power_count,
                        COUNT(*) AS product_row_count
                    FROM ods_logistic_ship_product
                    """
                )
            )
            .mappings()
            .first()
        )
        result["source_field_availability"]["price_count"] = product_field_availability["price_count"]
        result["source_field_availability"]["power_count"] = product_field_availability["power_count"]
        result["source_field_availability"]["product_row_count"] = product_field_availability["product_row_count"]
        result["table_columns"] = {
            table: self._list_columns(table)
            for table in (
                "dwd_logistics_hist_shipment_detail",
                "dwd_logistics_ship_task",
                "dwd_logistics_ship_product",
                "dwd_logistics_assign_task",
                "dwd_logistics_assign_detail",
                "dws_logistics_detail_union",
            )
        }
        return result

    def hist_total_fee_city_rank(self, *, year: int, province: str, top_n: int) -> dict[str, Any]:
        """历史总费用按城市排名。"""
        total_fee = self.db.execute(
            text(
                """
                SELECT ROUND(SUM(total_fee), 0)
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year = :year AND province = :province
                """
            ),
            {"year": year, "province": province},
        ).scalar()
        rows = self.db.execute(
            text(
                """
                SELECT city, ROUND(SUM(total_fee), 0) AS total_fee
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year = :year AND province = :province
                GROUP BY city
                ORDER BY total_fee DESC
                LIMIT :limit_value
                """
            ),
            {"year": year, "province": province, "limit_value": top_n},
        ).mappings().all()
        return {"total_fee": total_fee, "items": [dict(row) for row in rows]}

    def hist_avg_fee_by_month(
        self,
        *,
        year: int,
        origin_place: str,
        province: str,
        vehicle_type: str,
    ) -> dict[str, Any]:
        """历史月均运费。

        返回：
            1. 按月平均运费表；
            2. 整体样本平均；
            3. 月均值再平均。

        说明：
            Q02 的正式基线已明确要求把两种均值口径都说清楚，
            因此仓储层直接返回这两个摘要数值，避免服务层重复拼 SQL。
        """
        rows = self.db.execute(
            text(
                """
                SELECT biz_month, ROUND(AVG(total_fee), 0) AS avg_fee
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year = :year
                  AND origin_place = :origin_place
                  AND province = :province
                  AND required_vehicle_type LIKE :vehicle_type
                GROUP BY biz_month
                ORDER BY biz_month
                """
            ),
            {
                "year": year,
                "origin_place": origin_place,
                "province": province,
                "vehicle_type": f"%{vehicle_type}%",
            },
        ).mappings().all()
        overall = self.db.execute(
            text(
                """
                SELECT ROUND(AVG(total_fee), 0)
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year = :year
                  AND origin_place = :origin_place
                  AND province = :province
                  AND required_vehicle_type LIKE :vehicle_type
                """
            ),
            {
                "year": year,
                "origin_place": origin_place,
                "province": province,
                "vehicle_type": f"%{vehicle_type}%",
            },
        ).scalar()
        avg_of_monthly_avgs = self.db.execute(
            text(
                """
                SELECT ROUND(AVG(avg_fee), 0)
                FROM (
                    SELECT AVG(total_fee) AS avg_fee
                    FROM dwd_logistics_hist_shipment_detail
                    WHERE biz_year = :year
                      AND origin_place = :origin_place
                      AND province = :province
                      AND required_vehicle_type LIKE :vehicle_type
                    GROUP BY biz_month
                ) t
                """
            ),
            {
                "year": year,
                "origin_place": origin_place,
                "province": province,
                "vehicle_type": f"%{vehicle_type}%",
            },
        ).scalar()
        return {
            "overall_avg_fee": overall,
            "avg_of_monthly_avgs": avg_of_monthly_avgs,
            "items": [dict(row) for row in rows],
        }

    def hist_avg_fee_per_watt_by_transport(self, *, region_name: str) -> list[dict[str, Any]]:
        """历史元/瓦按运输方式排序。

        口径说明：
            1. 把“汽运”归一到“公路”；
            2. 平均元/瓦使用 SUM(total_fee) / SUM(actual_watt) 的加权口径，避免直接平均单行 fee_per_watt 造成小票据权重过高。
        """
        rows = self.db.execute(
            text(
                """
                SELECT
                    CASE WHEN transport_mode IN ('汽运', '公路') THEN '公路' ELSE transport_mode END AS transport_mode,
                    ROUND(SUM(total_fee) / NULLIF(SUM(actual_watt), 0), 6) AS avg_fee_per_watt,
                    ROUND(SUM(total_fee), 0) AS total_fee,
                    ROUND(SUM(actual_watt), 0) AS shipment_watt,
                    COUNT(*) AS row_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE region_name = :region_name
                  AND actual_watt IS NOT NULL
                  AND actual_watt > 0
                GROUP BY CASE WHEN transport_mode IN ('汽运', '公路') THEN '公路' ELSE transport_mode END
                ORDER BY avg_fee_per_watt ASC
                """
            ),
            {"region_name": region_name},
        ).mappings().all()
        return [dict(row) for row in rows]

    def hist_extra_fee_ratio_peak_month(self, *, year: int) -> dict[str, Any] | None:
        """历史额外费用占比最高月份。"""
        row = self.db.execute(
            text(
                """
                SELECT
                    biz_month,
                    ROUND(SUM(extra_fee), 0) AS extra_fee_amount,
                    ROUND(SUM(total_fee), 0) AS total_fee_amount,
                    ROUND(100 * SUM(extra_fee) / NULLIF(SUM(total_fee), 0), 1) AS extra_fee_ratio
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year = :year
                GROUP BY biz_month
                ORDER BY extra_fee_ratio DESC
                LIMIT 1
                """
            ),
            {"year": year},
        ).mappings().first()
        return dict(row) if row else None

    def hist_total_fee_by_origin_and_carrier(self, *, year: int, origin_place: str, carrier_name: str) -> dict[str, Any]:
        """历史基地+承运商总运费。"""
        total = self.db.execute(
            text(
                """
                SELECT ROUND(SUM(total_fee), 0)
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year = :year
                  AND origin_place = :origin_place
                  AND logistics_company_name LIKE :carrier_name
                """
            ),
            {"year": year, "origin_place": origin_place, "carrier_name": f"%{carrier_name}%"},
        ).scalar()
        return {"total_fee": total}

    def hist_top_customers_fee_and_mw_by_province(
        self,
        *,
        year: int | None,
        province: str,
        top_n: int = 5,
    ) -> list[dict[str, Any]]:
        """历史省份内按客户统计前 N 名费用与发运量。

        口径说明：
            1. 总费用直接汇总历史台账 total_fee；
            2. 发运量按 actual_watt 汇总后折算 MW；
            3. 当前排名按总费用降序，更贴近业务“前五名客户费用”问法。
            4. 当 year 为空时，按 2023–2025 历史累计口径统计。
        """
        filters = [
            "province = :province",
            "customer_name IS NOT NULL",
            "TRIM(customer_name) <> ''",
        ]
        params: dict[str, Any] = {"province": province, "limit_value": top_n}
        if year is not None:
            filters.insert(0, "biz_year = :year")
            params["year"] = year
        where_sql = " AND ".join(filters)
        rows = self.db.execute(
            text(
                f"""
                SELECT
                    customer_name,
                    ROUND(SUM(total_fee), 0) AS total_fee,
                    ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                GROUP BY customer_name
                ORDER BY total_fee DESC, shipment_mw DESC, customer_name ASC
                LIMIT :limit_value
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def hist_total_fee_by_province(
        self,
        *,
        province: str,
        year: int | None = None,
        years: list[int] | None = None,
    ) -> dict[str, Any]:
        """历史按省份汇总总费用。

        参数：
            province: 目的省份。
            year: 可选年份；为空时按 2023–2025 历史累计统计。
            years: 可选年份列表；用于“2023到2025年江苏总运费”这类明确跨年范围。

        返回：
            包含总费用、总发运量和命中行数的结构化字典。

        说明：
            1. “历史发运”默认落在 2023–2025 台账累计；
            2. 如用户明确给出年份，则只按单年统计；
            3. 该能力主要服务于 Top200 高频省份总费用题族。
        """
        filters = ["province = :province"]
        params: dict[str, Any] = {"province": province}
        if years:
            safe_years = [int(item) for item in years if int(item) in {2023, 2024, 2025}]
            if safe_years:
                year_placeholders = ", ".join(str(item) for item in safe_years)
                filters.append(f"biz_year IN ({year_placeholders})")
                scope_label = f"{min(safe_years)}-{max(safe_years)}年" if len(safe_years) > 1 else f"{safe_years[0]}年"
            else:
                filters.append("biz_year IN (2023, 2024, 2025)")
                scope_label = "2023-2025历史累计"
        elif year is None:
            filters.append("biz_year IN (2023, 2024, 2025)")
            scope_label = "2023-2025历史累计"
        else:
            filters.append("biz_year = :year")
            params["year"] = year
            scope_label = f"{year}年"
        where_sql = " AND ".join(filters)
        row = self.db.execute(
            text(
                f"""
                SELECT
                    ROUND(SUM(total_fee), 0) AS total_fee,
                    ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw,
                    ROUND(SUM(COALESCE(shipment_trip_count, 0)), 0) AS shipment_trip_count,
                    COUNT(*) AS row_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                """
            ),
            params,
        ).mappings().first()
        payload = dict(row or {})
        payload["scope_label"] = scope_label
        return payload

    def hist_total_fee_summary(
        self,
        *,
        year: int,
        months: list[int] | None = None,
        region_name: str | None = None,
        transport_mode: str | None = None,
        carrier_name: str | None = None,
        customer_name: str | None = None,
    ) -> dict[str, Any]:
        """历史总运费通用汇总。

        参数：
            year: 统计年份，只允许 2023–2025 历史台账年份。
            months: 可选月份列表；为空时统计全年。
            region_name: 可选目的区域过滤。
            transport_mode: 可选运输方式过滤，公路会兼容历史台账里的“汽运”。
            carrier_name: 可选承运商过滤，按物流公司名称模糊匹配。
            customer_name: 可选客户过滤，按客户名称模糊匹配。

        返回：
            包含总运费、发运量、行数和可选占比的结构化统计结果。

        说明：
            1. 该方法服务于 903 全量 B 类补槽后续答闭环中高频“总运费”题族；
            2. 仍然只访问历史明细白名单表，不接受任意 SQL；
            3. 当按承运商或客户过滤时，同时返回其占当年同口径总运费的比例，便于回答“占比”问法。
        """
        filters = ["biz_year = :year"]
        denominator_filters = ["biz_year = :year"]
        params: dict[str, Any] = {"year": year}
        if months:
            month_placeholders = ", ".join(str(int(month)) for month in months)
            filters.append(f"MONTH(biz_date) IN ({month_placeholders})")
            denominator_filters.append(f"MONTH(biz_date) IN ({month_placeholders})")
        if region_name:
            filters.append("region_name = :region_name")
            denominator_filters.append("region_name = :region_name")
            params["region_name"] = region_name
        if transport_mode:
            if transport_mode == "公路":
                filters.append("transport_mode IN ('公路', '汽运')")
                denominator_filters.append("transport_mode IN ('公路', '汽运')")
            else:
                filters.append("transport_mode = :transport_mode")
                denominator_filters.append("transport_mode = :transport_mode")
                params["transport_mode"] = transport_mode
        if carrier_name:
            filters.append("logistics_company_name LIKE :carrier_name")
            params["carrier_name"] = f"%{carrier_name}%"
        if customer_name:
            filters.append("customer_name LIKE :customer_name")
            params["customer_name"] = f"%{customer_name}%"
        where_sql = " AND ".join(filters)
        denominator_where_sql = " AND ".join(denominator_filters)
        row = self.db.execute(
            text(
                f"""
                SELECT
                    ROUND(SUM(total_fee), 0) AS total_fee,
                    ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw,
                    ROUND(SUM(COALESCE(shipment_trip_count, 0)), 0) AS shipment_trip_count,
                    COUNT(*) AS row_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                """
            ),
            params,
        ).mappings().first()
        denominator_params = {
            key: value
            for key, value in params.items()
            if key not in {"carrier_name", "customer_name"}
        }
        denominator_total_fee = self.db.execute(
            text(
                f"""
                SELECT ROUND(SUM(total_fee), 0)
                FROM dwd_logistics_hist_shipment_detail
                WHERE {denominator_where_sql}
                """
            ),
            denominator_params,
        ).scalar()
        payload = dict(row or {})
        total_fee = float(payload.get("total_fee") or 0)
        denominator = float(denominator_total_fee or 0)
        payload["scope_label"] = f"{year}年" + ("".join(f"{month}月" for month in months) if months else "全年")
        payload["denominator_total_fee"] = denominator_total_fee
        payload["total_fee_share_pct"] = round(total_fee / denominator * 100, 2) if denominator else None
        return payload

    def hist_carrier_kpi_by_year(self, *, year: int) -> dict[str, Any]:
        """历史年度承运商 KPI 统计。

        返回：
            1. 各承运商的发运量 MW；
            2. 发运量占比；
            3. 运费总额。

        说明：
            1. 发运量默认按瓦数口径，折算为 MW；
            2. 占比基于当年全部承运商的总发运量；
            3. 统一兼容“承运商 / 物流公司 / 物流供应商”问法。
        """
        total_shipment_mw = self.db.execute(
            text(
                """
                SELECT ROUND(SUM(actual_watt) / 1000000, 3)
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year = :year
                  AND logistics_company_name IS NOT NULL
                  AND TRIM(logistics_company_name) <> ''
                """
            ),
            {"year": year},
        ).scalar()
        rows = self.db.execute(
            text(
                """
                SELECT
                    logistics_company_name AS carrier_name,
                    ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw,
                    ROUND(
                        100 * SUM(actual_watt) / NULLIF((
                            SELECT SUM(actual_watt)
                            FROM dwd_logistics_hist_shipment_detail
                            WHERE biz_year = :year
                              AND logistics_company_name IS NOT NULL
                              AND TRIM(logistics_company_name) <> ''
                        ), 0),
                        2
                    ) AS shipment_share_pct,
                    ROUND(SUM(total_fee), 0) AS total_fee
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year = :year
                  AND logistics_company_name IS NOT NULL
                  AND TRIM(logistics_company_name) <> ''
                GROUP BY logistics_company_name
                ORDER BY shipment_mw DESC, total_fee DESC, logistics_company_name ASC
                """
            ),
            {"year": year},
        ).mappings().all()
        return {
            "total_shipment_mw": total_shipment_mw,
            "items": [dict(row) for row in rows],
        }

    def hist_mw_summary(
        self,
        *,
        year: int,
        months: list[int] | None = None,
        customer_name: str | None = None,
        region_name: str | None = None,
        origin_place: str | None = None,
        carrier_name: str | None = None,
        transport_mode: str | None = None,
    ) -> dict[str, Any]:
        """历史 MW 汇总。

        说明：
            1. 统一承接客户、区域、始发地、承运商等单值过滤；
            2. 发运量固定按 actual_watt 汇总后除以 1,000,000；
            3. 该方法只返回单值汇总，不负责分组拆分。
        """
        filters = ["biz_year = :year"]
        params: dict[str, Any] = {"year": year}
        if months:
            month_placeholders = ", ".join(str(int(month)) for month in months)
            filters.append(f"MONTH(biz_date) IN ({month_placeholders})")
        if customer_name:
            filters.append("customer_name LIKE :customer_name")
            # 客户简称可能出现在客户全称中间，例如“创维”对应“南京创维光伏科技有限公司”。
            # 这里使用包含匹配，仍只作用于已由 planner 抽取出的客户槽位。
            params["customer_name"] = f"%{customer_name}%"
        if region_name:
            filters.append("region_name = :region_name")
            params["region_name"] = region_name
        if origin_place:
            filters.append("origin_place = :origin_place")
            params["origin_place"] = origin_place
        if carrier_name:
            filters.append("logistics_company_name LIKE :carrier_name")
            params["carrier_name"] = f"%{carrier_name}%"
        if transport_mode:
            if transport_mode == "公路":
                filters.append("transport_mode IN ('公路', '汽运')")
            elif transport_mode == "铁路":
                filters.append("transport_mode IN ('铁路', '铁运')")
            else:
                filters.append("transport_mode = :transport_mode")
                params["transport_mode"] = transport_mode
        where_sql = " AND ".join(filters)
        shipment_mw = self.db.execute(
            text(
                f"""
                SELECT ROUND(SUM(actual_watt) / 1000000, 3)
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                """
            ),
            params,
        ).scalar()
        return {"shipment_mw": shipment_mw}

    def mixed_mw_summary_2023_2026(
        self,
        *,
        months: list[int] | None = None,
        region_name: str | None = None,
        transport_mode: str | None = None,
    ) -> dict[str, Any]:
        """2023-2026 全时间发运量汇总。

        参数：
            months: 可选月份过滤；为空时统计 2023-2026 全部月份。
            region_name: 可选区域过滤。
            transport_mode: 可选运输方式过滤。

        返回：
            包含历史 2023-2025、系统 2026 与合计 MW 的字典。

        业务逻辑：用户没有给年月日时，按产品要求默认查询 2023-2026 全时间；
        其中 2023-2025 使用历史台账 actual_watt，2026 使用正式系统 power × quantity。
        """

        filters = ["biz_year IN (2023, 2024, 2025)"]
        params: dict[str, Any] = {}
        if months:
            month_placeholders = ", ".join(str(int(month)) for month in months)
            filters.append(f"MONTH(biz_date) IN ({month_placeholders})")
        if region_name:
            filters.append("region_name = :region_name")
            params["region_name"] = region_name
        if transport_mode:
            if transport_mode == "公路":
                filters.append("transport_mode IN ('公路', '汽运')")
            elif transport_mode == "铁路":
                filters.append("transport_mode IN ('铁路', '铁运')")
            else:
                filters.append("transport_mode = :transport_mode")
                params["transport_mode"] = transport_mode
        where_sql = " AND ".join(filters)
        hist_row = self.db.execute(
            text(
                f"""
                SELECT
                    ROUND(SUM(actual_watt) / 1000000, 3) AS hist_shipment_mw,
                    COUNT(*) AS hist_row_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                """
            ),
            params,
        ).mappings().first()
        sys_row = self.sys_mw_and_trip_count(
            year=2026,
            months=months,
            transport_mode=transport_mode,
            region_name=region_name,
        )
        hist_mw = float((hist_row or {}).get("hist_shipment_mw") or 0)
        sys_mw = float(sys_row.get("shipment_mw") or 0)
        return {
            "scope_label": "2023-2026年",
            "shipment_mw": round(hist_mw + sys_mw, 3),
            "hist_shipment_mw": hist_mw,
            "sys_2026_shipment_mw": sys_mw,
            "hist_row_count": int((hist_row or {}).get("hist_row_count") or 0),
            "sys_2026_task_count": int(sys_row.get("strict_scope_task_count") or 0),
            "sys_2026_power_missing_count": int(sys_row.get("power_missing_count") or 0),
        }

    def mixed_total_fee_summary_2023_2026(
        self,
        *,
        months: list[int] | None = None,
        region_name: str | None = None,
        transport_mode: str | None = None,
        carrier_name: str | None = None,
        customer_name: str | None = None,
    ) -> dict[str, Any]:
        """2023-2026 全时间总运费汇总。

        参数：
            months: 可选月份过滤；为空时统计全部月份。
            region_name: 可选区域过滤。
            transport_mode: 可选运输方式过滤。
            carrier_name: 可选承运商过滤。
            customer_name: 可选客户过滤。

        返回：
            包含历史 2023-2025、系统 2026 与合计总运费的字典。

        业务逻辑：无时间条件默认 2023-2026；历史侧使用 total_fee，2026 侧复用正式系统费用口径。
        """

        filters = ["biz_year IN (2023, 2024, 2025)"]
        params: dict[str, Any] = {}
        if months:
            month_placeholders = ", ".join(str(int(month)) for month in months)
            filters.append(f"MONTH(biz_date) IN ({month_placeholders})")
        if region_name:
            filters.append("region_name = :region_name")
            params["region_name"] = region_name
        if transport_mode:
            if transport_mode == "公路":
                filters.append("transport_mode IN ('公路', '汽运')")
            elif transport_mode == "铁路":
                filters.append("transport_mode IN ('铁路', '铁运')")
            else:
                filters.append("transport_mode = :transport_mode")
                params["transport_mode"] = transport_mode
        if carrier_name:
            filters.append("logistics_company_name LIKE :carrier_name")
            params["carrier_name"] = f"%{carrier_name}%"
        if customer_name:
            filters.append("customer_name LIKE :customer_name")
            params["customer_name"] = f"%{customer_name}%"
        where_sql = " AND ".join(filters)
        hist_row = self.db.execute(
            text(
                f"""
                SELECT
                    ROUND(SUM(total_fee), 0) AS hist_total_fee,
                    ROUND(SUM(actual_watt) / 1000000, 3) AS hist_shipment_mw,
                    COUNT(*) AS hist_row_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                """
            ),
            params,
        ).mappings().first()
        sys_row = self.sys_total_fee_by_filters(
            year=2026,
            months=months,
            company_name=carrier_name,
            customer_name=customer_name,
            transport_mode=transport_mode,
            region_name=region_name,
        )
        hist_total_fee = float((hist_row or {}).get("hist_total_fee") or 0)
        sys_total_fee = float(sys_row.get("total_fee") or 0)
        return {
            "scope_label": "2023-2026年",
            "total_fee": round(hist_total_fee + sys_total_fee, 2),
            "hist_total_fee": hist_total_fee,
            "sys_2026_total_fee": sys_total_fee,
            "shipment_mw": float((hist_row or {}).get("hist_shipment_mw") or 0),
            "hist_row_count": int((hist_row or {}).get("hist_row_count") or 0),
            "sys_2026_task_count": int(sys_row.get("task_count") or 0),
            "sys_2026_parse_fail_count": int(sys_row.get("parse_fail_count") or 0),
            "sys_2026_price_missing_count": int(sys_row.get("price_missing_count") or 0),
        }

    def hist_product_spec_mw_summary(self, *, product_spec: str) -> dict[str, Any]:
        """历史规格总发运瓦数。

        参数：
            product_spec: 题面中的组件规格文本。

        返回：
            2023-2025 历史累计发运量、命中记录数和命中规格数。

        说明：
            1. “历史发运”默认锁定 2023-2025 历史台账；
            2. 规格按 product_spec 模糊匹配，避免同一规格存在轻微文本后缀时漏算；
            3. 发运量仍按 actual_watt 汇总后折算 MW。
        """

        row = self.db.execute(
            text(
                """
                SELECT
                    ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw,
                    ROUND(SUM(actual_watt), 0) AS shipment_watt,
                    COUNT(*) AS row_count,
                    COUNT(DISTINCT product_spec) AS matched_spec_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year IN (2023, 2024, 2025)
                  AND product_spec LIKE :product_spec
                """
            ),
            {"product_spec": f"%{product_spec}%"},
        ).mappings().first()
        return dict(row or {})

    def hist_transport_mode_record_summary(
        self,
        *,
        transport_mode: str,
        years: list[int] | None = None,
    ) -> dict[str, Any]:
        """历史运输方式发运记录数与占比。

        参数：
            transport_mode: 标准运输方式。
            years: 可选年份列表；为空时按 2023-2025 历史累计。

        返回：
            发运记录数、总记录数、占比及省份/月度分布。

        说明：
            1. 公路口径合并“公路/汽运”；
            2. 铁路口径合并“铁路/铁运”；
            3. 水路、多式联运按原字段值直接过滤。
        """

        years = years or [2023, 2024, 2025]
        params: dict[str, Any] = {f"year_{idx}": year for idx, year in enumerate(years)}
        year_sql = ", ".join(f":year_{idx}" for idx, _ in enumerate(years))
        mode_filter, mode_params = self._transport_mode_filter_sql(transport_mode)
        params.update(mode_params)
        total_count = self.db.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year IN ({year_sql})
                """
            ),
            params,
        ).scalar()
        record_count = self.db.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year IN ({year_sql})
                  AND {mode_filter}
                """
            ),
            params,
        ).scalar()
        province_rows = self.db.execute(
            text(
                f"""
                SELECT province, COUNT(*) AS record_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year IN ({year_sql})
                  AND {mode_filter}
                GROUP BY province
                ORDER BY record_count DESC, province ASC
                LIMIT 10
                """
            ),
            params,
        ).mappings().all()
        month_rows = self.db.execute(
            text(
                f"""
                    SELECT
                        MONTH(biz_date) AS biz_month,
                        COUNT(*) AS record_count
                    FROM dwd_logistics_hist_shipment_detail
                    WHERE biz_year IN ({year_sql})
                      AND {mode_filter}
                    GROUP BY MONTH(biz_date)
                    ORDER BY record_count DESC, biz_month ASC
                    LIMIT 10
                """
            ),
            params,
        ).mappings().all()
        total = int(total_count or 0)
        count = int(record_count or 0)
        return {
            "transport_mode": transport_mode,
            "years": years,
            "record_count": count,
            "total_record_count": total,
            "record_share_pct": round(count / total * 100, 2) if total else None,
            "top_provinces": [dict(row) for row in province_rows],
            "top_months": [dict(row) for row in month_rows],
        }

    def hist_remark_keyword_fee_ratio(self, *, keywords: list[str]) -> dict[str, Any]:
        """历史备注关键词费用占比。

        参数：
            keywords: 需要在 remark 字段中匹配的关键词列表。

        返回：
            命中关键词记录的总费用、历史总费用、费用占比和记录数。
        """

        keyword_filters = []
        params: dict[str, Any] = {}
        for idx, keyword in enumerate(keywords):
            key = f"keyword_{idx}"
            keyword_filters.append(f"remark LIKE :{key}")
            params[key] = f"%{keyword}%"
        keyword_sql = " OR ".join(keyword_filters) or "1=0"
        row = self.db.execute(
            text(
                f"""
                SELECT
                    ROUND(SUM(CASE WHEN {keyword_sql} THEN total_fee ELSE 0 END), 0) AS keyword_total_fee,
                    ROUND(SUM(total_fee), 0) AS total_fee,
                    SUM(CASE WHEN {keyword_sql} THEN 1 ELSE 0 END) AS keyword_record_count,
                    COUNT(*) AS total_record_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year IN (2023, 2024, 2025)
                """
            ),
            params,
        ).mappings().first()
        payload = dict(row or {})
        keyword_fee = float(payload.get("keyword_total_fee") or 0)
        total_fee = float(payload.get("total_fee") or 0)
        payload["fee_share_pct"] = round(keyword_fee / total_fee * 100, 2) if total_fee else None
        payload["keywords"] = keywords
        return payload

    def hist_high_fee_addresses_by_customer(
        self,
        *,
        year: int,
        customer_name: str,
        threshold_fee: float,
    ) -> list[dict[str, Any]]:
        """历史客户高运费收货地址明细。

        参数：
            year: 统计年份。
            customer_name: 客户名称前缀或简称。
            threshold_fee: 地址汇总运费阈值。

        返回：
            超过阈值的地址、城市、省份和费用汇总。
        """

        rows = self.db.execute(
            text(
                """
                SELECT
                    address,
                    province,
                    city,
                    ROUND(SUM(total_fee), 0) AS total_fee,
                    ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw,
                    COUNT(*) AS row_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year = :year
                  AND customer_name LIKE :customer_name
                  AND address IS NOT NULL
                  AND TRIM(address) <> ''
                GROUP BY address, province, city
                HAVING SUM(total_fee) > :threshold_fee
                ORDER BY total_fee DESC, address ASC
                """
            ),
            {
                "year": year,
                "customer_name": f"{customer_name}%",
                "threshold_fee": threshold_fee,
            },
        ).mappings().all()
        return [dict(row) for row in rows]

    def hist_quarter_region_metric(self, *, year: int, quarter: str, metric: str) -> list[dict[str, Any]]:
        """历史季度各区域指标汇总。

        参数：
            year: 历史年份。
            quarter: Q1-Q4。
            metric: shipment_mw、total_fee 或 unit_fee_per_watt。

        返回：
            按区域排序的季度指标表。
        """

        quarter_months = {
            "Q1": (1, 2, 3),
            "Q2": (4, 5, 6),
            "Q3": (7, 8, 9),
            "Q4": (10, 11, 12),
        }[quarter]
        month_sql = ", ".join(str(month) for month in quarter_months)
        if metric == "shipment_mw":
            metric_sql = "ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw"
        elif metric == "total_fee":
            metric_sql = "ROUND(SUM(total_fee), 0) AS total_fee"
        else:
            metric_sql = "ROUND(SUM(total_fee) / NULLIF(SUM(actual_watt), 0), 8) AS unit_fee_per_watt"
        rows = self.db.execute(
            text(
                f"""
                SELECT
                    region_name,
                    {metric_sql},
                    ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw,
                    COUNT(*) AS row_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year = :year
                  AND MONTH(biz_date) IN ({month_sql})
                  AND region_name IS NOT NULL
                  AND TRIM(region_name) <> ''
                GROUP BY region_name
                ORDER BY {metric} DESC, region_name ASC
                """
            ),
            {"year": year},
        ).mappings().all()
        return [dict(row) for row in rows]

    def _transport_mode_filter_sql(self, transport_mode: str) -> tuple[str, dict[str, Any]]:
        """生成历史运输方式过滤 SQL 片段。"""

        if transport_mode == "公路":
            return "transport_mode IN ('公路', '汽运')", {}
        if transport_mode == "铁路":
            return "transport_mode IN ('铁路', '铁运')", {}
        return "transport_mode = :transport_mode", {"transport_mode": transport_mode}

    def hist_mw_by_origin_and_carrier(self, *, year: int, origin_place: str, carrier_name: str) -> dict[str, Any]:
        """历史按基地和承运商统计发运量 MW。"""
        return self.hist_mw_summary(year=year, origin_place=origin_place, carrier_name=carrier_name)

    def hist_mw_by_region_province(
        self,
        *,
        year: int,
        region_name: str,
        provinces: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """历史按区域内各省拆分发运量 MW。

        说明：
            1. 当前只用于历史台账口径；
            2. 可选传入省份白名单，兼容“华东各省（江苏、浙江...）”问法；
            3. 返回结果按 MW 降序排列。
        """
        filters = [
            "biz_year = :year",
            "region_name = :region_name",
            "province IS NOT NULL",
            "TRIM(province) <> ''",
        ]
        params: dict[str, Any] = {"year": year, "region_name": region_name}
        if provinces:
            province_placeholders = ", ".join(f":province_{idx}" for idx, _ in enumerate(provinces))
            filters.append(f"province IN ({province_placeholders})")
            for idx, province in enumerate(provinces):
                params[f"province_{idx}"] = province
        where_sql = " AND ".join(filters)
        rows = self.db.execute(
            text(
                f"""
                SELECT
                    province,
                    ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                GROUP BY province
                ORDER BY shipment_mw DESC, province ASC
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def hist_mw_by_all_regions(self, *, year: int) -> list[dict[str, Any]]:
        """历史按区域汇总发运量 MW。"""
        rows = self.db.execute(
            text(
                """
                SELECT
                    region_name,
                    ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year = :year
                  AND region_name IS NOT NULL
                  AND TRIM(region_name) <> ''
                GROUP BY region_name
                ORDER BY shipment_mw DESC, region_name ASC
                """
            ),
            {"year": year},
        ).mappings().all()
        return [dict(row) for row in rows]

    def hist_monthly_total_fee_by_year(self, *, year: int | None = None, years: list[int] | None = None) -> list[dict[str, Any]]:
        """历史按 year-month 月份粒度对比总运费。

        参数：
            year: 单一年份过滤条件，兼容原有“2025 年各月”问法。
            years: 多年份过滤条件，用于“2023–2025 年各月”跨年逐月对比。
        返回：
            按 `YYYY-MM` 升序排列的月度总费用列表。
        """

        safe_years = sorted({int(item) for item in (years or ([year] if year else [])) if int(item) in {2023, 2024, 2025}})
        if not safe_years:
            return []
        year_filter_sql = ", ".join(str(item) for item in safe_years)
        rows = self.db.execute(
            text(
                f"""
                SELECT
                    DATE_FORMAT(biz_date, '%Y-%m') AS biz_month,
                    ROUND(SUM(total_fee), 0) AS total_fee
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year IN ({year_filter_sql})
                  AND biz_date IS NOT NULL
                GROUP BY DATE_FORMAT(biz_date, '%Y-%m')
                ORDER BY biz_month ASC
                """
            )
        ).mappings().all()
        return [dict(row) for row in rows]

    def hist_monthly_metric_by_filters(
        self,
        *,
        years: list[int],
        region_name: str | None = None,
        province: str | None = None,
    ) -> list[dict[str, Any]]:
        """按月份汇总历史发运量和总运费。

        参数：
            years: 需要纳入统计的历史年份列表。
            region_name: 可选区域过滤条件。
            province: 可选目的省份过滤条件。
        返回值：
            按月份排序的汇总表，包含发运量 MW、总运费和记录数。
        """

        safe_years = sorted({int(year) for year in years if int(year) in {2023, 2024, 2025}})
        if not safe_years:
            return []
        filters = [f"biz_year IN ({', '.join(str(year) for year in safe_years)})", "biz_date IS NOT NULL"]
        params: dict[str, Any] = {}
        if region_name:
            filters.append("region_name LIKE :region_name")
            params["region_name"] = f"%{region_name}%"
        if province:
            filters.append("province LIKE :province")
            params["province"] = f"%{province.rstrip('省市区')}%"
        where_sql = " AND ".join(filters)
        rows = self.db.execute(
            text(
                f"""
                SELECT
                    MONTH(biz_date) AS biz_month,
                    ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw,
                    ROUND(SUM(total_fee), 0) AS total_fee,
                    COUNT(*) AS row_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                GROUP BY MONTH(biz_date)
                ORDER BY biz_month ASC
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def hist_unit_fee_per_watt(
        self,
        *,
        year: int,
        province: str | None = None,
        months: list[int] | None = None,
        include_extra_fee: bool = False,
        transport_mode: str | None = None,
        carrier_name: str | None = None,
    ) -> dict[str, Any]:
        """历史单瓦运输成本。

        参数：
            year: 统计年份。
            province: 可选目的省份过滤。
            months: 可选月份过滤。
            include_extra_fee: 是否把 extra_fee 一并纳入分子。
            transport_mode: 可选运输方式过滤，公路/铁路会合并同义写法。
            carrier_name: 可选承运商简称，按物流公司名称模糊匹配。

        说明：
            1. `单瓦价` 默认按 total_fee / actual_watt；
            2. 当业务明确要求“(运费+额外费用)/总W数”时，再纳入 extra_fee。
            3. 承运商过滤只用于已通过 planner 校验的历史承运商别名题族。
        """
        filters = ["biz_year = :year", "actual_watt IS NOT NULL", "actual_watt <> 0"]
        params: dict[str, Any] = {"year": year}
        if province:
            filters.append("province = :province")
            params["province"] = province
        if months:
            month_placeholders = ", ".join(str(int(month)) for month in months)
            filters.append(f"MONTH(biz_date) IN ({month_placeholders})")
        if transport_mode:
            mode_filter, mode_params = self._transport_mode_filter_sql(transport_mode)
            filters.append(mode_filter)
            params.update(mode_params)
        if carrier_name:
            filters.append("logistics_company_name LIKE :carrier_name")
            params["carrier_name"] = f"%{carrier_name}%"
        numerator_sql = "SUM(total_fee)" if not include_extra_fee else "SUM(total_fee) + SUM(COALESCE(extra_fee, 0))"
        where_sql = " AND ".join(filters)
        row = self.db.execute(
            text(
                f"""
                SELECT
                    ROUND({numerator_sql}, 0) AS total_fee_amount,
                    ROUND(SUM(COALESCE(extra_fee, 0)), 0) AS extra_fee_amount,
                    ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw,
                    ROUND(({numerator_sql}) / NULLIF(SUM(actual_watt), 0), 8) AS unit_fee_per_watt
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                """
            ),
            params,
        ).mappings().first()
        return dict(row or {})

    def hist_route_pricing_analysis(
        self,
        *,
        years: list[int],
        vehicle_type: str,
        view_mode: str,
        origin_place: str | None = None,
        province: str | None = None,
        city: str | None = None,
    ) -> dict[str, Any]:
        """历史线路/城市运价分析。

        参数：
            years: 参与统计的年份列表，支持单年和双年对比。
            vehicle_type: 车型口径，当前主要兼容 17.5 / 13m。
            view_mode: 结果模式，支持 avg_fee / monthly_avg / year_compare / fee_extremes。
            origin_place: 可选始发地。
            province: 可选目的省份。
            city: 可选目的城市。

        返回：
            统一返回包含 `view_mode`、`items` 和 `summary_row` 的结构。

        说明：
            1. 该方法服务于 Round2 的历史线路运价题族；
            2. 统计口径固定使用历史台账 total_fee；
            3. 如果目的地给的是城市，则优先按 city 过滤；否则按 province 过滤。
        """
        filters = ["required_vehicle_type LIKE :vehicle_type"]
        params: dict[str, Any] = {"vehicle_type": f"%{vehicle_type}%"}
        year_placeholders = ", ".join(f":year_{idx}" for idx, _ in enumerate(years))
        filters.append(f"biz_year IN ({year_placeholders})")
        for idx, year in enumerate(years):
            params[f"year_{idx}"] = year
        if origin_place:
            filters.append("origin_place = :origin_place")
            params["origin_place"] = origin_place
        if city:
            filters.append("city = :city")
            params["city"] = city
        elif province:
            filters.append("province = :province")
            params["province"] = province
        where_sql = " AND ".join(filters)

        if view_mode == "monthly_avg":
            rows = self.db.execute(
                text(
                    f"""
                    SELECT
                        DATE_FORMAT(biz_date, '%Y-%m') AS biz_month,
                        ROUND(AVG(total_fee), 0) AS avg_fee,
                        COUNT(*) AS row_count
                    FROM dwd_logistics_hist_shipment_detail
                    WHERE {where_sql}
                      AND biz_date IS NOT NULL
                    GROUP BY DATE_FORMAT(biz_date, '%Y-%m')
                    ORDER BY biz_month ASC
                    """
                ),
                params,
            ).mappings().all()
            return {"view_mode": view_mode, "items": [dict(row) for row in rows], "summary_row": None}

        if view_mode == "year_compare":
            rows = self.db.execute(
                text(
                    f"""
                    SELECT
                        biz_year,
                        ROUND(AVG(total_fee), 0) AS avg_fee,
                        COUNT(*) AS row_count
                    FROM dwd_logistics_hist_shipment_detail
                    WHERE {where_sql}
                    GROUP BY biz_year
                    ORDER BY biz_year ASC
                    """
                ),
                params,
            ).mappings().all()
            return {"view_mode": view_mode, "items": [dict(row) for row in rows], "summary_row": None}

        if view_mode == "fee_extremes":
            row = self.db.execute(
                text(
                    f"""
                    SELECT
                        ROUND(MIN(total_fee), 0) AS min_fee,
                        ROUND(MAX(total_fee), 0) AS max_fee,
                        ROUND(AVG(total_fee), 0) AS avg_fee,
                        COUNT(*) AS row_count
                    FROM dwd_logistics_hist_shipment_detail
                    WHERE {where_sql}
                    """
                ),
                params,
            ).mappings().first()
            return {"view_mode": view_mode, "items": [dict(row or {})], "summary_row": dict(row or {})}

        row = self.db.execute(
            text(
                f"""
                SELECT
                    ROUND(AVG(total_fee), 0) AS avg_fee,
                    COUNT(*) AS row_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                """
            ),
            params,
        ).mappings().first()
        return {"view_mode": "avg_fee", "items": [dict(row or {})], "summary_row": dict(row or {})}

    def hist_route_aggregate_summary(
        self,
        *,
        year: int,
        origin_place: str,
        metric: str,
        province: str | None = None,
        city: str | None = None,
    ) -> dict[str, Any]:
        """历史始发地到省/市的线路汇总。

        参数：
            year: 历史台账年份，仅服务 2023–2025。
            origin_place: 始发地，目前主要为合肥、阜宁。
            metric: 统计指标，支持 avg_fee、avg_fee_per_trip 或 shipment_mw。
            province: 可选目的省份。
            city: 可选目的城市。

        返回：
            包含平均运费、发运量 MW、记录数的结构化结果。

        说明：
            1. 这是 B-gap Wave1 的受控 query_key，不写死单题；
            2. 没有车型条件时，平均运费按 AVG(total_fee) 计算，表示该始发-目的范围内的样本平均；
            3. 发运量按 actual_watt 汇总后折算为 MW；
            4. 平均每车运费按 SUM(total_fee) / SUM(shipment_trip_count) 计算。
        """

        filters = ["biz_year = :year", "origin_place = :origin_place"]
        params: dict[str, Any] = {"year": year, "origin_place": origin_place}
        if city:
            filters.append("city LIKE :city")
            params["city"] = f"%{city}%"
        elif province:
            filters.append("province = :province")
            params["province"] = province
        where_sql = " AND ".join(filters)
        row = self.db.execute(
            text(
                f"""
                SELECT
                    ROUND(AVG(total_fee), 0) AS avg_fee,
                    ROUND(SUM(total_fee) / NULLIF(SUM(shipment_trip_count), 0), 0) AS avg_fee_per_trip,
                    ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw,
                    COUNT(*) AS row_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                """
            ),
            params,
        ).mappings().first()
        payload = dict(row or {})
        payload["metric"] = metric
        return payload

    def hist_origin_vehicle_metric_summary(
        self,
        *,
        year: int,
        origin_place: str,
        vehicle_type: str,
        metric: str,
    ) -> dict[str, Any]:
        """历史始发地 + 车型的单车/单瓦成本汇总。

        参数：
            year: 历史台账年份，仅服务 2023–2025。
            origin_place: 始发地，目前主要为合肥、阜宁。
            vehicle_type: 车型口径，例如 17.5、13、9.6。
            metric: 统计指标，支持 avg_fee_per_trip 或 unit_fee_per_watt。

        返回：
            包含单车均费、单瓦价、总费用、发运量和车次的结构化结果。

        说明：
            1. 单车均费 = SUM(total_fee) / SUM(shipment_trip_count)；
            2. 单瓦价 = SUM(total_fee) / SUM(actual_watt)；
            3. 该能力只下推已明确的年份、始发地和车型，不处理模糊评价题。
        """

        row = self.db.execute(
            text(
                """
                SELECT
                    ROUND(SUM(total_fee), 0) AS total_fee,
                    ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw,
                    ROUND(SUM(shipment_trip_count), 0) AS shipment_trip_count,
                    ROUND(SUM(total_fee) / NULLIF(SUM(shipment_trip_count), 0), 2) AS avg_fee_per_trip,
                    ROUND(SUM(total_fee) / NULLIF(SUM(actual_watt), 0), 8) AS unit_fee_per_watt,
                    COUNT(*) AS row_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year = :year
                  AND origin_place = :origin_place
                  AND required_vehicle_type LIKE :vehicle_type
                """
            ),
            {
                "year": year,
                "origin_place": origin_place,
                "vehicle_type": f"%{vehicle_type}%",
            },
        ).mappings().first()
        payload = dict(row or {})
        payload["metric"] = metric
        return payload

    def hist_origin_vehicle_breakdown_summary(
        self,
        *,
        year: int | None = None,
        years: list[int] | None = None,
        origin_place: str | None = None,
        include_origin_dimension: bool = False,
    ) -> list[dict[str, Any]]:
        """按始发地和车型汇总历史车次、费用和平均单车费用。

        参数：
            year: 历史台账年份，仅支持 2023–2025；为空时按 years 多年范围过滤。
            years: 多年历史台账范围，当前用于无时间条件但字段仅存在历史台账的装载托数类问题。
            origin_place: 已校验的始发地；为空时不下推过滤。
            include_origin_dimension: 为空始发地时是否保留“始发地”分组列。
        返回值：
            返回按总费用降序排列的结构化表格行。

        业务说明：
            1. 该方法服务样例题中“某年某始发地不同车型”的多指标汇总；
            2. 平均单车费用使用 SUM(total_fee) / SUM(shipment_trip_count)；
            3. 当问题中的始发地无法在别名表安全校验时，不编造过滤条件，改为展示真实源数据里的始发地分组。
        """

        filters = []
        params: dict[str, Any] = {}
        if year is not None:
            filters.append("biz_year = :year")
            params["year"] = year
        else:
            scoped_years = [int(item) for item in (years or [2023, 2024, 2025]) if int(item) in {2023, 2024, 2025}]
            if not scoped_years:
                scoped_years = [2023, 2024, 2025]
            year_placeholders: list[str] = []
            for index, scoped_year in enumerate(scoped_years):
                key = f"year_{index}"
                year_placeholders.append(f":{key}")
                params[key] = scoped_year
            filters.append(f"biz_year IN ({', '.join(year_placeholders)})")
        if origin_place:
            filters.append("origin_place = :origin_place")
            params["origin_place"] = origin_place
        dimension_columns = ["required_vehicle_type"]
        if include_origin_dimension:
            dimension_columns.insert(0, "origin_place")
        select_dimensions = ", ".join(dimension_columns)
        group_by = ", ".join(dimension_columns)
        rows = self.db.execute(
            text(
                f"""
                SELECT
                    {select_dimensions},
                    ROUND(SUM(COALESCE(shipment_trip_count, 0)), 0) AS shipment_trip_count,
                    ROUND(SUM(COALESCE(actual_qty, 0)), 0) AS shipment_count,
                    ROUND(SUM(COALESCE(total_fee, 0)), 2) AS total_fee,
                    ROUND(SUM(COALESCE(total_fee, 0)) / NULLIF(SUM(COALESCE(shipment_trip_count, 0)), 0), 2) AS avg_fee_per_trip,
                    ROUND(AVG(CASE WHEN pallet_per_vehicle IS NOT NULL THEN pallet_per_vehicle END), 2) AS avg_pallet_per_vehicle,
                    COUNT(pallet_per_vehicle) AS valid_pallet_record_count,
                    COUNT(*) - COUNT(pallet_per_vehicle) AS missing_pallet_record_count,
                    COUNT(*) AS row_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE {" AND ".join(filters)}
                GROUP BY {group_by}
                ORDER BY total_fee DESC
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def hist_monthly_trip_count_summary(self, *, year: int, months: list[int]) -> dict[str, Any]:
        """历史月度总车次汇总。

        参数：
            year: 历史台账年份，仅服务 2023–2025。
            months: 统计月份列表。

        返回：
            包含总车次和命中记录数的结构化结果。

        说明：
            B-gap Wave1 中大量“某年某月总车次”题只缺一个稳定 query_key，
            当前按历史台账 biz_month + shipment_trip_count 做受控汇总。
        """

        month_placeholders = ", ".join(str(int(month)) for month in months)
        row = self.db.execute(
            text(
                f"""
                SELECT
                    ROUND(SUM(shipment_trip_count), 0) AS shipment_trip_count,
                    COUNT(*) AS row_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year = :year
                  AND MONTH(biz_date) IN ({month_placeholders})
                """
            ),
            {"year": year},
        ).mappings().first()
        return dict(row or {})

    def hist_carrier_ranking(
        self,
        *,
        year: int,
        ranking_metric: str,
        top_n: int = 10,
    ) -> list[dict[str, Any]]:
        """历史承运商运费/单瓦成本排名。

        说明：
            1. 该方法统一承接 2024/2025 历史承运商排名题；
            2. `ranking_metric=total_fee` 时按总运费排名；
            3. `ranking_metric=unit_fee_per_watt` 时按 total_fee / actual_watt 排名。
        """
        if ranking_metric == "total_fee":
            rows = self.db.execute(
                text(
                    """
                    SELECT
                        logistics_company_name AS carrier_name,
                        ROUND(SUM(total_fee), 0) AS total_fee,
                        ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw
                    FROM dwd_logistics_hist_shipment_detail
                    WHERE biz_year = :year
                      AND logistics_company_name IS NOT NULL
                      AND TRIM(logistics_company_name) <> ''
                    GROUP BY logistics_company_name
                    ORDER BY total_fee DESC, shipment_mw DESC, carrier_name ASC
                    LIMIT :limit_value
                    """
                ),
                {"year": year, "limit_value": top_n},
            ).mappings().all()
            return [dict(row) for row in rows]

        rows = self.db.execute(
            text(
                """
                SELECT
                    logistics_company_name AS carrier_name,
                    ROUND(SUM(total_fee) / NULLIF(SUM(actual_watt), 0), 8) AS unit_fee_per_watt,
                    ROUND(SUM(total_fee), 0) AS total_fee,
                    ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year = :year
                  AND logistics_company_name IS NOT NULL
                  AND TRIM(logistics_company_name) <> ''
                  AND actual_watt IS NOT NULL
                  AND actual_watt <> 0
                GROUP BY logistics_company_name
                ORDER BY unit_fee_per_watt DESC, total_fee DESC, carrier_name ASC
                LIMIT :limit_value
                """
            ),
            {"year": year, "limit_value": top_n},
        ).mappings().all()
        return [dict(row) for row in rows]

    def hist_trip_count_by_region(self, *, year: int, region_name: str) -> dict[str, Any]:
        """历史总车次。"""
        total = self.db.execute(
            text(
                """
                SELECT ROUND(SUM(shipment_trip_count), 0)
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year = :year AND region_name = :region_name
                """
            ),
            {"year": year, "region_name": region_name},
        ).scalar()
        return {"shipment_trip_count": total}

    def hist_quantity_by_region(self, *, region_name: str, year: int | None = None, transport_mode: str | None = None) -> dict[str, Any]:
        """历史总发运件数。

        参数：
            region_name: 区域名称。
            year: 可选年份过滤。
            transport_mode: 可选运输方式过滤，公路/汽运、铁路/铁运按同义口径合并。

        返回值：包含 `shipment_count` 的汇总字典。
        """
        filters = ["region_name = :region_name"]
        params: dict[str, Any] = {"region_name": region_name}
        # 用户明确给出年份时，件数口径必须按该年份过滤；未给年份时保留历史累计兼容口径。
        if year:
            filters.append("biz_year = :year")
            params["year"] = year
        if transport_mode:
            mode_filter, mode_params = self._transport_mode_filter_sql(transport_mode)
            filters.append(mode_filter)
            params.update(mode_params)
        where_sql = " AND ".join(filters)
        total = self.db.execute(
            text(
                f"""
                SELECT ROUND(SUM(actual_qty), 0)
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                """
            ),
            params,
        ).scalar()
        return {"shipment_count": total}

    def hist_customer_mw(self, *, customer_name: str, year: int | None = None) -> dict[str, Any]:
        """历史客户发运量 MW。

        口径说明：
            1. 当前客户名存在“项目后缀/客诉组件”等变体；
            2. 为尽量贴近业务问法，这里先按前缀 LIKE 做归并；
            3. 同时返回命中的客户名列表，便于外层输出 warning。
            4. 当 year 为空时，默认按 2023–2025 历史累计统计。
        """
        filters = ["customer_name LIKE :customer_name"]
        params: dict[str, Any] = {"customer_name": f"%{customer_name}%"}
        if year is None:
            filters.insert(0, "biz_year IN (2023, 2024, 2025)")
            scope_label = "2023-2025历史累计"
        else:
            filters.insert(0, "biz_year = :year")
            params["year"] = year
            scope_label = f"{year}年"
        where_sql = " AND ".join(filters)
        rows = self.db.execute(
            text(
                f"""
                SELECT customer_name, ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                GROUP BY customer_name
                ORDER BY customer_name
                """
            ),
            params,
        ).mappings().all()
        total = round(sum(float(row["shipment_mw"] or 0) for row in rows), 3)
        return {
            "shipment_mw": total,
            "matched_customer_names": [str(row["customer_name"]) for row in rows],
            "scope_label": scope_label,
        }

    def hist_customer_mw_ranking(
        self,
        *,
        year: int | None = None,
        top_n: int = 10,
    ) -> dict[str, Any]:
        """历史客户发运量 MW 排名。

        参数：
            year: 可选年份；为空时按 2023–2025 历史累计统计。
            top_n: 返回前 N 名客户。

        返回：
            包含统计范围和客户排行列表的结构化结果。

        说明：
            1. 排名口径固定按 actual_watt 汇总后折算为 MW；
            2. 当用户明确说“历史台账”但未给年份时，默认按 2023–2025 历史累计统计；
            3. 该方法只做客户排行，不额外混入费用等其他指标。
        """
        filters = [
            "customer_name IS NOT NULL",
            "TRIM(customer_name) <> ''",
        ]
        params: dict[str, Any] = {"limit_value": top_n}
        if year is None:
            filters.insert(0, "biz_year IN (2023, 2024, 2025)")
            scope_label = "2023-2025历史累计"
        else:
            filters.insert(0, "biz_year = :year")
            params["year"] = year
            scope_label = f"{year}年"
        where_sql = " AND ".join(filters)
        rows = self.db.execute(
            text(
                f"""
                SELECT
                    customer_name,
                    ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                GROUP BY customer_name
                ORDER BY shipment_mw DESC, customer_name ASC
                LIMIT :limit_value
                """
            ),
            params,
        ).mappings().all()
        return {
            "scope_label": scope_label,
            "items": [dict(row) for row in rows],
        }

    def hist_city_carrier_avg_fee_per_trip(
        self,
        *,
        city: str,
        year: int | None = None,
    ) -> dict[str, Any]:
        """历史城市维度承运商平均单价/车。

        参数：
            city: 目的城市。
            year: 可选年份；为空时按 2023–2025 历史累计统计。

        返回：
            包含统计范围和按承运商分组的单车均价列表。

        说明：
            1. 单价/车口径固定为 SUM(total_fee) / SUM(shipment_trip_count)；
            2. 城市按包含匹配，兼容“合肥/合肥市/合肥庐江”等历史台账写法；
            3. 只统计有承运商名称且 shipment_trip_count 大于 0 的记录；
            4. 未给年份时，默认按 2023–2025 历史累计统计。
        """
        filters = [
            "city LIKE :city",
            "logistics_company_name IS NOT NULL",
            "TRIM(logistics_company_name) <> ''",
        ]
        params: dict[str, Any] = {"city": f"%{city}%"}
        if year is None:
            filters.insert(0, "biz_year IN (2023, 2024, 2025)")
            scope_label = "2023-2025历史累计"
        else:
            filters.insert(0, "biz_year = :year")
            params["year"] = year
            scope_label = f"{year}年"
        where_sql = " AND ".join(filters)
        rows = self.db.execute(
            text(
                f"""
                SELECT
                    logistics_company_name AS carrier_name,
                    ROUND(SUM(total_fee) / NULLIF(SUM(shipment_trip_count), 0), 0) AS avg_fee_per_trip,
                    ROUND(SUM(total_fee), 0) AS total_fee,
                    ROUND(SUM(shipment_trip_count), 0) AS shipment_trip_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                GROUP BY logistics_company_name
                HAVING SUM(shipment_trip_count) > 0
                ORDER BY avg_fee_per_trip DESC, total_fee DESC, carrier_name ASC
                """
            ),
            params,
        ).mappings().all()
        return {
            "scope_label": scope_label,
            "items": [dict(row) for row in rows],
        }

    def hist_avg_pallet_per_vehicle(
        self,
        *,
        year: int,
        months: list[int],
        origin_place: str,
    ) -> dict[str, Any]:
        """历史平均每车装载托数。

        参数：
            year: 历史台账年份。
            months: 月份列表；当前由 planner 保证非空。
            origin_place: 始发地，例如合肥、阜宁。
        返回值：
            包含平均托数、有效记录数和总记录数的字典。
        业务逻辑：
            pallet_per_vehicle 是原始历史台账中的“每车装载托数”字段；
            默认只对非空记录求平均，并额外返回空值数量用于答案质量提示。
        """
        month_placeholders = ", ".join(str(int(month)) for month in months)
        row = self.db.execute(
            text(
                f"""
                SELECT
                    ROUND(AVG(pallet_per_vehicle), 2) AS avg_pallet_per_vehicle,
                    COUNT(pallet_per_vehicle) AS valid_record_count,
                    COUNT(*) AS total_record_count,
                    SUM(CASE WHEN pallet_per_vehicle IS NULL THEN 1 ELSE 0 END) AS missing_record_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year = :year
                  AND CAST(SUBSTRING(biz_month, 6, 2) AS UNSIGNED) IN ({month_placeholders})
                  AND origin_place = :origin_place
                """
            ),
            {"year": year, "origin_place": origin_place},
        ).mappings().first()
        return dict(row or {})

    def hist_vehicle_type_trip_count(self, *, year: int, vehicle_type: str, origin_place: str | None = None) -> dict[str, Any]:
        """历史按车型查询总车次。

        参数：
            year: 历史台账年份。
            vehicle_type: 车型口径，例如 17.5、13、9.6。
            origin_place: 可选始发基地；用户明确指定基地时必须下推，避免全车型口径误算。
        返回值：
            包含命中车次合计的字典。
        """
        origin_filter = " AND origin_place = :origin_place" if origin_place else ""
        params = {"year": year, "vehicle_type": f"%{vehicle_type}%"}
        if origin_place:
            params["origin_place"] = origin_place
        total = self.db.execute(
            text(
                f"""
                SELECT ROUND(SUM(shipment_trip_count), 0)
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year = :year
                  AND required_vehicle_type LIKE :vehicle_type
                  {origin_filter}
                """
            ),
            params,
        ).scalar()
        return {"shipment_trip_count": total}

    def hist_multi_origin_customers(self, *, year: int) -> dict[str, Any]:
        """历史同客户多始发地分析。

        口径说明：
            1. 验收基线当前已锁定为原始台账字段“客户名称（标准名称；最终客户）”；
            2. 当前 DWD 标准字段 customer_name 与该原始字段存在口径偏差；
            3. 为了让运行态和正式验收基线严格一致，这里直接使用 raw_row_json 中的原始最终客户字段；
            4. 该题不再回退 customer_name，避免把 119 又回落到 116。
        """
        effective_customer_sql = """
            JSON_UNQUOTE(JSON_EXTRACT(raw_row_json, '$."客户名称（标准名称；最终客户）"'))
        """
        total = self.db.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM (
                    SELECT effective_customer_name
                    FROM (
                        SELECT
                            {effective_customer_sql} AS effective_customer_name,
                            origin_place
                        FROM dwd_logistics_hist_shipment_detail
                        WHERE biz_year = :year
                    ) base
                    WHERE effective_customer_name IS NOT NULL
                      AND TRIM(effective_customer_name) <> ''
                    GROUP BY effective_customer_name
                    HAVING COUNT(DISTINCT origin_place) > 1
                ) t
                """
            ),
            {"year": year},
        ).scalar()
        rows = self.db.execute(
            text(
                f"""
                SELECT
                    effective_customer_name AS customer_name,
                    COUNT(DISTINCT origin_place) AS origin_place_count
                FROM (
                    SELECT
                        {effective_customer_sql} AS effective_customer_name,
                        origin_place
                    FROM dwd_logistics_hist_shipment_detail
                    WHERE biz_year = :year
                ) base
                WHERE effective_customer_name IS NOT NULL
                  AND TRIM(effective_customer_name) <> ''
                GROUP BY customer_name
                HAVING COUNT(DISTINCT origin_place) > 1
                ORDER BY origin_place_count DESC, customer_name ASC
                LIMIT 50
                """
            ),
            {"year": year},
        ).mappings().all()
        return {"customer_count": total, "items": [dict(row) for row in rows]}

    def hist_plan_actual_deviation(self, *, year: int, region_name: str) -> dict[str, Any]:
        """历史计划与实际偏差率。

        口径说明：
            问题文本明确问“件数”，因此按 plan_qty / actual_qty 计算。
        """
        row = self.db.execute(
            text(
                """
                SELECT
                    ROUND(SUM(plan_qty), 0) AS plan_qty_total,
                    ROUND(SUM(actual_qty), 0) AS actual_qty_total,
                    ROUND((SUM(actual_qty) - SUM(plan_qty)) / NULLIF(SUM(plan_qty), 0) * 100, 1) AS deviation_rate
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year = :year
                  AND region_name = :region_name
                  AND plan_qty IS NOT NULL
                  AND actual_qty IS NOT NULL
                """
            ),
            {"year": year, "region_name": region_name},
        ).mappings().first()
        return dict(row or {})

    def sys_mw_and_trip_count(
        self,
        *,
        year: int,
        months: list[int] | None,
        transport_mode: str | None = None,
        base_code: str | None = None,
        region_name: str | None = None,
        special_scope: str | None = None,
        monthly_breakdown: bool = False,
    ) -> dict[str, Any]:
        """2026 系统发运量 MW 与车次。

        口径说明：
            1. MW = SUM(power * quantity) / 1,000,000
            2. power 缺失记录不纳入 MW
            3. 车次 = COUNT(assign_task.task_id) 且状态仅统计 ENTER/LEAVE
            4. 若题目限定基地，则统一按 dwd_logistics_ship_task.base_code 过滤。
            5. monthly_breakdown 只改变返回颗粒度，用于趋势/图表展示，不改变统计口径。
        """
        transport_filter_sql = ""
        params: dict[str, Any] = {"year": year}
        month_filter_sql = ""
        base_filter_sql = ""
        base_filter_plain_sql = ""
        region_filter_sql = ""
        region_filter_plain_sql = ""
        special_filter_sql = ""
        special_filter_plain_sql = ""
        if months:
            month_placeholders = ", ".join(str(int(month)) for month in months)
            month_filter_sql = f" AND MONTH({self.PICKUP_DATE_SQL}) IN ({month_placeholders})"
        if transport_mode:
            transport_filter_sql = " AND st.transport_mode = :transport_mode"
            params["transport_mode"] = transport_mode
        if base_code:
            base_filter_sql = " AND st.base_code = :base_code"
            base_filter_plain_sql = " AND base_code = :base_code"
            params["base_code"] = base_code
        if region_name:
            # 系统侧区域优先使用已同步的 normalized_region_name；为空时用 delivery_area / delivery_province 现场归一，
            # 确保无时间条件默认 2023-2026 时，2026 正式系统数据也能按同一区域口径参与汇总。
            region_filter_sql = f" AND COALESCE(st.normalized_region_name, {self.REGION_CASE_SQL}) = :region_name"
            region_filter_plain_sql = " AND normalized_region_name = :region_name"
            params["region_name"] = region_name
        if special_scope:
            # 特殊业务范围复用系统总运费已锁定过滤条件；同时生成带 st 前缀和纯任务表两套 SQL，
            # 保证 power、车次、任务数和 pickup_date 质量提示使用完全一致的数据范围。
            special_field_sql = {
                "planning": "expand_dept IN ('经营计划', '经营计划部')",
                "sample": "ship_type = '2'",
                "liujuan": "entrusted_person = '刘娟'",
            }[special_scope]
            special_filter_plain_sql = f" AND {special_field_sql}"
            special_filter_sql = f" AND st.{special_field_sql}"
        power_missing_count = self.db.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM dwd_logistics_ship_product sp
                JOIN dwd_logistics_ship_task st ON st.task_id = sp.task_id
                LEFT JOIN ods_logistic_ship_task ost ON ost.task_id = st.task_id
                WHERE YEAR({self.PICKUP_DATE_SQL}) = :year
                  {month_filter_sql}
                  {transport_filter_sql}
                  {base_filter_sql}
                  {region_filter_sql}
                  {special_filter_sql}
                  AND sp.power IS NULL
                """
            ),
            params,
        ).scalar()
        pickup_date_missing_count = self.db.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM dwd_logistics_ship_task
                WHERE biz_year = :year
                  AND pickup_date IS NULL
                  {base_filter_plain_sql}
                  {region_filter_plain_sql}
                  {special_filter_plain_sql}
                """
            ),
            params,
        ).scalar()
        shipment_mw = self.db.execute(
            text(
                f"""
                SELECT ROUND(SUM(sp.power * sp.quantity) / 1000000, 3)
                FROM dwd_logistics_ship_product sp
                JOIN dwd_logistics_ship_task st ON st.task_id = sp.task_id
                LEFT JOIN ods_logistic_ship_task ost ON ost.task_id = st.task_id
                WHERE YEAR({self.PICKUP_DATE_SQL}) = :year
                  {month_filter_sql}
                  {transport_filter_sql}
                  {base_filter_sql}
                  {region_filter_sql}
                  {special_filter_sql}
                  AND sp.power IS NOT NULL
                """
            ),
            params,
        ).scalar()
        shipment_trip_count = self.db.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM dwd_logistics_assign_task at
                JOIN dwd_logistics_ship_task st ON st.task_id = at.ship_task_id
                LEFT JOIN ods_logistic_ship_task ost ON ost.task_id = st.task_id
                WHERE YEAR({self.PICKUP_DATE_SQL}) = :year
                  {month_filter_sql}
                  {transport_filter_sql}
                  {base_filter_sql}
                  {region_filter_sql}
                  {special_filter_sql}
                  AND at.status IN ('ENTER', 'LEAVE')
                """
            ),
            params,
        ).scalar()
        region_coverage = self.db.execute(
            text(
                f"""
                SELECT
                    SUM(CASE WHEN {self.REGION_SOURCE_SQL} = 'delivery_area' THEN 1 ELSE 0 END) AS direct_area_count,
                    SUM(CASE WHEN {self.REGION_SOURCE_SQL} = 'delivery_province' THEN 1 ELSE 0 END) AS province_fallback_count,
                    SUM(CASE WHEN {self.REGION_SOURCE_SQL} = 'other' THEN 1 ELSE 0 END) AS other_count
                FROM dwd_logistics_ship_task st
                LEFT JOIN ods_logistic_ship_task ost ON ost.task_id = st.task_id
                WHERE YEAR({self.PICKUP_DATE_SQL}) = :year
                  {month_filter_sql}
                  {transport_filter_sql}
                  {base_filter_sql}
                  {region_filter_sql}
                  {special_filter_sql}
                """
            ),
            params,
        ).mappings().first()
        strict_scope_task_count = self.db.execute(
            text(
                f"""
                SELECT COUNT(DISTINCT st.task_id)
                FROM dwd_logistics_ship_task st
                LEFT JOIN ods_logistic_ship_task ost ON ost.task_id = st.task_id
                WHERE YEAR({self.PICKUP_DATE_SQL}) = :year
                  {month_filter_sql}
                  {transport_filter_sql}
                  {base_filter_sql}
                  {region_filter_sql}
                  {special_filter_sql}
                """
            ),
            params,
        ).scalar()
        year_task_count = self.db.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM dwd_logistics_ship_task
                WHERE biz_year = :year
                  {base_filter_plain_sql}
                  {region_filter_plain_sql}
                  {special_filter_plain_sql}
                """
            ),
            params,
        ).scalar()
        pickup_date_available_count = self.db.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM dwd_logistics_ship_task
                WHERE biz_year = :year
                  AND pickup_date IS NOT NULL
                  {base_filter_plain_sql}
                  {region_filter_plain_sql}
                  {special_filter_plain_sql}
                """
            ),
            params,
        ).scalar()
        year_region_coverage = self.db.execute(
            text(
                f"""
                SELECT
                    SUM(CASE WHEN region_resolve_source = 'delivery_area' THEN 1 ELSE 0 END) AS direct_area_count,
                    SUM(CASE WHEN region_resolve_source = 'delivery_province' THEN 1 ELSE 0 END) AS province_fallback_count,
                    SUM(CASE WHEN region_resolve_source = 'other' THEN 1 ELSE 0 END) AS other_count
                FROM dwd_logistics_ship_task
                WHERE biz_year = :year
                  {base_filter_plain_sql}
                  {region_filter_plain_sql}
                  {special_filter_plain_sql}
                """
            ),
            params,
        ).mappings().first()
        monthly_rows: list[dict[str, Any]] = []
        if monthly_breakdown:
            mw_rows = self.db.execute(
                text(
                    f"""
                    SELECT
                        DATE_FORMAT({self.PICKUP_DATE_SQL}, '%Y-%m') AS biz_month,
                        ROUND(SUM(sp.power * sp.quantity) / 1000000, 3) AS shipment_mw
                    FROM dwd_logistics_ship_product sp
                    JOIN dwd_logistics_ship_task st ON st.task_id = sp.task_id
                    LEFT JOIN ods_logistic_ship_task ost ON ost.task_id = st.task_id
                    WHERE YEAR({self.PICKUP_DATE_SQL}) = :year
                      {month_filter_sql}
                      {transport_filter_sql}
                      {base_filter_sql}
                  {region_filter_sql}
                  {special_filter_sql}
                      AND sp.power IS NOT NULL
                    GROUP BY DATE_FORMAT({self.PICKUP_DATE_SQL}, '%Y-%m')
                    ORDER BY biz_month
                    """
                ),
                params,
            ).mappings().all()
            trip_rows = self.db.execute(
                text(
                    f"""
                    SELECT
                        DATE_FORMAT({self.PICKUP_DATE_SQL}, '%Y-%m') AS biz_month,
                        COUNT(*) AS shipment_trip_count
                    FROM dwd_logistics_assign_task at
                    JOIN dwd_logistics_ship_task st ON st.task_id = at.ship_task_id
                    LEFT JOIN ods_logistic_ship_task ost ON ost.task_id = st.task_id
                    WHERE YEAR({self.PICKUP_DATE_SQL}) = :year
                      {month_filter_sql}
                      {transport_filter_sql}
                      {base_filter_sql}
                  {region_filter_sql}
                  {special_filter_sql}
                      AND at.status IN ('ENTER', 'LEAVE')
                    GROUP BY DATE_FORMAT({self.PICKUP_DATE_SQL}, '%Y-%m')
                    ORDER BY biz_month
                    """
                ),
                params,
            ).mappings().all()
            mw_by_month = {str(row["biz_month"]): row.get("shipment_mw") for row in mw_rows}
            trip_by_month = {str(row["biz_month"]): int(row.get("shipment_trip_count") or 0) for row in trip_rows}
            month_sequence = months or sorted(
                {
                    int(month_text.split("-")[1])
                    for month_text in set(mw_by_month) | set(trip_by_month)
                    if "-" in month_text and month_text.split("-")[1].isdigit()
                }
            )
            for month in month_sequence:
                biz_month = f"{year}-{int(month):02d}"
                monthly_rows.append(
                    {
                        "biz_month": biz_month,
                        "shipment_mw": mw_by_month.get(biz_month) or 0,
                        "shipment_trip_count": trip_by_month.get(biz_month, 0),
                    }
                )
        result_payload = {
            "shipment_mw": shipment_mw,
            "shipment_trip_count": shipment_trip_count,
            "power_missing_count": int(power_missing_count or 0),
            "pickup_date_missing_count": int(pickup_date_missing_count or 0),
            "strict_scope_task_count": int(strict_scope_task_count or 0),
            "year_task_count": int(year_task_count or 0),
            "pickup_date_available_count": int(pickup_date_available_count or 0),
            "region_coverage": {
                "direct_area_count": int((region_coverage or {}).get("direct_area_count") or 0),
                "province_fallback_count": int((region_coverage or {}).get("province_fallback_count") or 0),
                "other_count": int((region_coverage or {}).get("other_count") or 0),
            },
            "year_region_coverage": {
                "direct_area_count": int((year_region_coverage or {}).get("direct_area_count") or 0),
                "province_fallback_count": int((year_region_coverage or {}).get("province_fallback_count") or 0),
                "other_count": int((year_region_coverage or {}).get("other_count") or 0),
            },
        }
        if monthly_breakdown:
            result_payload["monthly_rows"] = monthly_rows
        return result_payload

    def sys_total_fee_by_filters(
        self,
        *,
        year: int,
        months: list[int] | None = None,
        company_name: str | None = None,
        customer_name: str | None = None,
        transport_mode: str | None = None,
        region_name: str | None = None,
        special_scope: str | None = None,
        base_code: str | None = None,
        procurement_type: str | None = None,
        monthly_breakdown: bool = False,
    ) -> dict[str, Any]:
        """2026 系统按过滤条件统计总运费。

        口径说明：
            1. 延续当前特殊业务口径：总运费 = ship_product.price × project_name 解析总车数；
            2. 月份过滤优先使用 pickup_date，缺失时退回 biz_date，避免月度题直接查不出；
            3. 客户过滤当前只能基于 project_name 模糊命中，不额外承诺独立 customer 字段。
            4. 若题目限定基地，则统一按 dwd_logistics_ship_task.base_code 过滤。
            5. transport_mode 仅用于用户明确说“公路运输/铁路运输”等运输方式时过滤。
            6. procurement_type 仅用于用户明确说“招标/询比价”等系统侧采购方式时过滤。
            7. monthly_breakdown 只控制返回是否增加按月明细，不改变总费用计算口径。
        """
        filters = ["st.biz_year = :year"]
        params: dict[str, Any] = {"year": year}
        if months:
            month_placeholders = ", ".join(str(int(month)) for month in months)
            filters.append(
                f"MONTH(COALESCE(st.pickup_date, st.biz_date)) IN ({month_placeholders})"
            )
        if company_name:
            filters.append("st.company_name LIKE :company_name")
            params["company_name"] = f"%{company_name}%"
        if customer_name:
            filters.append("st.project_name LIKE :customer_name")
            params["customer_name"] = f"%{customer_name}%"
        if transport_mode:
            filters.append("st.transport_mode = :transport_mode")
            params["transport_mode"] = transport_mode
        if region_name:
            # 2026 系统侧按 normalized_region_name / delivery_area / delivery_province 统一成物流区域，
            # 让无时间条件默认 2023-2026 的区域费用口径与历史 region_name 对齐。
            filters.append(f"COALESCE(st.normalized_region_name, {self.REGION_CASE_SQL}) = :region_name")
            params["region_name"] = region_name
        if procurement_type:
            filters.append("st.procurement_type = :procurement_type")
            params["procurement_type"] = procurement_type
        if base_code:
            filters.append("st.base_code = :base_code")
            params["base_code"] = base_code
        if special_scope:
            special_filter_sql = {
                "planning": "st.expand_dept IN ('经营计划', '经营计划部')",
                "sample": "st.ship_type = '2'",
                "liujuan": "st.entrusted_person = '刘娟'",
            }[special_scope]
            filters.append(special_filter_sql)
        where_sql = " AND ".join(filters)
        row = self.db.execute(
            text(
                f"""
                WITH task_product AS (
                    SELECT
                        st.task_id,
                        st.project_name,
                        {self.PROJECT_TOTAL_TRUCKS_SQL} AS total_truck_count,
                        MAX(sp.price) AS car_price
                    FROM dwd_logistics_ship_task st
                    LEFT JOIN dwd_logistics_ship_product sp ON sp.task_id = st.task_id
                    WHERE {where_sql}
                    GROUP BY st.task_id, st.project_name
                )
                SELECT
                    ROUND(SUM(CASE WHEN total_truck_count IS NOT NULL AND car_price IS NOT NULL THEN car_price * total_truck_count ELSE 0 END), 2) AS total_fee,
                    COUNT(*) AS task_count,
                    SUM(CASE WHEN total_truck_count IS NULL THEN 1 ELSE 0 END) AS parse_fail_count,
                    SUM(CASE WHEN car_price IS NULL THEN 1 ELSE 0 END) AS price_missing_count
                FROM task_product
                """
            ),
            params,
        ).mappings().first()
        payload = dict(row or {})
        if monthly_breakdown:
            monthly_rows = self.db.execute(
                text(
                    f"""
                    WITH task_product AS (
                        SELECT
                            st.task_id,
                            st.project_name,
                            DATE_FORMAT(COALESCE(st.pickup_date, st.biz_date), '%Y-%m') AS biz_month,
                            {self.PROJECT_TOTAL_TRUCKS_SQL} AS total_truck_count,
                            MAX(sp.price) AS car_price
                        FROM dwd_logistics_ship_task st
                        LEFT JOIN dwd_logistics_ship_product sp ON sp.task_id = st.task_id
                        WHERE {where_sql}
                        GROUP BY st.task_id, st.project_name, DATE_FORMAT(COALESCE(st.pickup_date, st.biz_date), '%Y-%m')
                    )
                    SELECT
                        biz_month,
                        ROUND(SUM(CASE WHEN total_truck_count IS NOT NULL AND car_price IS NOT NULL THEN car_price * total_truck_count ELSE 0 END), 2) AS total_fee,
                        COUNT(*) AS task_count,
                        SUM(CASE WHEN total_truck_count IS NULL THEN 1 ELSE 0 END) AS parse_fail_count,
                        SUM(CASE WHEN car_price IS NULL THEN 1 ELSE 0 END) AS price_missing_count
                    FROM task_product
                    GROUP BY biz_month
                    ORDER BY biz_month
                    """
                ),
                params,
            ).mappings().all()
            rows_by_month = {str(row["biz_month"]): dict(row) for row in monthly_rows if row.get("biz_month")}
            # 用户明确给出月份列表时，即便某月无数据也返回 0 行，方便前端表格/图表稳定展示。
            month_sequence = months or sorted(
                {
                    int(month_text.split("-")[1])
                    for month_text in rows_by_month
                    if "-" in month_text and month_text.split("-")[1].isdigit()
                }
            )
            payload["monthly_rows"] = [
                rows_by_month.get(
                    f"{year}-{int(month):02d}",
                    {
                        "biz_month": f"{year}-{int(month):02d}",
                        "total_fee": 0,
                        "task_count": 0,
                        "parse_fail_count": 0,
                        "price_missing_count": 0,
                    },
                )
                for month in month_sequence
            ]
        return payload

    def sys_unit_fee_per_watt(
        self,
        *,
        year: int,
        months: list[int],
        company_name: str | None = None,
        include_extra_cost: bool = False,
    ) -> dict[str, Any]:
        """2026 系统按月份统计单瓦运输成本。

        参数：
            year: 统计年份。
            months: 月份列表。
            company_name: 可选承运商过滤。
            include_extra_cost: 是否把 assign_detail.extra_cost 一并纳入分子。

        返回：
            单瓦运输成本、总运费、总发运量和质量提示字段。

        说明：
            1. 分子继续复用当前系统总运费正式口径：price × 解析总车数；
            2. 分母使用 ship_product.power × quantity 汇总后的总瓦数；
            3. 当业务明确给出“(运费+额外费用)/总W数”公式时，再把 extra_cost 一并纳入分子；
            4. power 缺失、price 缺失和 project_name 解析失败都必须显式暴露。
        """
        month_placeholders = ", ".join(str(int(month)) for month in months)
        filters = ["st.biz_year = :year", f"MONTH(COALESCE(st.pickup_date, st.biz_date)) IN ({month_placeholders})"]
        params: dict[str, Any] = {"year": year}
        if company_name:
            filters.append("st.company_name LIKE :company_name")
            params["company_name"] = f"%{company_name}%"
        where_sql = " AND ".join(filters)
        row = self.db.execute(
            text(
                f"""
                WITH task_product AS (
                    SELECT
                        st.task_id,
                        st.project_name,
                        {self.PROJECT_TOTAL_TRUCKS_SQL} AS total_truck_count,
                        MAX(sp.price) AS car_price
                    FROM dwd_logistics_ship_task st
                    LEFT JOIN dwd_logistics_ship_product sp ON sp.task_id = st.task_id
                    WHERE {where_sql}
                    GROUP BY st.task_id, st.project_name
                ),
                fee_scope AS (
                    SELECT
                        ROUND(SUM(CASE WHEN total_truck_count IS NOT NULL AND car_price IS NOT NULL THEN car_price * total_truck_count ELSE 0 END), 2) AS total_fee,
                        COUNT(*) AS task_count,
                        SUM(CASE WHEN total_truck_count IS NULL THEN 1 ELSE 0 END) AS parse_fail_count,
                        SUM(CASE WHEN car_price IS NULL THEN 1 ELSE 0 END) AS price_missing_count
                    FROM task_product
                ),
                extra_scope AS (
                    SELECT
                        ROUND(SUM(COALESCE(ad.extra_cost, 0)), 2) AS extra_fee_amount
                    FROM dwd_logistics_assign_detail ad
                    JOIN dwd_logistics_ship_task st ON st.task_id = ad.ship_task_id
                    WHERE {where_sql}
                ),
                mw_scope AS (
                    SELECT
                        ROUND(SUM(CASE WHEN sp.power IS NOT NULL THEN sp.power * sp.quantity ELSE 0 END) / 1000000, 3) AS shipment_mw,
                        SUM(CASE WHEN sp.power IS NULL THEN 1 ELSE 0 END) AS power_missing_count,
                        SUM(CASE WHEN sp.power IS NOT NULL THEN sp.power * sp.quantity ELSE 0 END) AS shipment_watt
                    FROM dwd_logistics_ship_product sp
                    JOIN dwd_logistics_ship_task st ON st.task_id = sp.task_id
                    WHERE {where_sql}
                )
                SELECT
                    fee_scope.total_fee,
                    extra_scope.extra_fee_amount,
                    fee_scope.task_count,
                    fee_scope.parse_fail_count,
                    fee_scope.price_missing_count,
                    mw_scope.shipment_mw,
                    mw_scope.power_missing_count,
                    ROUND(
                        (
                            fee_scope.total_fee
                            + CASE WHEN :include_extra_cost = 1 THEN COALESCE(extra_scope.extra_fee_amount, 0) ELSE 0 END
                        ) / NULLIF(mw_scope.shipment_watt, 0),
                        8
                    ) AS unit_fee_per_watt
                FROM fee_scope
                CROSS JOIN extra_scope
                CROSS JOIN mw_scope
                """
            ),
            {**params, "include_extra_cost": 1 if include_extra_cost else 0},
        ).mappings().first()
        return dict(row or {})

    def sys_carrier_ranking(
        self,
        *,
        year: int,
        months: list[int],
        ranking_metric: str,
        top_n: int = 10,
    ) -> list[dict[str, Any]]:
        """2026 系统承运商运费/单瓦成本排名。"""
        month_placeholders = ", ".join(str(int(month)) for month in months)
        common_filters = f"""
            st.biz_year = :year
            AND MONTH(COALESCE(st.pickup_date, st.biz_date)) IN ({month_placeholders})
            AND st.company_name IS NOT NULL
            AND TRIM(st.company_name) <> ''
        """
        params = {"year": year, "limit_value": top_n}
        if ranking_metric == "total_fee":
            rows = self.db.execute(
                text(
                    f"""
                    WITH task_product AS (
                        SELECT
                            st.task_id,
                            st.company_name,
                            {self.PROJECT_TOTAL_TRUCKS_SQL} AS total_truck_count,
                            MAX(sp.price) AS car_price
                        FROM dwd_logistics_ship_task st
                        LEFT JOIN dwd_logistics_ship_product sp ON sp.task_id = st.task_id
                        WHERE {common_filters}
                        GROUP BY st.task_id, st.company_name, st.project_name
                    )
                    SELECT
                        company_name AS carrier_name,
                        ROUND(SUM(CASE WHEN total_truck_count IS NOT NULL AND car_price IS NOT NULL THEN car_price * total_truck_count ELSE 0 END), 2) AS total_fee,
                        COUNT(*) AS task_count
                    FROM task_product
                    GROUP BY company_name
                    ORDER BY total_fee DESC, task_count DESC, carrier_name ASC
                    LIMIT :limit_value
                    """
                ),
                params,
            ).mappings().all()
            return [dict(row) for row in rows]

        rows = self.db.execute(
            text(
                f"""
                WITH task_fee AS (
                    SELECT
                        st.task_id,
                        st.company_name,
                        CASE
                            WHEN {self.PROJECT_TOTAL_TRUCKS_SQL} IS NOT NULL AND MAX(sp.price) IS NOT NULL
                                THEN MAX(sp.price) * {self.PROJECT_TOTAL_TRUCKS_SQL}
                            ELSE 0
                        END AS task_total_fee
                    FROM dwd_logistics_ship_task st
                    LEFT JOIN dwd_logistics_ship_product sp ON sp.task_id = st.task_id
                    WHERE {common_filters}
                    GROUP BY st.task_id, st.company_name, st.project_name
                ),
                fee_scope AS (
                    SELECT
                        company_name,
                        ROUND(SUM(task_total_fee), 2) AS total_fee,
                        COUNT(*) AS task_count
                    FROM task_fee
                    GROUP BY company_name
                ),
                mw_scope AS (
                    SELECT
                        st.company_name,
                        ROUND(SUM(CASE WHEN sp.power IS NOT NULL THEN sp.power * sp.quantity ELSE 0 END) / 1000000, 3) AS shipment_mw,
                        SUM(CASE WHEN sp.power IS NOT NULL THEN sp.power * sp.quantity ELSE 0 END) AS shipment_watt
                    FROM dwd_logistics_ship_product sp
                    JOIN dwd_logistics_ship_task st ON st.task_id = sp.task_id
                    WHERE {common_filters}
                    GROUP BY st.company_name
                )
                SELECT
                    fee_scope.company_name AS carrier_name,
                    ROUND(fee_scope.total_fee / NULLIF(mw_scope.shipment_watt, 0), 8) AS unit_fee_per_watt,
                    fee_scope.total_fee,
                    fee_scope.task_count,
                    mw_scope.shipment_mw
                FROM fee_scope
                JOIN mw_scope ON mw_scope.company_name = fee_scope.company_name
                ORDER BY unit_fee_per_watt DESC, total_fee DESC, carrier_name ASC
                LIMIT :limit_value
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def sys_mw_by_procurement_type(self, *, year: int) -> list[dict[str, Any]]:
        """2026 按采购方式拆分发运量 MW。"""
        rows = self.db.execute(
            text(
                """
                SELECT
                    COALESCE(NULLIF(TRIM(procurement_type), ''), '未填充') AS procurement_type,
                    ROUND(SUM(CASE WHEN power IS NOT NULL THEN power * quantity ELSE 0 END) / 1000000, 3) AS shipment_mw,
                    COUNT(DISTINCT st.task_id) AS task_count
                FROM dwd_logistics_ship_product sp
                JOIN dwd_logistics_ship_task st ON st.task_id = sp.task_id
                WHERE st.biz_year = :year
                GROUP BY procurement_type
                ORDER BY shipment_mw DESC, procurement_type ASC
                """
            ),
            {"year": year},
        ).mappings().all()
        return [dict(row) for row in rows]

    def sys_task_status_distribution(self, *, year: int, table_scope: str = "ship_task") -> dict[str, Any]:
        """2026 系统任务状态分布。

        参数：
            year: 统计年份。
            table_scope: ship_task 表示主任务表，assign_task 表示派车任务表。

        返回：
            状态数量、占比和总任务数。
        """

        if table_scope == "assign_task":
            rows = self.db.execute(
                text(
                    """
                    SELECT status, COUNT(*) AS task_count
                    FROM dwd_logistics_assign_task
                    WHERE YEAR(created_at) = :year
                      AND status IS NOT NULL
                      AND TRIM(status) <> ''
                    GROUP BY status
                    ORDER BY task_count DESC, status ASC
                    """
                ),
                {"year": year},
            ).mappings().all()
        else:
            rows = self.db.execute(
                text(
                    """
                    SELECT status, COUNT(*) AS task_count
                    FROM dwd_logistics_ship_task
                    WHERE biz_year = :year
                      AND status IS NOT NULL
                      AND TRIM(status) <> ''
                    GROUP BY status
                    ORDER BY task_count DESC, status ASC
                    """
                ),
                {"year": year},
            ).mappings().all()
        items = [dict(row) for row in rows]
        total = sum(int(item.get("task_count") or 0) for item in items)
        for item in items:
            item["task_share_pct"] = round(int(item.get("task_count") or 0) / total * 100, 2) if total else None
        return {"table_scope": table_scope, "total_task_count": total, "items": items}

    def sys_avg_loading_trucks_by_province(self, *, year: int, province: str) -> dict[str, Any]:
        """2026 指定送达省份平均装车数。"""

        normalized_province = province if province.endswith(("省", "市", "自治区")) else f"{province}省"
        row = self.db.execute(
            text(
                """
                SELECT
                    ROUND(AVG(loading_trucks), 3) AS avg_loading_trucks,
                    COUNT(*) AS task_count,
                    SUM(CASE WHEN loading_trucks IS NOT NULL THEN 1 ELSE 0 END) AS non_null_task_count
                FROM dwd_logistics_ship_task
                WHERE biz_year = :year
                  AND delivery_province = :province
                """
            ),
            {"year": year, "province": normalized_province},
        ).mappings().first()
        payload = dict(row or {})
        payload["province"] = normalized_province
        return payload

    def sys_task_status_province_ranking(self, *, year: int, status: str, top_n: int = 10) -> list[dict[str, Any]]:
        """2026 指定状态按送达省份排名。"""

        rows = self.db.execute(
            text(
                """
                SELECT delivery_province, COUNT(*) AS task_count
                FROM dwd_logistics_ship_task
                WHERE biz_year = :year
                  AND status = :status
                  AND delivery_province IS NOT NULL
                  AND TRIM(delivery_province) <> ''
                GROUP BY delivery_province
                ORDER BY task_count DESC, delivery_province ASC
                LIMIT :limit_value
                """
            ),
            {"year": year, "status": status, "limit_value": top_n},
        ).mappings().all()
        return [dict(row) for row in rows]

    def sys_reconciliation_fill_rate_by_month(self, *, year: int) -> list[dict[str, Any]]:
        """2026 reconciliation_status 按月填充率。"""

        rows = self.db.execute(
            text(
                """
                SELECT
                    biz_month,
                    ROUND(100 * AVG(CASE WHEN reconciliation_status IS NOT NULL AND TRIM(reconciliation_status) <> '' THEN 1 ELSE 0 END), 2) AS fill_rate,
                    COUNT(*) AS task_count
                FROM dwd_logistics_ship_task
                WHERE biz_year = :year
                  AND biz_month IS NOT NULL
                GROUP BY biz_month
                ORDER BY biz_month ASC
                """
            ),
            {"year": year},
        ).mappings().all()
        return [dict(row) for row in rows]

    def sys_ship_product_detail_stats(self, *, year: int, top_n: int = 10) -> dict[str, Any]:
        """2026 每个物流任务包含 ship_product 明细数统计。"""

        avg_row = self.db.execute(
            text(
                """
                SELECT ROUND(AVG(detail_count), 3) AS avg_detail_count
                FROM (
                    SELECT st.task_id, COUNT(sp.id) AS detail_count
                    FROM dwd_logistics_ship_task st
                    LEFT JOIN dwd_logistics_ship_product sp ON sp.task_id = st.task_id
                    WHERE st.biz_year = :year
                    GROUP BY st.task_id
                ) t
                """
            ),
            {"year": year},
        ).mappings().first()
        top_rows = self.db.execute(
            text(
                """
                SELECT st.task_id, st.project_name, COUNT(sp.id) AS detail_count
                FROM dwd_logistics_ship_task st
                LEFT JOIN dwd_logistics_ship_product sp ON sp.task_id = st.task_id
                WHERE st.biz_year = :year
                GROUP BY st.task_id, st.project_name
                ORDER BY detail_count DESC, st.task_id ASC
                LIMIT :limit_value
                """
            ),
            {"year": year, "limit_value": top_n},
        ).mappings().all()
        return {"avg_detail_count": (avg_row or {}).get("avg_detail_count"), "items": [dict(row) for row in top_rows]}

    def sys_driver_task_ranking(self, *, year: int, top_n: int = 20) -> list[dict[str, Any]]:
        """2026 派车任务按司机排名。"""

        rows = self.db.execute(
            text(
                """
                SELECT driver_name, COUNT(*) AS assign_task_count
                FROM dwd_logistics_assign_task
                WHERE YEAR(created_at) = :year
                  AND driver_name IS NOT NULL
                  AND TRIM(driver_name) <> ''
                GROUP BY driver_name
                ORDER BY assign_task_count DESC, driver_name ASC
                LIMIT :limit_value
                """
            ),
            {"year": year, "limit_value": top_n},
        ).mappings().all()
        return [dict(row) for row in rows]

    def sys_driver_phone_name_consistency(self, *, year: int, top_n: int = 50) -> dict[str, Any]:
        """检查同一手机号关联多个司机姓名的派车数据。

        参数：
            year: 系统侧年份，当前用于 2026 正式系统数据。
            top_n: 返回异常手机号明细上限。
        返回值：
            包含异常组数量、异常任务数和明细行的字典。
        业务逻辑：
            按 driver_phone 分组，统计 distinct driver_name；姓名数大于 1 视为一号多人。
            空手机号或空司机姓名不参与一致性判断，避免把缺失值误判为异常。
        """

        summary_row = self.db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS abnormal_group_count,
                    COALESCE(SUM(assign_task_count), 0) AS abnormal_task_count
                FROM (
                    SELECT
                        TRIM(driver_phone) AS normalized_driver_phone,
                        COUNT(DISTINCT TRIM(driver_name)) AS driver_name_count,
                        COUNT(*) AS assign_task_count
                    FROM dwd_logistics_assign_task
                    WHERE YEAR(created_at) = :year
                      AND driver_phone IS NOT NULL
                      AND TRIM(driver_phone) <> ''
                      AND driver_name IS NOT NULL
                      AND TRIM(driver_name) <> ''
                    GROUP BY TRIM(driver_phone)
                    HAVING COUNT(DISTINCT TRIM(driver_name)) > 1
                ) abnormal_groups
                """
            ),
            {"year": year},
        ).mappings().first()
        rows = self.db.execute(
            text(
                """
                SELECT
                    TRIM(driver_phone) AS driver_phone,
                    GROUP_CONCAT(DISTINCT TRIM(driver_name) ORDER BY TRIM(driver_name) SEPARATOR '、') AS driver_names,
                    COUNT(DISTINCT TRIM(driver_name)) AS driver_name_count,
                    COUNT(*) AS assign_task_count,
                    COUNT(DISTINCT task_id) AS distinct_task_count
                FROM dwd_logistics_assign_task
                WHERE YEAR(created_at) = :year
                  AND driver_phone IS NOT NULL
                  AND TRIM(driver_phone) <> ''
                  AND driver_name IS NOT NULL
                  AND TRIM(driver_name) <> ''
                GROUP BY TRIM(driver_phone)
                HAVING COUNT(DISTINCT TRIM(driver_name)) > 1
                ORDER BY assign_task_count DESC, driver_phone ASC
                LIMIT :limit_value
                """
            ),
            {"year": year, "limit_value": top_n},
        ).mappings().all()
        items = [dict(row) for row in rows]
        return {
            "abnormal_group_count": int((summary_row or {}).get("abnormal_group_count") or 0),
            "abnormal_task_count": int((summary_row or {}).get("abnormal_task_count") or 0),
            "items": items,
        }

    def sys_driver_id_phone_consistency(self, *, year: int, top_n: int = 50) -> dict[str, Any]:
        """检查同一身份证号关联多个手机号的派车数据。

        参数：
            year: 系统侧年份，当前用于 2026 正式系统数据。
            top_n: 返回异常身份证号明细上限。
        返回值：
            包含异常组数量、异常任务数和明细行的字典。
        业务逻辑：
            按 driver_id_number 分组，统计 distinct driver_phone；手机号数大于 1 视为一人多号。
            空身份证号或空手机号不参与一致性判断，避免缺失值污染异常结果。
        """

        summary_row = self.db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS abnormal_group_count,
                    COALESCE(SUM(assign_task_count), 0) AS abnormal_task_count
                FROM (
                    SELECT
                        TRIM(driver_id_number) AS normalized_driver_id_number,
                        COUNT(DISTINCT TRIM(driver_phone)) AS driver_phone_count,
                        COUNT(*) AS assign_task_count
                    FROM dwd_logistics_assign_task
                    WHERE YEAR(created_at) = :year
                      AND driver_id_number IS NOT NULL
                      AND TRIM(driver_id_number) <> ''
                      AND driver_phone IS NOT NULL
                      AND TRIM(driver_phone) <> ''
                    GROUP BY TRIM(driver_id_number)
                    HAVING COUNT(DISTINCT TRIM(driver_phone)) > 1
                ) abnormal_groups
                """
            ),
            {"year": year},
        ).mappings().first()
        rows = self.db.execute(
            text(
                """
                SELECT
                    TRIM(driver_id_number) AS driver_id_number,
                    GROUP_CONCAT(DISTINCT TRIM(driver_phone) ORDER BY TRIM(driver_phone) SEPARATOR '、') AS driver_phones,
                    COUNT(DISTINCT TRIM(driver_phone)) AS driver_phone_count,
                    COUNT(*) AS assign_task_count,
                    COUNT(DISTINCT task_id) AS distinct_task_count
                FROM dwd_logistics_assign_task
                WHERE YEAR(created_at) = :year
                  AND driver_id_number IS NOT NULL
                  AND TRIM(driver_id_number) <> ''
                  AND driver_phone IS NOT NULL
                  AND TRIM(driver_phone) <> ''
                GROUP BY TRIM(driver_id_number)
                HAVING COUNT(DISTINCT TRIM(driver_phone)) > 1
                ORDER BY assign_task_count DESC, driver_id_number ASC
                LIMIT :limit_value
                """
            ),
            {"year": year, "limit_value": top_n},
        ).mappings().all()
        items = [dict(row) for row in rows]
        return {
            "abnormal_group_count": int((summary_row or {}).get("abnormal_group_count") or 0),
            "abnormal_task_count": int((summary_row or {}).get("abnormal_task_count") or 0),
            "items": items,
        }

    def sys_delivery_note_parse_status_distribution(self, *, year: int) -> dict[str, Any]:
        """2026 派车任务回单解析状态分布。"""

        rows = self.db.execute(
            text(
                """
                SELECT delivery_note_parse_status, COUNT(*) AS record_count
                FROM dwd_logistics_assign_task
                WHERE YEAR(created_at) = :year
                  AND delivery_note_parse_status IS NOT NULL
                GROUP BY delivery_note_parse_status
                ORDER BY delivery_note_parse_status ASC
                """
            ),
            {"year": year},
        ).mappings().all()
        items = [dict(row) for row in rows]
        total = sum(int(item.get("record_count") or 0) for item in items)
        for item in items:
            item["record_share_pct"] = round(int(item.get("record_count") or 0) / total * 100, 2) if total else None
        return {"total_record_count": total, "items": items}

    def sys_procurement_task_distribution(self, *, year: int) -> dict[str, Any]:
        """2026 采购方式任务量和占比。"""

        rows = self.db.execute(
            text(
                """
                SELECT procurement_type, COUNT(*) AS task_count
                FROM dwd_logistics_ship_task
                WHERE biz_year = :year
                  AND procurement_type IS NOT NULL
                  AND TRIM(procurement_type) <> ''
                GROUP BY procurement_type
                ORDER BY task_count DESC, procurement_type ASC
                """
            ),
            {"year": year},
        ).mappings().all()
        items = [dict(row) for row in rows]
        total = sum(int(item.get("task_count") or 0) for item in items)
        for item in items:
            item["task_share_pct"] = round(int(item.get("task_count") or 0) / total * 100, 2) if total else None
        return {"total_task_count": total, "items": items}

    def sys_procurement_avg_loading_trucks(self, *, year: int) -> list[dict[str, Any]]:
        """2026 按采购方式统计平均装车数。"""

        rows = self.db.execute(
            text(
                """
                SELECT
                    procurement_type,
                    ROUND(AVG(loading_trucks), 3) AS avg_loading_trucks,
                    COUNT(*) AS task_count,
                    SUM(CASE WHEN loading_trucks IS NOT NULL THEN 1 ELSE 0 END) AS non_null_task_count
                FROM dwd_logistics_ship_task
                WHERE biz_year = :year
                  AND procurement_type IS NOT NULL
                  AND TRIM(procurement_type) <> ''
                GROUP BY procurement_type
                ORDER BY avg_loading_trucks DESC, procurement_type ASC
                """
            ),
            {"year": year},
        ).mappings().all()
        return [dict(row) for row in rows]

    def sys_extra_fee_summary(
        self,
        *,
        year: int,
        months: list[int] | None = None,
        base_code: str | None = None,
    ) -> dict[str, Any]:
        """2026 额外费用总额。

        说明：
            当前额外费用按 assign_detail.extra_cost 汇总，月份和基地按主任务过滤。
        """

        filters = ["st.biz_year = :year"]
        params: dict[str, Any] = {"year": year}
        if months:
            month_sql = ", ".join(str(int(month)) for month in months)
            filters.append(f"MONTH(COALESCE(st.pickup_date, st.biz_date)) IN ({month_sql})")
        if base_code:
            filters.append("st.base_code = :base_code")
            params["base_code"] = base_code
        where_sql = " AND ".join(filters)
        row = self.db.execute(
            text(
                f"""
                SELECT
                    ROUND(SUM(COALESCE(ad.extra_cost, 0)), 2) AS extra_fee_amount,
                    COUNT(DISTINCT st.task_id) AS task_count,
                    COUNT(ad.id) AS detail_count
                FROM dwd_logistics_ship_task st
                LEFT JOIN dwd_logistics_assign_detail ad ON ad.ship_task_id = st.task_id
                WHERE {where_sql}
                """
            ),
            params,
        ).mappings().first()
        return dict(row or {})

    def sys_task_count_ranking(self, *, year: int, dimension: str, top_n: int = 10) -> list[dict[str, Any]]:
        """2026 按项目或送达城市统计任务量排名。"""
        if dimension not in {"delivery_city", "project_name"}:
            raise ValueError(f"不支持的任务量排名维度：{dimension}")
        rows = self.db.execute(
            text(
                f"""
                SELECT
                    {dimension} AS dimension_value,
                    COUNT(*) AS task_count
                FROM dwd_logistics_ship_task
                WHERE biz_year = :year
                  AND {dimension} IS NOT NULL
                  AND TRIM({dimension}) <> ''
                GROUP BY {dimension}
                ORDER BY task_count DESC, dimension_value ASC
                LIMIT :limit_value
                """
            ),
            {"year": year, "limit_value": top_n},
        ).mappings().all()
        return [dict(row) for row in rows]

    def sys_delivery_distance_fill_rate_by_province(self, *, year: int, top_n: int = 10) -> list[dict[str, Any]]:
        """2026 按送达省份统计 delivery_distance 填充率。"""
        rows = self.db.execute(
            text(
                """
                SELECT
                    delivery_province,
                    ROUND(100 * AVG(CASE WHEN delivery_distance IS NOT NULL THEN 1 ELSE 0 END), 1) AS fill_rate,
                    COUNT(*) AS task_count
                FROM dwd_logistics_ship_task
                WHERE biz_year = :year
                  AND delivery_province IS NOT NULL
                  AND TRIM(delivery_province) <> ''
                  AND delivery_province <> '-'
                GROUP BY delivery_province
                ORDER BY fill_rate ASC, task_count DESC, delivery_province ASC
                LIMIT :limit_value
                """
            ),
            {"year": year, "limit_value": top_n},
        ).mappings().all()
        return [dict(row) for row in rows]

    def sys_parse_success_rate_by_carrier(self, *, year: int, top_n: int = 10) -> dict[str, Any]:
        """2026 按承运商统计送货单解析成功率前后十。"""
        top_rows = self.db.execute(
            text(
                f"""
                SELECT
                    company_name,
                    ROUND(100 * AVG(CASE WHEN {self.PROJECT_TOTAL_TRUCKS_SQL} IS NOT NULL THEN 1 ELSE 0 END), 1) AS parse_success_rate,
                    COUNT(*) AS task_count
                FROM dwd_logistics_ship_task st
                WHERE st.biz_year = :year
                  AND st.company_name IS NOT NULL
                  AND TRIM(st.company_name) <> ''
                GROUP BY company_name
                ORDER BY parse_success_rate DESC, task_count DESC, company_name ASC
                LIMIT :limit_value
                """
            ),
            {"year": year, "limit_value": top_n},
        ).mappings().all()
        bottom_rows = self.db.execute(
            text(
                f"""
                SELECT
                    company_name,
                    ROUND(100 * AVG(CASE WHEN {self.PROJECT_TOTAL_TRUCKS_SQL} IS NOT NULL THEN 1 ELSE 0 END), 1) AS parse_success_rate,
                    COUNT(*) AS task_count
                FROM dwd_logistics_ship_task st
                WHERE st.biz_year = :year
                  AND st.company_name IS NOT NULL
                  AND TRIM(st.company_name) <> ''
                GROUP BY company_name
                ORDER BY parse_success_rate ASC, task_count DESC, company_name ASC
                LIMIT :limit_value
                """
            ),
            {"year": year, "limit_value": top_n},
        ).mappings().all()
        return {"top10": [dict(row) for row in top_rows], "bottom10": [dict(row) for row in bottom_rows]}

    def sys_company_mapping_gap(self, *, year: int, limit: int = 20) -> dict[str, Any]:
        """2026 company_id 无法映射承运商主数据的任务清单。"""
        rows = self.db.execute(
            text(
                """
                SELECT
                    st.task_id,
                    st.company_id,
                    st.company_name
                FROM dwd_logistics_ship_task st
                LEFT JOIN dwd_logistics_company c ON c.source_id = st.company_id
                WHERE st.biz_year = :year
                  AND st.company_id IS NOT NULL
                  AND c.source_id IS NULL
                ORDER BY st.task_id ASC
                LIMIT :limit_value
                """
            ),
            {"year": year, "limit_value": limit},
        ).mappings().all()
        total_count = self.db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM dwd_logistics_ship_task st
                LEFT JOIN dwd_logistics_company c ON c.source_id = st.company_id
                WHERE st.biz_year = :year
                  AND st.company_id IS NOT NULL
                  AND c.source_id IS NULL
                """
            ),
            {"year": year},
        ).scalar()
        return {"missing_task_count": int(total_count or 0), "items": [dict(row) for row in rows]}

    def sys_extra_cost_audited_concentration(self, *, year: int, top_n: int = 10) -> dict[str, Any]:
        """2026 extra_cost_audited=1 任务集中度。"""
        total_count = self.db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM dwd_logistics_ship_task
                WHERE biz_year = :year
                  AND extra_cost_audited = 1
                """
            ),
            {"year": year},
        ).scalar()
        carrier_rows = self.db.execute(
            text(
                """
                SELECT
                    company_name,
                    COUNT(*) AS task_count
                FROM dwd_logistics_ship_task
                WHERE biz_year = :year
                  AND extra_cost_audited = 1
                  AND company_name IS NOT NULL
                  AND TRIM(company_name) <> ''
                GROUP BY company_name
                ORDER BY task_count DESC, company_name ASC
                LIMIT :limit_value
                """
            ),
            {"year": year, "limit_value": top_n},
        ).mappings().all()
        province_rows = self.db.execute(
            text(
                """
                SELECT
                    delivery_province,
                    COUNT(*) AS task_count
                FROM dwd_logistics_ship_task
                WHERE biz_year = :year
                  AND extra_cost_audited = 1
                  AND delivery_province IS NOT NULL
                  AND TRIM(delivery_province) <> ''
                GROUP BY delivery_province
                ORDER BY task_count DESC, delivery_province ASC
                LIMIT :limit_value
                """
            ),
            {"year": year, "limit_value": top_n},
        ).mappings().all()
        return {
            "audited_task_count": int(total_count or 0),
            "top_carriers": [dict(row) for row in carrier_rows],
            "top_provinces": [dict(row) for row in province_rows],
        }

    def sys_signedfor_rate_by_carrier(self, *, year: int) -> dict[str, Any]:
        """2026 承运商签收率排行。"""
        top_rows = self.db.execute(
            text(
                """
                SELECT
                    company_name,
                    ROUND(100 * AVG(CASE WHEN status = 'SIGNEDFOR' THEN 1 ELSE 0 END), 1) AS signedfor_rate,
                    COUNT(*) AS task_count
                FROM dwd_logistics_ship_task
                WHERE biz_year = :year
                  AND company_name IS NOT NULL
                GROUP BY company_name
                ORDER BY signedfor_rate DESC, task_count DESC, company_name ASC
                LIMIT 10
                """
            ),
            {"year": year},
        ).mappings().all()
        bottom_rows = self.db.execute(
            text(
                """
                SELECT
                    company_name,
                    ROUND(100 * AVG(CASE WHEN status = 'SIGNEDFOR' THEN 1 ELSE 0 END), 1) AS signedfor_rate,
                    COUNT(*) AS task_count
                FROM dwd_logistics_ship_task
                WHERE biz_year = :year
                  AND company_name IS NOT NULL
                GROUP BY company_name
                ORDER BY signedfor_rate ASC, task_count DESC, company_name ASC
                LIMIT 10
                """
            ),
            {"year": year},
        ).mappings().all()
        return {"top10": [dict(row) for row in top_rows], "bottom10": [dict(row) for row in bottom_rows]}

    def sys_companies_without_tasks(self, *, year: int) -> dict[str, Any]:
        """已建档但无 2026 任务的物流公司。"""
        rows = self.db.execute(
            text(
                """
                SELECT c.company_name
                FROM dwd_logistics_company c
                LEFT JOIN dwd_logistics_ship_task st
                  ON st.company_id = c.source_id
                 AND st.biz_year = :year
                WHERE st.id IS NULL
                ORDER BY c.company_name
                """
            ),
            {"year": year},
        ).mappings().all()
        return {"company_count": len(rows), "items": [dict(row) for row in rows]}

    def sys_special_total_fee(
        self,
        *,
        year: int,
        special_scope: str,
    ) -> dict[str, Any]:
        """按特殊业务口径统计 2026 总运费。

        口径说明：
            1. 总运费 = ship_product.price × project_name 解析出的总车数；
            2. 解析失败、价格缺失都要计数；
            3. 这里只做总额统计，不展开预测和异常分析。
        """
        filter_sql = {
            "planning": "st.expand_dept IN ('经营计划', '经营计划部')",
            "sample": "st.ship_type = '2'",
            "liujuan": "st.entrusted_person = '刘娟'",
        }[special_scope]
        row = self.db.execute(
            text(
                f"""
                WITH task_product AS (
                    SELECT
                        st.task_id,
                        st.project_name,
                        {self.PROJECT_TOTAL_TRUCKS_SQL} AS total_truck_count,
                        MAX(sp.price) AS car_price
                    FROM dwd_logistics_ship_task st
                    LEFT JOIN dwd_logistics_ship_product sp ON sp.task_id = st.task_id
                    WHERE st.biz_year = :year
                      AND {filter_sql}
                    GROUP BY st.task_id, st.project_name
                )
                SELECT
                    ROUND(SUM(CASE WHEN total_truck_count IS NOT NULL AND car_price IS NOT NULL THEN car_price * total_truck_count ELSE 0 END), 2) AS total_fee,
                    SUM(CASE WHEN total_truck_count IS NULL THEN 1 ELSE 0 END) AS parse_fail_count,
                    SUM(CASE WHEN car_price IS NULL THEN 1 ELSE 0 END) AS price_missing_count
                FROM task_product
                """
            ),
            {"year": year},
        ).mappings().first()
        return dict(row or {})

    def _list_columns(self, table_name: str) -> list[str]:
        """读取指定表的字段清单。

        说明：
            1. 只用于数据资产核验报告；
            2. 不参与业务查询执行；
            3. 失败时返回空列表，避免影响主链路。
        """
        rows = self.db.execute(
            text(
                """
                SELECT COLUMN_NAME
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = :table_name
                ORDER BY ORDINAL_POSITION
                """
            ),
            {"table_name": table_name},
        ).scalars().all()
        return [str(row) for row in rows]
