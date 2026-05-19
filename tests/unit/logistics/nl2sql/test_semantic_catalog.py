from __future__ import annotations

from datetime import date

import pytest

from backend.app.domains.logistics.services.nl2sql.business_rules import LogisticsNl2SqlBusinessRules
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.tables_builder import build_static_logistics_tables_catalog
from backend.app.domains.logistics.services.query_planner_v2.legacy_adapter import LogisticsQueryPlannerV2LegacyAdapter
from backend.app.domains.logistics.services.query_planner_v2.normalizer import LogisticsQueryPlannerV2Normalizer
from backend.app.domains.logistics.services.query_planner_v2.validator import LogisticsQueryPlannerV2Validator
from backend.app.domains.logistics.services.query_planner_v2.capability_registry import LogisticsQueryPlannerV2CapabilityRegistry


def test_semantic_catalog_loads_mvp_metrics_and_quote_mouth() -> None:
    """Semantic Catalog 必须固化物流一期核心指标和报价/均价边界。"""

    catalog = LogisticsSemanticCatalogLoader().load()

    assert catalog.catalog_version == "logistics_nl2sql_catalog.v1"
    assert catalog.domain == "logistics"

    shipment_mw = catalog.get_metric("shipment_mw")
    assert shipment_mw.sql_expression == "SUM(shipment_watt)"
    assert shipment_mw.unit == "MW"
    assert catalog.resolve_metric_alias("件数").metric_id == "shipment_mw"
    assert catalog.resolve_metric_alias("发货量").metric_id == "shipment_mw"

    avg_fee = catalog.get_metric("avg_fee_per_trip")
    assert "SUM(total_fee)" in avg_fee.sql_expression
    assert "SUM(shipment_trip_count)" in avg_fee.sql_expression
    assert "AVG(total_fee)" not in avg_fee.sql_expression

    for alias in ("报价", "单价", "运价"):
        quote_metric = catalog.resolve_metric_alias(alias)
        assert quote_metric.metric_id == "unit_price_per_vehicle"
        assert quote_metric.sql_expression == "unit_price_per_vehicle"
        assert "SUM(total_fee)" not in quote_metric.sql_expression

    carrier_rank = catalog.get_metric("carrier_rank_by_mw")
    assert carrier_rank.sort_expression == "SUM(shipment_watt) DESC"


def test_semantic_catalog_loads_rules_for_time_source_empty_and_unsupported_units() -> None:
    """规则目录必须覆盖默认时间、今年口径、跨源混查、空结果和吨数拒答。"""

    catalog = LogisticsSemanticCatalogLoader().load()
    rules = LogisticsNl2SqlBusinessRules(catalog)

    assert catalog.resolve_rule_alias("吨数").rule_id == "unsupported_tonnage"
    assert catalog.resolve_rule_alias("运输吨位").action == "reject"
    assert rules.is_unsupported_question("2025年各承运商运输吨位是多少") is True

    assert rules.resolve_years("各承运商发运量", today=date(2026, 5, 15)) == [2023, 2024, 2025, 2026]
    assert rules.resolve_years("今年各承运商发运量", today=date(2026, 5, 15)) == [2026]
    assert rules.resolve_years("当前各承运商发运量", today=date(2026, 5, 15)) == [2026]
    assert rules.resolve_years("最近各承运商发运量", today=date(2026, 5, 15)) == [2026]

    assert rules.cross_source_years_allowed([2023, 2026]) is True
    empty_policy = rules.empty_result_policy()
    assert empty_policy["relax_filters"] is False
    assert "改问建议" in empty_policy["business_message"]


def test_semantic_catalog_tables_are_limited_to_middle_db_logistics_whitelist() -> None:
    """表目录只能暴露智能助手中间库物流白名单表，不能混入 SAP MID 表。"""

    catalog = LogisticsSemanticCatalogLoader().load()
    table_names = catalog.allowed_table_names()

    assert {
        "dws_logistics_detail_union",
        "dws_logistics_monthly_metric",
        "dwd_logistics_hist_shipment_detail",
        "dwd_logistics_ship_task",
        "dwd_logistics_ship_product",
        "dwd_logistics_assign_task",
        "dwd_logistics_assign_detail",
        "dm_logistics_company_month_rank",
    } <= table_names
    assert "V_SAP_HFFN_EKKO" not in table_names
    assert "ods_logistic_ship_task" not in table_names
    assert "sys_query_log" not in table_names

    for join in catalog.joins:
        assert join.left_table in table_names
        assert join.right_table in table_names

    for table in catalog.allowed_tables():
        assert table.source_system == "middle_db"
        assert table.allowed_read is True
        assert table.domain == "logistics"
        assert table.columns


def test_semantic_catalog_loader_rejects_non_whitelisted_tables(tmp_path) -> None:
    """Catalog 加载器必须 fail-closed，拒绝 SAP、ODS 和日志审计等非业务表。"""

    (tmp_path / "tables.yaml").write_text(
        """
catalog_version: logistics_nl2sql_catalog.v1
domain: logistics
tables:
  - table_name: V_SAP_HFFN_EKKO
    display_name: SAP 采购订单视图
    domain: logistics
    source_system: middle_db
    allowed_read: true
    columns:
      - {name: EBELN, data_type: varchar, nullable: false}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="catalog_table_not_allowed::V_SAP_HFFN_EKKO"):
        LogisticsSemanticCatalogLoader(tmp_path).load()


def test_semantic_catalog_loader_rejects_non_middle_db_source(tmp_path) -> None:
    """即使表名在白名单内，也不能把非中间库来源放进可读 catalog。"""

    (tmp_path / "tables.yaml").write_text(
        """
catalog_version: logistics_nl2sql_catalog.v1
domain: logistics
tables:
  - table_name: dws_logistics_detail_union
    display_name: 物流明细统一服务表
    domain: logistics
    source_system: sap_mid
    allowed_read: true
    columns:
      - {name: shipment_watt, data_type: decimal, nullable: true}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="catalog_table_source_system_invalid::dws_logistics_detail_union::sap_mid"):
        LogisticsSemanticCatalogLoader(tmp_path).load()


def test_semantic_catalog_loader_rejects_non_whitelisted_tables_even_when_not_readable(tmp_path) -> None:
    """不可读表也不能混进 catalog，避免后续组件误用 SAP/ODS/日志表。"""

    (tmp_path / "tables.yaml").write_text(
        """
catalog_version: logistics_nl2sql_catalog.v1
domain: logistics
tables:
  - table_name: sys_query_log
    display_name: 查询日志表
    domain: logistics
    source_system: middle_db
    allowed_read: false
    columns:
      - {name: query_text, data_type: text, nullable: true}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="catalog_table_not_allowed::sys_query_log"):
        LogisticsSemanticCatalogLoader(tmp_path).load()


def test_semantic_catalog_loader_rejects_non_middle_db_source_even_when_not_readable(tmp_path) -> None:
    """不可读表也必须来自智能助手中间库，不能以 allowed_read=false 绕过来源校验。"""

    (tmp_path / "tables.yaml").write_text(
        """
catalog_version: logistics_nl2sql_catalog.v1
domain: logistics
tables:
  - table_name: dws_logistics_detail_union
    display_name: 物流明细统一服务表
    domain: logistics
    source_system: sap_mid
    allowed_read: false
    columns:
      - {name: shipment_watt, data_type: decimal, nullable: true}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="catalog_table_source_system_invalid::dws_logistics_detail_union::sap_mid"):
        LogisticsSemanticCatalogLoader(tmp_path).load()


def test_semantic_catalog_loader_rejects_metric_unknown_source_column(tmp_path) -> None:
    """指标 source_columns 必须全部存在于指标声明表字段中。"""

    _write_minimal_catalog_tables(tmp_path)
    (tmp_path / "metrics.yaml").write_text(
        """
catalog_version: logistics_nl2sql_catalog.v1
domain: logistics
metrics:
  - metric_id: broken_metric
    display_name: 错误指标
    aliases: [错误指标]
    sql_expression: SUM(missing_fee)
    aggregation: sum
    table: dws_logistics_detail_union
    source_columns: [missing_fee]
""",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="catalog_metric_column_not_allowed::broken_metric::dws_logistics_detail_union.missing_fee",
    ):
        LogisticsSemanticCatalogLoader(tmp_path).load()


def test_semantic_catalog_loader_rejects_dimension_unknown_column(tmp_path) -> None:
    """维度 column 必须存在于维度声明表字段中。"""

    _write_minimal_catalog_tables(tmp_path)
    (tmp_path / "dimensions.yaml").write_text(
        """
catalog_version: logistics_nl2sql_catalog.v1
domain: logistics
dimensions:
  - dimension_id: broken_dimension
    display_name: 错误维度
    aliases: [错误维度]
    column: missing_dimension
    table: dws_logistics_detail_union
""",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="catalog_dimension_column_not_allowed::broken_dimension::dws_logistics_detail_union.missing_dimension",
    ):
        LogisticsSemanticCatalogLoader(tmp_path).load()


def test_semantic_catalog_loader_rejects_join_unknown_on_column(tmp_path) -> None:
    """Join on 表达式中的 table.column 必须存在于两侧表字段中。"""

    _write_minimal_catalog_tables(tmp_path)
    (tmp_path / "joins.yaml").write_text(
        """
catalog_version: logistics_nl2sql_catalog.v1
domain: logistics
joins:
  - join_id: broken_join
    left_table: dwd_logistics_ship_task
    right_table: dwd_logistics_assign_task
    join_type: left
    "on":
      - dwd_logistics_assign_task.missing_ship_task_id = dwd_logistics_ship_task.task_id
""",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="catalog_join_column_not_allowed::broken_join::dwd_logistics_assign_task.missing_ship_task_id",
    ):
        LogisticsSemanticCatalogLoader(tmp_path).load()


def test_semantic_catalog_loader_rejects_join_on_extra_sql_fragment(tmp_path) -> None:
    """Join on 只允许单个 table.column = table.column，不能夹带额外 SQL 片段。"""

    _write_minimal_catalog_tables(tmp_path)
    (tmp_path / "joins.yaml").write_text(
        """
catalog_version: logistics_nl2sql_catalog.v1
domain: logistics
joins:
  - join_id: unsafe_join
    left_table: dwd_logistics_ship_task
    right_table: dwd_logistics_assign_task
    join_type: left
    "on":
      - dwd_logistics_assign_task.ship_task_id = dwd_logistics_ship_task.task_id OR 1=1
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="catalog_join_on_expression_invalid::unsafe_join"):
        LogisticsSemanticCatalogLoader(tmp_path).load()


def test_semantic_catalog_loader_rejects_join_on_missing_join_side(tmp_path) -> None:
    """Join on 必须同时引用声明的 left_table 和 right_table。"""

    _write_minimal_catalog_tables(tmp_path)
    (tmp_path / "joins.yaml").write_text(
        """
catalog_version: logistics_nl2sql_catalog.v1
domain: logistics
joins:
  - join_id: one_side_join
    left_table: dwd_logistics_ship_task
    right_table: dwd_logistics_assign_task
    join_type: left
    "on":
      - dwd_logistics_ship_task.task_id = dwd_logistics_ship_task.task_id
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="catalog_join_on_missing_join_side::one_side_join"):
        LogisticsSemanticCatalogLoader(tmp_path).load()


def test_semantic_catalog_loader_rejects_join_on_multiple_predicates(tmp_path) -> None:
    """Join on 列表只能配置一条等值谓词，多条谓词必须 fail-closed。"""

    _write_minimal_catalog_tables(tmp_path)
    (tmp_path / "joins.yaml").write_text(
        """
catalog_version: logistics_nl2sql_catalog.v1
domain: logistics
joins:
  - join_id: multi_predicate_join
    left_table: dwd_logistics_ship_task
    right_table: dwd_logistics_assign_task
    join_type: left
    "on":
      - dwd_logistics_ship_task.task_id = dwd_logistics_assign_task.ship_task_id
      - dwd_logistics_ship_task.task_id = dwd_logistics_assign_task.task_id
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="catalog_join_on_expression_invalid::multi_predicate_join"):
        LogisticsSemanticCatalogLoader(tmp_path).load()


def test_semantic_catalog_loader_rejects_join_on_empty_predicates(tmp_path) -> None:
    """Join on 不能为空，缺失谓词时不能让后续 SQLPlan 自行猜测连接条件。"""

    _write_minimal_catalog_tables(tmp_path)
    (tmp_path / "joins.yaml").write_text(
        """
catalog_version: logistics_nl2sql_catalog.v1
domain: logistics
joins:
  - join_id: empty_predicate_join
    left_table: dwd_logistics_ship_task
    right_table: dwd_logistics_assign_task
    join_type: left
    "on": []
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="catalog_join_on_expression_invalid::empty_predicate_join"):
        LogisticsSemanticCatalogLoader(tmp_path).load()


def test_semantic_catalog_loader_rejects_join_on_third_table(tmp_path) -> None:
    """Join on 的表名必须来自声明的 left_table/right_table，第三张表必须 fail-closed。"""

    _write_minimal_catalog_tables(tmp_path)
    (tmp_path / "tables.yaml").write_text(
        (tmp_path / "tables.yaml").read_text(encoding="utf-8")
        + """
  - table_name: dm_logistics_company_month_rank
    display_name: 承运商月度排行表
    domain: logistics
    source_system: middle_db
    allowed_read: true
    columns:
      - {name: task_id, data_type: varchar, nullable: false}
""",
        encoding="utf-8",
    )
    (tmp_path / "joins.yaml").write_text(
        """
catalog_version: logistics_nl2sql_catalog.v1
domain: logistics
joins:
  - join_id: third_table_join
    left_table: dwd_logistics_ship_task
    right_table: dwd_logistics_assign_task
    join_type: left
    "on":
      - dwd_logistics_ship_task.task_id = dm_logistics_company_month_rank.task_id
""",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="catalog_join_on_table_not_in_join::third_table_join::dm_logistics_company_month_rank",
    ):
        LogisticsSemanticCatalogLoader(tmp_path).load()


def test_semantic_catalog_loader_rejects_same_table_join_declaration(tmp_path) -> None:
    """Join 声明的左右表必须是两张不同表，不能用同表自连接绕过两侧校验。"""

    _write_minimal_catalog_tables(tmp_path)
    (tmp_path / "joins.yaml").write_text(
        """
catalog_version: logistics_nl2sql_catalog.v1
domain: logistics
joins:
  - join_id: same_table_join
    left_table: dwd_logistics_assign_task
    right_table: dwd_logistics_assign_task
    join_type: left
    "on":
      - dwd_logistics_assign_task.task_id = dwd_logistics_assign_task.ship_task_id
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="catalog_join_same_table_not_allowed::same_table_join"):
        LogisticsSemanticCatalogLoader(tmp_path).load()


def test_tables_builder_filters_introspection_rows_to_whitelisted_tables() -> None:
    """tables.yaml 生成器必须从库表探查结果中只保留中间库物流白名单。"""

    rows = [
        {"table_name": "dws_logistics_detail_union", "column_name": "shipment_watt", "data_type": "decimal", "is_nullable": "YES"},
        {"table_name": "dws_logistics_detail_union", "column_name": "total_fee", "data_type": "decimal", "is_nullable": "YES"},
        {"table_name": "sys_query_log", "column_name": "query_text", "data_type": "text", "is_nullable": "YES"},
        {"table_name": "ods_logistic_ship_task", "column_name": "source_id", "data_type": "varchar", "is_nullable": "NO"},
        {"table_name": "V_SAP_HFFN_EKKO", "column_name": "EBELN", "data_type": "varchar", "is_nullable": "NO"},
    ]

    built = build_static_logistics_tables_catalog(rows)

    assert [table.table_name for table in built] == ["dws_logistics_detail_union"]
    assert [column.name for column in built[0].columns] == ["shipment_watt", "total_fee"]
    assert built[0].source_system == "middle_db"


def test_query_planner_v2_uses_catalog_quote_mouth_for_yunjia() -> None:
    """V2 规划归一化必须与新 catalog 一致：报价/单价/运价都走单价/车。"""

    normalizer = LogisticsQueryPlannerV2Normalizer()
    validator = LogisticsQueryPlannerV2Validator(registry=LogisticsQueryPlannerV2CapabilityRegistry())
    legacy_adapter = LogisticsQueryPlannerV2LegacyAdapter()
    question = "2025年合肥发广州17.5车运价是多少？"
    payload = {
        "intent": "aggregate",
        "query_key": "hist_route_pricing_analysis",
        "filters": {
            "years": [2025],
            "origin_place": "合肥",
            "city": "广州",
            "vehicle_type": "17.5",
            "view_mode": "avg_fee",
            "price_metric": "运价",
        },
        "metrics": ["avg_fee", "row_count"],
        "dimensions": [],
        "group_by": [],
        "aggregations": ["avg"],
        "compare_mode": None,
        "time_range": {"years": [2025]},
        "confidence": 0.95,
        "clarification_questions": [],
        "unsupported_reason": None,
        "normalized_question": question,
    }

    candidate = normalizer.normalize(payload, question=question)
    validation = validator.validate(candidate, original_question=question)
    plan = legacy_adapter.to_logistics_plan(validation.candidate)

    assert validation.accepted, validation.errors
    assert plan.filters["price_metric"] == "unit_price_per_vehicle"


def _write_minimal_catalog_tables(tmp_path) -> None:
    """写入字段级校验测试所需的最小合法表目录。

    参数：
        tmp_path: pytest 临时目录。
    返回：
        无；调用方可继续写入 metrics/dimensions/joins 触发负例。
    业务逻辑：
        只声明物流中间库白名单表和少量字段，确保负例失败原因聚焦在字段引用缺失。
    """

    (tmp_path / "tables.yaml").write_text(
        """
catalog_version: logistics_nl2sql_catalog.v1
domain: logistics
tables:
  - table_name: dws_logistics_detail_union
    display_name: 物流明细统一服务表
    domain: logistics
    source_system: middle_db
    allowed_read: true
    columns:
      - {name: shipment_watt, data_type: decimal, nullable: true}
      - {name: total_fee, data_type: decimal, nullable: true}
  - table_name: dwd_logistics_ship_task
    display_name: 系统物流发运任务表
    domain: logistics
    source_system: middle_db
    allowed_read: true
    columns:
      - {name: task_id, data_type: varchar, nullable: false}
  - table_name: dwd_logistics_assign_task
    display_name: 系统物流委派任务表
    domain: logistics
    source_system: middle_db
    allowed_read: true
    columns:
      - {name: task_id, data_type: varchar, nullable: false}
      - {name: ship_task_id, data_type: varchar, nullable: false}
""",
        encoding="utf-8",
    )
