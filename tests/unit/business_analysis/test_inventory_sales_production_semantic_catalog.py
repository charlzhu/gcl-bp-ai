from __future__ import annotations

import pytest

from backend.app.domains.business_analysis.repositories.inventory_sales_production_repository import METRIC_CATALOG
from backend.app.domains.business_analysis.services.inventory_sales_production.semantic_catalog import (
    InventorySalesProductionSemanticCatalogLoader,
)


def _minimal_catalog_payload(**overrides):
    """构造最小产销存语义目录载荷，便于 focused 负例只表达本轮边界。"""

    payload = {
        "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
        "domain": "business_analysis",
        "sub_domain": "inventory_sales_production",
        "tables": [
            {
                "table_name": "dwd_ba_isp_monthly_fact",
                "display_name": "产销存月度事实",
                "domain": "business_analysis",
                "sub_domain": "inventory_sales_production",
                "source_system": "middle_db",
                "allowed_read": True,
                "columns": [
                    {"name": "business_year", "data_type": "int"},
                    {"name": "business_month", "data_type": "int"},
                    {"name": "metric_code", "data_type": "varchar"},
                    {"name": "value_decimal", "data_type": "decimal"},
                    {"name": "is_published_month", "data_type": "smallint"},
                ],
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_isp_semantic_catalog_registers_mvp_metrics_aliases_and_dimensions() -> None:
    """产销存语义目录必须注册 M2/M4 已落地指标、同义词和 QueryPlan 白名单维度。"""

    catalog = InventorySalesProductionSemanticCatalogLoader().load()

    assert catalog.catalog_version == "business_analysis_inventory_sales_production_catalog.v1"
    assert catalog.domain == "business_analysis"
    assert catalog.sub_domain == "inventory_sales_production"

    seeded_metric_ids = {entry["metric_code"] for entry in METRIC_CATALOG}
    catalog_metric_ids = {metric.metric_id for metric in catalog.metrics}
    assert seeded_metric_ids <= catalog_metric_ids
    assert len(catalog_metric_ids) == len(seeded_metric_ids) + 1

    production = catalog.get_metric("production_actual_including_oem")
    assert production.display_name == "实际产量（含委外）"
    assert production.table == "dwd_ba_isp_monthly_fact"
    assert production.aggregation == "flow_sum"
    assert production.unit == "MW"
    assert "value_decimal" in production.source_columns
    assert "business_month" in production.source_columns

    model_type_production = catalog.get_metric("production_by_model_type")
    assert model_type_production.display_name == "版型产量"
    assert model_type_production.metric_category == "production"
    assert "model_type" in model_type_production.source_columns

    production_budget = catalog.get_metric("production_budget")
    assert production_budget.display_name == "产量预算/目标"
    assert production_budget.metric_category == "budget"
    assert production_budget.aggregation == "flow_sum"
    assert production_budget.unit == "MW"

    shipment_external = catalog.get_metric("shipment_external_excluding_internal")
    assert shipment_external.support_status == "supported"
    assert shipment_external.default_for_sales is True
    assert catalog.resolve_metric_alias("销量").metric_id == "shipment_volume"
    assert catalog.resolve_metric_alias("销售量").metric_id == "shipment_volume"
    assert catalog.resolve_metric_alias("库存（SAP数据）").metric_id == "ending_inventory_volume"
    assert catalog.resolve_metric_alias("寄存合计").metric_id == "consigned_inventory_volume"
    assert catalog.resolve_metric_alias("开票").requires_explicit_phrase is True

    year_dimension = catalog.get_dimension("business_year")
    assert year_dimension.display_name == "年份"
    assert year_dimension.table == "dwd_ba_isp_monthly_fact"
    assert year_dimension.column == "business_year"
    assert catalog.resolve_dimension_alias("年份").dimension_id == "business_year"

    quarter_dimension = catalog.get_dimension("business_quarter")
    assert quarter_dimension.display_name == "季度"
    assert quarter_dimension.table == "dwd_ba_isp_monthly_fact"
    assert quarter_dimension.column == "business_month"
    assert catalog.resolve_dimension_alias("季度").dimension_id == "business_quarter"

    base_dimension = catalog.get_dimension("base_name")
    assert base_dimension.display_name == "基地"
    assert base_dimension.table == "dwd_ba_isp_monthly_fact"
    assert base_dimension.column == "base_name"
    assert catalog.resolve_dimension_alias("按基地").dimension_id == "base_name"
    assert catalog.resolve_dimension_alias("各版型").dimension_id == "model_type"


def test_isp_semantic_catalog_registers_budget_achievement_as_calculated_metric() -> None:
    """预算达成率必须作为可校验的计算类指标进入语义目录。"""

    catalog = InventorySalesProductionSemanticCatalogLoader().load()

    metric = catalog.get_metric("production_budget_achievement_rate")
    assert metric.display_name == "产量预算达成率"
    assert metric.aggregation == "calculated_ratio"
    assert metric.unit == "percent"
    assert metric.metric_category == "rate"
    assert metric.support_status == "supported"
    assert metric.source_columns == [
        "business_year",
        "business_month",
        "metric_code",
        "value_decimal",
        "is_published_month",
    ]
    assert metric.depends_on_metrics == ["production_actual_including_oem", "production_budget"]
    assert catalog.resolve_metric_alias("产量预算达成率").metric_id == "production_budget_achievement_rate"
    assert catalog.resolve_metric_alias("生产预算达成率").metric_id == "production_budget_achievement_rate"
    with pytest.raises(KeyError, match="metric_alias_not_found::预算达成率"):
        catalog.resolve_metric_alias("预算达成率")
    with pytest.raises(KeyError, match="metric_alias_not_found::目标达成率"):
        catalog.resolve_metric_alias("目标达成率")
    catalog.validate_query_plan_support(
        query_key="ba_isp_budget_achievement",
        metrics=["production_budget_achievement_rate"],
        dimensions=[],
        filters={},
    )
    catalog.validate_query_plan_support(
        query_key="ba_isp_budget_achievement",
        metrics=["production_actual_including_oem"],
        dimensions=[],
        filters={},
    )
    with pytest.raises(
        ValueError,
        match="catalog_query_key_dimension_mismatch::ba_isp_budget_achievement::business_year",
    ):
        catalog.validate_query_plan_support(
            query_key="ba_isp_budget_achievement",
            metrics=["production_actual_including_oem"],
            dimensions=["business_year"],
            filters={},
        )


def test_isp_semantic_catalog_rejects_trace_columns_even_when_table_not_readable() -> None:
    """字段边界必须对所有目录表 fail-closed，不能靠 allowed_read=False 隐藏原始来源字段。"""

    blocked_columns = [
        {"name": "source_file_name", "data_type": "varchar"},
        {"name": "raw_item", "data_type": "varchar"},
        {"name": "import_audit_id", "data_type": "varchar", "semantic_role": "trace"},
    ]
    for column in blocked_columns:
        payload = _minimal_catalog_payload(
            tables=[
                {
                    "table_name": "dwd_ba_isp_monthly_fact",
                    "display_name": "产销存月度事实",
                    "domain": "business_analysis",
                    "sub_domain": "inventory_sales_production",
                    "source_system": "middle_db",
                    "allowed_read": False,
                    "columns": [
                        {"name": "value_decimal", "data_type": "decimal"},
                        column,
                    ],
                }
            ]
        )
        with pytest.raises(
            ValueError,
            match=f"catalog_table_column_not_allowed::dwd_ba_isp_monthly_fact.{column['name']}",
        ):
            InventorySalesProductionSemanticCatalogLoader(payload=payload).load()


def test_isp_semantic_catalog_tables_are_limited_to_middle_db_business_analysis_whitelist() -> None:
    """产销存语义目录只能暴露智能助手中间库的标准事实/维表，不能混入 ODS、日志或外部源表。"""

    catalog = InventorySalesProductionSemanticCatalogLoader().load()
    table_names = catalog.allowed_table_names()

    assert table_names == {
        "dwd_ba_isp_monthly_fact",
        "dim_ba_isp_metric",
        "dim_ba_isp_metric_alias",
    }
    assert "ods_ba_isp_excel_workbook" not in table_names
    assert "ods_ba_isp_excel_sheet" not in table_names
    assert "sys_query_log" not in table_names
    assert "V_SAP_HFFN_CRKLSZ" not in table_names

    for table in catalog.allowed_tables():
        assert table.domain == "business_analysis"
        assert table.sub_domain == "inventory_sales_production"
        assert table.source_system == "middle_db"
        assert table.allowed_read is True
        assert table.columns
        for column in table.columns:
            assert not column.name.startswith(("source_", "raw_", "trace_")), column.name
            assert column.semantic_role != "trace", column.name


def test_isp_semantic_catalog_validates_query_key_metric_dimension_and_explicit_alias_status() -> None:
    """语义目录必须 fail-closed 校验查询能力、指标、维度和必须显式触发的同义词状态。"""

    catalog = InventorySalesProductionSemanticCatalogLoader().load()

    catalog.validate_query_plan_support(
        query_key="ba_isp_metric_breakdown",
        metrics=["shipment_by_base"],
        dimensions=["base_name"],
        filters={},
    )
    catalog.validate_query_plan_support(
        query_key="ba_isp_metric_summary",
        metrics=["invoice_sales_volume"],
        dimensions=[],
        filters={"explicit_invoice": True},
    )

    with pytest.raises(ValueError, match="catalog_query_key_not_supported::ba_isp_free_sql"):
        catalog.validate_query_plan_support(
            query_key="ba_isp_free_sql",
            metrics=["shipment_volume"],
            dimensions=[],
            filters={},
        )
    with pytest.raises(ValueError, match="catalog_metric_not_supported::unknown_metric"):
        catalog.validate_query_plan_support(
            query_key="ba_isp_metric_summary",
            metrics=["unknown_metric"],
            dimensions=[],
            filters={},
        )
    with pytest.raises(ValueError, match="catalog_dimension_not_supported::raw_item"):
        catalog.validate_query_plan_support(
            query_key="ba_isp_metric_breakdown",
            metrics=["shipment_volume"],
            dimensions=["raw_item"],
            filters={},
        )
    with pytest.raises(ValueError, match="catalog_metric_requires_explicit_phrase::invoice_sales_volume"):
        catalog.validate_query_plan_support(
            query_key="ba_isp_metric_summary",
            metrics=["invoice_sales_volume"],
            dimensions=[],
            filters={},
        )
    with pytest.raises(
        ValueError,
        match="catalog_query_key_dimension_mismatch::ba_isp_metric_summary::base_name",
    ):
        catalog.validate_query_plan_support(
            query_key="ba_isp_metric_summary",
            metrics=["shipment_volume"],
            dimensions=["base_name"],
            filters={},
        )
    with pytest.raises(ValueError, match="catalog_query_key_dimension_required::ba_isp_metric_breakdown"):
        catalog.validate_query_plan_support(
            query_key="ba_isp_metric_breakdown",
            metrics=["shipment_volume"],
            dimensions=[],
            filters={},
        )
    with pytest.raises(
        ValueError,
        match="catalog_query_key_metric_mismatch::ba_isp_inventory_snapshot::shipment_volume",
    ):
        catalog.validate_query_plan_support(
            query_key="ba_isp_inventory_snapshot",
            metrics=["shipment_volume"],
            dimensions=[],
            filters={},
        )
    with pytest.raises(
        ValueError,
        match="catalog_query_key_metric_mismatch::ba_isp_budget_achievement::shipment_volume",
    ):
        catalog.validate_query_plan_support(
            query_key="ba_isp_budget_achievement",
            metrics=["shipment_volume"],
            dimensions=[],
            filters={},
        )
    with pytest.raises(
        ValueError,
        match="catalog_query_key_metric_mismatch::ba_isp_metric_summary::production_budget_achievement_rate",
    ):
        catalog.validate_query_plan_support(
            query_key="ba_isp_metric_summary",
            metrics=["production_budget_achievement_rate"],
            dimensions=[],
            filters={},
        )


def test_isp_semantic_catalog_rejects_unsafe_table_and_field_config() -> None:
    """目录加载期必须阻断非白名单表、非中间库来源和未声明字段引用。"""

    unsafe_table_payload = {
        "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
        "domain": "business_analysis",
        "sub_domain": "inventory_sales_production",
        "tables": [
            {
                "table_name": "ods_ba_isp_excel_workbook",
                "display_name": "原始工作簿",
                "domain": "business_analysis",
                "sub_domain": "inventory_sales_production",
                "source_system": "middle_db",
                "allowed_read": True,
                "columns": [{"name": "source_file_name", "data_type": "varchar"}],
            }
        ],
    }
    with pytest.raises(ValueError, match="catalog_table_not_allowed::ods_ba_isp_excel_workbook"):
        InventorySalesProductionSemanticCatalogLoader(payload=unsafe_table_payload).load()

    unsafe_source_payload = {
        "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
        "domain": "business_analysis",
        "sub_domain": "inventory_sales_production",
        "tables": [
            {
                "table_name": "dwd_ba_isp_monthly_fact",
                "display_name": "产销存月度事实",
                "domain": "business_analysis",
                "sub_domain": "inventory_sales_production",
                "source_system": "sap_mid",
                "allowed_read": True,
                "columns": [{"name": "value_decimal", "data_type": "decimal"}],
            }
        ],
    }
    with pytest.raises(ValueError, match="catalog_table_source_system_invalid::dwd_ba_isp_monthly_fact::sap_mid"):
        InventorySalesProductionSemanticCatalogLoader(payload=unsafe_source_payload).load()

    unsafe_column_prefix_payload = {
        "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
        "domain": "business_analysis",
        "sub_domain": "inventory_sales_production",
        "tables": [
            {
                "table_name": "dwd_ba_isp_monthly_fact",
                "display_name": "产销存月度事实",
                "domain": "business_analysis",
                "sub_domain": "inventory_sales_production",
                "source_system": "middle_db",
                "allowed_read": True,
                "columns": [
                    {"name": "value_decimal", "data_type": "decimal"},
                    {"name": "source_file_name", "data_type": "varchar"},
                ],
            }
        ],
    }
    with pytest.raises(
        ValueError,
        match="catalog_table_column_not_allowed::dwd_ba_isp_monthly_fact.source_file_name",
    ):
        InventorySalesProductionSemanticCatalogLoader(payload=unsafe_column_prefix_payload).load()

    unsafe_trace_column_payload = {
        "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
        "domain": "business_analysis",
        "sub_domain": "inventory_sales_production",
        "tables": [
            {
                "table_name": "dwd_ba_isp_monthly_fact",
                "display_name": "产销存月度事实",
                "domain": "business_analysis",
                "sub_domain": "inventory_sales_production",
                "source_system": "middle_db",
                "allowed_read": True,
                "columns": [
                    {"name": "value_decimal", "data_type": "decimal"},
                    {"name": "import_audit_id", "data_type": "varchar", "semantic_role": "trace"},
                ],
            }
        ],
    }
    with pytest.raises(
        ValueError,
        match="catalog_table_column_not_allowed::dwd_ba_isp_monthly_fact.import_audit_id",
    ):
        InventorySalesProductionSemanticCatalogLoader(payload=unsafe_trace_column_payload).load()

    unsafe_metric_payload = {
        "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
        "domain": "business_analysis",
        "sub_domain": "inventory_sales_production",
        "tables": [
            {
                "table_name": "dwd_ba_isp_monthly_fact",
                "display_name": "产销存月度事实",
                "domain": "business_analysis",
                "sub_domain": "inventory_sales_production",
                "source_system": "middle_db",
                "allowed_read": True,
                "columns": [{"name": "value_decimal", "data_type": "decimal"}],
            }
        ],
        "metrics": [
            {
                "metric_id": "broken_metric",
                "display_name": "错误指标",
                "aliases": ["错误指标"],
                "table": "dwd_ba_isp_monthly_fact",
                "source_columns": ["missing_value"],
                "aggregation": "flow_sum",
                "unit": "MW",
            }
        ],
    }
    with pytest.raises(
        ValueError,
        match="catalog_metric_column_not_allowed::broken_metric::dwd_ba_isp_monthly_fact.missing_value",
    ):
        InventorySalesProductionSemanticCatalogLoader(payload=unsafe_metric_payload).load()

    unsafe_calculated_without_dependencies_payload = {
        "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
        "domain": "business_analysis",
        "sub_domain": "inventory_sales_production",
        "tables": [
            {
                "table_name": "dwd_ba_isp_monthly_fact",
                "display_name": "产销存月度事实",
                "domain": "business_analysis",
                "sub_domain": "inventory_sales_production",
                "source_system": "middle_db",
                "allowed_read": True,
                "columns": [
                    {"name": "business_year", "data_type": "int"},
                    {"name": "business_month", "data_type": "int"},
                    {"name": "metric_code", "data_type": "varchar"},
                    {"name": "value_decimal", "data_type": "decimal"},
                    {"name": "is_published_month", "data_type": "smallint"},
                ],
            }
        ],
        "metrics": [
            {
                "metric_id": "broken_calculated_metric",
                "display_name": "错误计算指标",
                "aliases": ["错误计算指标"],
                "table": "dwd_ba_isp_monthly_fact",
                "source_columns": ["business_year", "business_month", "metric_code", "value_decimal", "is_published_month"],
                "aggregation": "calculated_ratio",
                "unit": "percent",
            }
        ],
    }
    with pytest.raises(ValueError, match="catalog_metric_dependency_required::broken_calculated_metric"):
        InventorySalesProductionSemanticCatalogLoader(payload=unsafe_calculated_without_dependencies_payload).load()

    unsafe_dependency_payload = {
        "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
        "domain": "business_analysis",
        "sub_domain": "inventory_sales_production",
        "tables": [
            {
                "table_name": "dwd_ba_isp_monthly_fact",
                "display_name": "产销存月度事实",
                "domain": "business_analysis",
                "sub_domain": "inventory_sales_production",
                "source_system": "middle_db",
                "allowed_read": True,
                "columns": [
                    {"name": "business_year", "data_type": "int"},
                    {"name": "business_month", "data_type": "int"},
                    {"name": "metric_code", "data_type": "varchar"},
                    {"name": "value_decimal", "data_type": "decimal"},
                    {"name": "is_published_month", "data_type": "smallint"},
                ],
            }
        ],
        "metrics": [
            {
                "metric_id": "broken_calculated_metric",
                "display_name": "错误计算指标",
                "aliases": ["错误计算指标"],
                "table": "dwd_ba_isp_monthly_fact",
                "source_columns": ["business_year", "business_month", "metric_code", "value_decimal", "is_published_month"],
                "aggregation": "calculated_ratio",
                "unit": "percent",
                "depends_on_metrics": ["missing_metric"],
            }
        ],
    }
    with pytest.raises(
        ValueError,
        match="catalog_metric_dependency_not_allowed::broken_calculated_metric::missing_metric",
    ):
        InventorySalesProductionSemanticCatalogLoader(payload=unsafe_dependency_payload).load()
