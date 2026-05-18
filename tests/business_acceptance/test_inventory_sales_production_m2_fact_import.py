from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.domains.business_analysis.models import (
    BaIspExcelWorkbook,
    BaIspMonthlyFact,
)
from backend.app.domains.business_analysis.repositories.inventory_sales_production_repository import (
    InventorySalesProductionRepository,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.excel_import_service import (
    InventorySalesProductionExcelImportService,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.excel_parser import (
    InventorySalesProductionExcelParser,
)

ROOT = Path(__file__).resolve().parents[2]
FILE_2023 = ROOT / "2023年产量与预算达成率分析.xlsx"
FILE_2024 = ROOT / "经营数据汇总表2024年.xlsx"
FILE_2025 = ROOT / "组件事业部月度产销存-2025年.xlsx"
FILE_2026 = ROOT / "组件事业部月度产销存-2026.04.xlsx"


@pytest.fixture(scope="module", autouse=True)
def _require_excel_files() -> None:
    """确认业务提供的产销存 Excel 已放在项目根目录。

    说明：
        这些 Excel 是用户本轮提供的业务附件，不提交到仓库；
        测试运行前必须真实存在，避免用假数据替代业务文件。
    """
    missing = [path.name for path in [FILE_2023, FILE_2024, FILE_2025, FILE_2026] if not path.exists()]
    if missing:
        pytest.fail(f"缺少产销存业务 Excel 文件，无法执行 M2 入库验收：{missing}")


@pytest.fixture()
def db_session():
    """创建 SQLite 临时库会话。

    返回：
        SQLAlchemy Session。只创建 ORM 表，不连接真实 MySQL。
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_parse_2023_uses_monthly_columns_and_ignores_broken_annual_column() -> None:
    """2023 必须导入 1-12 月月度事实，不能把漏 12 月的年度列当事实。"""
    parsed = InventorySalesProductionExcelParser().parse_file(FILE_2023)

    assert parsed.business_year == 2023
    assert parsed.data_cutoff_month == 12
    assert parsed.sheet_count == 1
    assert parsed.monthly_fact_count == 295
    assert all(fact.business_month in range(1, 13) for fact in parsed.monthly_facts)
    assert all(fact.source_col_index >= 9 for fact in parsed.monthly_facts)
    assert not any(fact.period_label == "23年" for fact in parsed.monthly_facts)

    december_budget = next(
        fact
        for fact in parsed.monthly_facts
        if fact.metric_code == "production_budget" and fact.raw_item == "年度预算" and fact.business_month == 12
    )
    assert december_budget.value_decimal == Decimal("1805.22")
    assert any("2023 年度列漏 12 月" in flag for flag in parsed.quality_flags)


def test_parse_2026_only_published_months_and_normalizes_inventory_consignment() -> None:
    """2026 文件只发布到 4 月，库存/存货和寄存仓必须归一为标准时点指标。"""
    parsed = InventorySalesProductionExcelParser().parse_file(FILE_2026)

    assert parsed.business_year == 2026
    assert parsed.data_cutoff_month == 4
    assert parsed.monthly_fact_count == 158
    assert {fact.business_month for fact in parsed.monthly_facts} == {1, 2, 3, 4}
    assert not any(fact.business_month >= 5 for fact in parsed.monthly_facts)

    april_inventory = next(
        fact
        for fact in parsed.monthly_facts
        if fact.metric_code == "ending_inventory_volume" and fact.raw_item == "存货合计" and fact.business_month == 4
    )
    assert april_inventory.aggregation_type == "period_end"
    assert april_inventory.metric_name == "期末库存/存货"
    assert april_inventory.value_decimal == Decimal("374.23911")

    april_consigned = next(
        fact
        for fact in parsed.monthly_facts
        if fact.metric_code == "consigned_inventory_volume" and fact.raw_item == "寄存仓" and fact.business_month == 4
    )
    assert april_consigned.aggregation_type == "period_end"
    assert april_consigned.metric_name == "寄存库存"
    assert april_consigned.is_consigned is True
    assert april_consigned.value_decimal == Decimal("40.978995")


def test_parse_2024_keeps_external_sales_scope_as_default_outbound_sales_source() -> None:
    """2024 对外销量默认口径应保留“组件事业部剔除内部交易”。"""
    parsed = InventorySalesProductionExcelParser().parse_file(FILE_2024)

    assert parsed.business_year == 2024
    assert parsed.data_cutoff_month == 12
    assert parsed.sheet_count == 2
    assert parsed.monthly_fact_count == 457

    december_external_sales = next(
        fact
        for fact in parsed.monthly_facts
        if fact.metric_code == "shipment_external_excluding_internal" and fact.business_month == 12
    )
    assert december_external_sales.metric_name == "对外销量（剔除内部交易）"
    assert december_external_sales.trade_scope == "剔除内部交易"
    assert december_external_sales.is_default_external_sales is True
    assert december_external_sales.value_decimal == Decimal("385.332353")


def test_import_persists_workbook_and_monthly_facts_idempotently(db_session) -> None:
    """导入服务应落库工作簿和 DWD 月度事实，同 hash 重复导入不能重复写入。"""
    service = InventorySalesProductionExcelImportService(
        repository=InventorySalesProductionRepository(db_session),
        parser=InventorySalesProductionExcelParser(),
    )

    first = service.import_file(FILE_2025)
    second = service.import_file(FILE_2025)

    assert first.import_status == "created"
    assert second.import_status == "existing"
    assert first.workbook_id == second.workbook_id
    assert first.monthly_fact_count == 503
    assert db_session.query(BaIspExcelWorkbook).count() == 1
    assert db_session.query(BaIspMonthlyFact).count() == 503

    december_total_shipment = (
        db_session.query(BaIspMonthlyFact)
        .filter(
            BaIspMonthlyFact.metric_code == "shipment_volume",
            BaIspMonthlyFact.raw_item == "发货合计",
            BaIspMonthlyFact.business_month == 12,
        )
        .one()
    )
    assert december_total_shipment.value_decimal == Decimal("1966.778875")
    assert december_total_shipment.period_start_date.isoformat() == "2025-12-01"
    assert december_total_shipment.period_end_date.isoformat() == "2025-12-31"


def test_business_analysis_models_are_registered_in_project_metadata() -> None:
    """经营分析产销存表必须注册到 Base.metadata，供 Alembic 和测试建表使用。"""
    expected_tables = {
        "ods_ba_isp_excel_workbook",
        "ods_ba_isp_excel_sheet",
        "dwd_ba_isp_monthly_fact",
        "dim_ba_isp_metric",
        "dim_ba_isp_metric_alias",
    }
    assert expected_tables.issubset(set(Base.metadata.tables.keys()))
