from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.domains.business_analysis.models import (
    BaIspExcelWorkbook,
    BaIspMetric,
    BaIspMonthlyFact,
)
from backend.app.domains.business_analysis.repositories.inventory_sales_production_repository import METRIC_CATALOG
from backend.app.domains.business_analysis.schemas.inventory_sales_production_query import (
    InventorySalesProductionPeriodSpec,
    InventorySalesProductionQueryPlan,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.query_executor import (
    InventorySalesProductionQueryExecutor,
)


@pytest.fixture()
def db_session():
    """创建产销存 M3 单元测试 SQLite 会话。

    说明：测试只验证 QueryPlan/执行器/聚合策略，不依赖真实 Excel 文件，避免把解析验收和查询验收耦合。
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        _seed_metric_catalog(session)
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _seed_metric_catalog(session) -> None:
    """写入 M2 指标白名单，供 QueryPlan 校验使用。"""
    for metric in METRIC_CATALOG:
        session.merge(BaIspMetric(**metric))
    session.commit()


def _seed_workbook(session, *, year: int, cutoff_month: int = 12) -> BaIspExcelWorkbook:
    """创建一个测试工作簿版本。"""
    workbook = BaIspExcelWorkbook(
        source_file_name=f"测试产销存-{year}.xlsx",
        source_file_sha256=f"sha256-{year}-{cutoff_month}",
        source_file_size=1024,
        business_year=year,
        data_cutoff_month=cutoff_month,
        source_version_label=f"{year}.{cutoff_month:02d}",
        upload_batch_no=f"TEST-{year}-{cutoff_month}",
        sheet_count=1,
        has_vba=0,
        external_link_count=0,
        parser_version="test",
        quality_status="success",
    )
    session.add(workbook)
    session.flush()
    return workbook


def _source_offset(*values: str | None) -> int:
    """根据维度值生成稳定来源行偏移，避免测试事实撞到来源坐标唯一约束。"""
    text = "|".join(value or "" for value in values)
    return sum(ord(char) for char in text) % 1000


def _add_fact(
    session,
    *,
    workbook: BaIspExcelWorkbook,
    month: int,
    metric_code: str,
    metric_name: str,
    metric_category: str,
    aggregation_type: str,
    value: str,
    base_name: str | None = None,
    model_type: str | None = None,
    trade_scope: str | None = None,
    is_default_external_sales: int = 0,
) -> None:
    """插入一条标准月度事实。"""
    session.add(
        BaIspMonthlyFact(
            workbook_id=workbook.id,
            sheet_id=None,
            business_year=workbook.business_year,
            business_month=month,
            period_label=f"{workbook.business_year}-{month:02d}",
            period_start_date=date(workbook.business_year, month, 1),
            period_end_date=date(workbook.business_year, month, 28),
            data_cutoff_month=workbook.data_cutoff_month,
            is_published_month=1,
            domain="business_analysis",
            sub_domain="inventory_sales_production",
            metric_code=metric_code,
            metric_name=metric_name,
            metric_category=metric_category,
            aggregation_type=aggregation_type,
            value_decimal=Decimal(value),
            unit_standard="MW",
            base_name=base_name,
            factory_name=None,
            model_type=model_type,
            production_mode=None,
            trade_scope=trade_scope,
            is_outsourced=0,
            is_consigned=1 if metric_category == "consignment" else 0,
            is_default_external_sales=is_default_external_sales,
            source_file_name=workbook.source_file_name,
            source_file_sha256=workbook.source_file_sha256,
            source_sheet="测试",
            source_row_index=month + _source_offset(base_name, model_type, trade_scope),
            source_col_index=month + 10,
            source_cell_ref=f"A{month + _source_offset(base_name, model_type, trade_scope)}",
            raw_category=metric_category,
            raw_item=metric_name,
            raw_unit="MW",
            parser_version="test",
            quality_flags="{}",
        )
    )


def _plan(
    *,
    query_key: str,
    metric: str,
    year: int,
    period_type: str = "year",
    dimensions: list[str] | None = None,
    filters: dict | None = None,
    month: int | None = None,
    end_month: int | None = None,
) -> InventorySalesProductionQueryPlan:
    """构造测试 QueryPlan。"""
    return InventorySalesProductionQueryPlan(
        query_key=query_key,
        intent="metric_query",
        metrics=[metric],
        dimensions=dimensions or [],
        filters=filters or {},
        period=InventorySalesProductionPeriodSpec(
            period_type=period_type,
            year=year,
            month=month,
            end_month=end_month,
        ),
    )


def test_query_executor_flow_sum_summary_recomputes_year_from_monthly_facts(db_session) -> None:
    """流量型指标必须按已发布月度事实求和，不能依赖 Excel 年度列。"""
    workbook = _seed_workbook(db_session, year=2025)
    _add_fact(
        db_session,
        workbook=workbook,
        month=1,
        metric_code="production_actual_including_oem",
        metric_name="实际产量（含委外）",
        metric_category="production",
        aggregation_type="flow_sum",
        value="100.25",
    )
    _add_fact(
        db_session,
        workbook=workbook,
        month=2,
        metric_code="production_actual_including_oem",
        metric_name="实际产量（含委外）",
        metric_category="production",
        aggregation_type="flow_sum",
        value="200.75",
    )
    db_session.commit()

    result = InventorySalesProductionQueryExecutor(db_session).execute(
        _plan(query_key="ba_isp_metric_summary", metric="production_actual_including_oem", year=2025)
    )

    assert result.status == "success"
    assert result.rows[0].value_decimal == Decimal("301.00000000")
    assert result.rows[0].months_covered == [1, 2]
    assert result.calculation_policy == "flow_sum"
    assert "SQL" not in result.answer_summary
    assert "planner" not in result.answer_summary.lower()


def test_query_executor_period_end_inventory_uses_last_published_month_not_sum(db_session) -> None:
    """时点库存必须取最后已发布月份，不允许把多个月库存相加。"""
    workbook = _seed_workbook(db_session, year=2026, cutoff_month=4)
    for month, value in [(1, "100"), (4, "120")]:
        _add_fact(
            db_session,
            workbook=workbook,
            month=month,
            metric_code="ending_inventory_volume",
            metric_name="期末库存/存货",
            metric_category="inventory",
            aggregation_type="period_end",
            value=value,
        )
    db_session.commit()

    result = InventorySalesProductionQueryExecutor(db_session).execute(
        _plan(query_key="ba_isp_inventory_snapshot", metric="ending_inventory_volume", year=2026)
    )

    assert result.status == "success"
    assert result.rows[0].value_decimal == Decimal("120.00000000")
    assert result.rows[0].months_covered == [4]
    assert result.calculation_policy == "period_end"
    assert any("最后已发布月份" in warning for warning in result.warnings)


def test_query_executor_rejects_unpublished_future_month(db_session) -> None:
    """显式查询未发布月份必须 fail closed，不能把空值或未来月份当 0。"""
    workbook = _seed_workbook(db_session, year=2026, cutoff_month=4)
    _add_fact(
        db_session,
        workbook=workbook,
        month=4,
        metric_code="shipment_volume",
        metric_name="发货量/销量",
        metric_category="shipment",
        aggregation_type="flow_sum",
        value="88",
    )
    db_session.commit()

    result = InventorySalesProductionQueryExecutor(db_session).execute(
        _plan(query_key="ba_isp_metric_summary", metric="shipment_volume", year=2026, period_type="month", month=5)
    )

    assert result.status == "clarification"
    assert "未发布" in result.answer_summary
    assert result.rows == []


def test_query_executor_breakdown_groups_by_allowed_dimension(db_session) -> None:
    """按基地拆分时，执行器只能使用白名单维度并返回确定性分组结果。"""
    workbook = _seed_workbook(db_session, year=2025)
    for base_name, value in [("合肥", "100"), ("阜宁", "50")]:
        _add_fact(
            db_session,
            workbook=workbook,
            month=1,
            metric_code="shipment_by_base",
            metric_name="基地发货量/销量",
            metric_category="shipment",
            aggregation_type="flow_sum",
            value=value,
            base_name=base_name,
        )
    db_session.commit()

    result = InventorySalesProductionQueryExecutor(db_session).execute(
        _plan(query_key="ba_isp_metric_breakdown", metric="shipment_by_base", year=2025, dimensions=["base_name"])
    )

    assert result.status == "success"
    assert [(row.dimensions["base_name"], row.value_decimal) for row in result.rows] == [
        ("合肥", Decimal("100.00000000")),
        ("阜宁", Decimal("50.00000000")),
    ]
    assert result.query_key == "ba_isp_metric_breakdown"


def test_query_executor_budget_achievement_recomputes_ratio_from_actual_and_budget(db_session) -> None:
    """预算达成率必须由后端用实际产量和预算月度事实重算。"""
    workbook = _seed_workbook(db_session, year=2023)
    for month, actual, budget in [(1, "80", "100"), (2, "120", "100")]:
        _add_fact(
            db_session,
            workbook=workbook,
            month=month,
            metric_code="production_actual_including_oem",
            metric_name="实际产量（含委外）",
            metric_category="production",
            aggregation_type="flow_sum",
            value=actual,
        )
        _add_fact(
            db_session,
            workbook=workbook,
            month=month,
            metric_code="production_budget",
            metric_name="产量预算/目标",
            metric_category="budget",
            aggregation_type="flow_sum",
            value=budget,
        )
    db_session.commit()

    result = InventorySalesProductionQueryExecutor(db_session).execute(
        _plan(query_key="ba_isp_budget_achievement", metric="production_actual_including_oem", year=2023)
    )

    assert result.status == "success"
    assert result.rows[0].value_decimal == Decimal("100.00000000")
    assert result.rows[0].unit_standard == "percent"
    assert result.rows[0].extra["actual_value"] == "200.00000000"
    assert result.rows[0].extra["budget_value"] == "200.00000000"
    assert result.calculation_policy == "calculated_ratio"


def test_query_executor_budget_achievement_fails_closed_when_budget_missing(db_session) -> None:
    """缺少预算分母时不能退化成产量查询或让 LLM 猜测达成率。"""
    workbook = _seed_workbook(db_session, year=2025)
    _add_fact(
        db_session,
        workbook=workbook,
        month=1,
        metric_code="production_actual_including_oem",
        metric_name="实际产量（含委外）",
        metric_category="production",
        aggregation_type="flow_sum",
        value="100",
    )
    db_session.commit()

    result = InventorySalesProductionQueryExecutor(db_session).execute(
        _plan(query_key="ba_isp_budget_achievement", metric="production_actual_including_oem", year=2025)
    )

    assert result.status == "clarification"
    assert "缺少预算" in result.answer_summary
    assert result.rows == []


def test_query_executor_2024_sales_defaults_to_external_sales_scope(db_session) -> None:
    """2024 用户问销量时应采用组件事业部剔除内部交易的默认对外销量口径。"""
    workbook = _seed_workbook(db_session, year=2024)
    _add_fact(
        db_session,
        workbook=workbook,
        month=12,
        metric_code="shipment_volume",
        metric_name="发货量/销量",
        metric_category="shipment",
        aggregation_type="flow_sum",
        value="999",
    )
    _add_fact(
        db_session,
        workbook=workbook,
        month=12,
        metric_code="shipment_external_excluding_internal",
        metric_name="对外销量（剔除内部交易）",
        metric_category="shipment",
        aggregation_type="flow_sum",
        value="385.332353",
        trade_scope="剔除内部交易",
        is_default_external_sales=1,
    )
    db_session.commit()

    result = InventorySalesProductionQueryExecutor(db_session).execute(
        _plan(query_key="ba_isp_metric_summary", metric="shipment_volume", year=2024)
    )

    assert result.status == "success"
    assert result.rows[0].metric_code == "shipment_external_excluding_internal"
    assert result.rows[0].value_decimal == Decimal("385.33235300")
    assert any("剔除内部交易" in warning for warning in result.warnings)


def test_query_plan_validator_rejects_unknown_metric_dimension_and_invoice_without_explicit_phrase(db_session) -> None:
    """QueryPlan 校验必须 fail closed：未知指标/维度和开票隐式触发都不能执行。"""
    executor = InventorySalesProductionQueryExecutor(db_session)

    bad_metric = executor.execute(_plan(query_key="ba_isp_metric_summary", metric="fake_metric", year=2025))
    bad_dimension = executor.execute(
        _plan(query_key="ba_isp_metric_breakdown", metric="shipment_by_base", year=2025, dimensions=["table_name"])
    )
    bad_invoice = executor.execute(_plan(query_key="ba_isp_metric_summary", metric="invoice_sales_volume", year=2025))

    assert bad_metric.status == "unsupported"
    assert "暂不支持该产销存指标" in bad_metric.answer_summary
    assert bad_dimension.status == "unsupported"
    assert "暂不支持该拆分维度" in bad_dimension.answer_summary
    assert bad_invoice.status == "clarification"
    assert "开票" in bad_invoice.answer_summary
