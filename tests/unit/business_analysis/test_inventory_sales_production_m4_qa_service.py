from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.domains.business_analysis.models import BaIspExcelWorkbook, BaIspMetric, BaIspMonthlyFact
from backend.app.domains.business_analysis.repositories.inventory_sales_production_repository import METRIC_CATALOG
from backend.app.domains.business_analysis.services.inventory_sales_production.nl_query_planner import (
    InventorySalesProductionNlQueryPlanner,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.qa_service import (
    InventorySalesProductionQaService,
)


@pytest.fixture()
def db_session():
    """创建产销存 M4 问答测试数据库。

    说明：
        M4 只验证自然语言到受控 QueryPlan 的临时生成器、QA 服务和 M3 执行器衔接，
        不依赖真实 Excel 文件，也不让测试绕过中间库事实表。
    """

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        for metric in METRIC_CATALOG:
            session.merge(BaIspMetric(**metric))
        session.commit()
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _seed_workbook(session, *, year: int, cutoff_month: int = 12) -> BaIspExcelWorkbook:
    """写入测试用工作簿版本。"""

    workbook = BaIspExcelWorkbook(
        source_file_name=f"测试产销存-{year}.xlsx",
        source_file_sha256=f"sha256-{year}-{cutoff_month}",
        source_file_size=1024,
        business_year=year,
        data_cutoff_month=cutoff_month,
        source_version_label=f"{year}.{cutoff_month:02d}",
        upload_batch_no=f"M4-TEST-{year}-{cutoff_month}",
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
    """根据维度生成稳定来源行偏移，避免单元格唯一约束冲突。"""

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
    trade_scope: str | None = None,
    is_default_external_sales: int = 0,
) -> None:
    """插入一条产销存标准月度事实。"""

    row_no = month + _source_offset(metric_code, base_name, trade_scope)
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
            model_type=None,
            production_mode=None,
            trade_scope=trade_scope,
            is_outsourced=0,
            is_consigned=1 if metric_category == "consignment" else 0,
            is_default_external_sales=is_default_external_sales,
            source_file_name=workbook.source_file_name,
            source_file_sha256=workbook.source_file_sha256,
            source_sheet="测试",
            source_row_index=row_no,
            source_col_index=month + 10,
            source_cell_ref=f"A{row_no}",
            raw_category=metric_category,
            raw_item=metric_name,
            raw_unit="MW",
            parser_version="test",
            quality_flags="{}",
        )
    )


def _assert_no_user_visible_technical_leak(text: str) -> None:
    """断言用户可见文案不含内部技术实现痕迹。"""

    forbidden = ["SQL", "query_key", "planner", "guardrail", "schema", "raw", "LLM", "ba_isp", "metric_code"]
    for word in forbidden:
        assert word.lower() not in text.lower()


def test_nl_planner_maps_sales_question_to_controlled_query_plan() -> None:
    """自然语言只允许生成产销存受控 QueryPlan，不能生成自由 SQL。"""

    plan = InventorySalesProductionNlQueryPlanner().build_plan("2024年销量是多少？")

    assert plan.domain == "business_analysis"
    assert plan.sub_domain == "inventory_sales_production"
    assert plan.query_key == "ba_isp_metric_summary"
    assert plan.metrics == ["shipment_volume"]
    assert plan.period.year == 2024
    assert plan.period.period_type == "year"
    assert "sql" not in plan.filters
    assert "table" not in plan.filters


def test_nl_planner_maps_inventory_and_published_month_boundary() -> None:
    """库存/存货问题必须映射为时点指标，并保留 2026 已发布月份边界。"""

    plan = InventorySalesProductionNlQueryPlanner().build_plan("2026年4月库存是多少？")

    assert plan.query_key == "ba_isp_inventory_snapshot"
    assert plan.metrics == ["ending_inventory_volume"]
    assert plan.period.year == 2026
    assert plan.period.period_type == "month"
    assert plan.period.month == 4


def test_qa_service_runs_m3_executor_and_returns_business_presentation(db_session) -> None:
    """M4 QA 服务必须复用 M3 执行器，并返回不暴露内部实现的业务化展示结果。"""

    workbook = _seed_workbook(db_session, year=2024)
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

    result = InventorySalesProductionQaService(db_session).ask("2024年销量是多少？", trace_id="trace-m4")

    assert result.domain == "business_analysis"
    assert result.sub_domain == "inventory_sales_production"
    assert result.status["code"] == "OK"
    assert result.presentation["title"] == "产销存经营分析"
    assert "385.332353" in result.presentation["answer"]
    assert "剔除内部交易" in "".join(result.warnings)
    assert result.result_table["columns"] == ["期间", "指标", "数值", "单位", "覆盖月份", "数据行数"]
    assert result.result_table["rows"][0]["数值"] == "385.33235300"
    _assert_no_user_visible_technical_leak(result.answer_summary)
    _assert_no_user_visible_technical_leak(result.presentation["answer"])


def test_qa_service_fails_closed_for_unsupported_turnover_question(db_session) -> None:
    """库存周转率等缺数据问题必须业务化澄清，不能编造公式或让 LLM 直接计算。"""

    result = InventorySalesProductionQaService(db_session).ask("2025年库存周转率是多少？", trace_id="trace-m4")

    assert result.status["code"] == "CLARIFICATION_REQUIRED"
    assert result.classification == "B"
    assert "库存周转率" in result.answer_summary
    assert "补充" in result.answer_summary
    assert result.result_table is None
    _assert_no_user_visible_technical_leak(result.answer_summary)
