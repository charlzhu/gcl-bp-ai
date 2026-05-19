from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.domains.business_analysis.models import BaIspExcelWorkbook, BaIspMetric, BaIspMonthlyFact
from backend.app.domains.business_analysis.repositories.inventory_sales_production_repository import METRIC_CATALOG
from backend.app.domains.business_analysis.services.inventory_sales_production.qa_service import (
    InventorySalesProductionQaService,
)


FORBIDDEN_VISIBLE_WORDS = ("SQL", "query_key", "planner", "guardrail", "schema", "raw", "debug", "LLM", "ba_isp", "metric_code")


@pytest.fixture()
def db_session():
    """创建 M4-6 真实问法回归用的临时中间库。

    说明：
        1. 本测试只模拟智能助手中间库，不直接读取 Excel 或外部系统；
        2. 数据值来自 M2/M3 已确认的业务口径样例，保证问法回归可重复执行；
        3. 每个用例都走 QA Service -> NL Planner -> QueryExecutor，避免绕过真实问答主链路。
    返回：
        SQLAlchemy Session，测试结束后自动释放。
    """

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        _seed_metric_catalog(session)
        _seed_acceptance_facts(session)
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _seed_metric_catalog(session) -> None:
    """初始化产销存指标白名单。

    参数：
        session: 当前测试数据库会话。
    返回：
        无返回值。
    """

    for metric in METRIC_CATALOG:
        session.merge(BaIspMetric(**metric))
    session.commit()


def _seed_workbook(session, *, year: int, cutoff_month: int) -> BaIspExcelWorkbook:
    """写入一个业务年份工作簿版本。

    参数：
        session: 当前测试数据库会话。
        year: 业务年份。
        cutoff_month: 数据发布截止月份。
    返回：
        已 flush 的工作簿 ORM 对象。
    """

    workbook = BaIspExcelWorkbook(
        source_file_name=f"M4-6产销存验收-{year}.xlsx",
        source_file_sha256=f"m4-6-sha256-{year}-{cutoff_month}",
        source_file_size=2048,
        business_year=year,
        data_cutoff_month=cutoff_month,
        source_version_label=f"{year}.{cutoff_month:02d}",
        upload_batch_no=f"M4-6-ACCEPTANCE-{year}-{cutoff_month}",
        sheet_count=1,
        has_vba=0,
        external_link_count=0,
        parser_version="m4_6_acceptance",
        quality_status="success",
    )
    session.add(workbook)
    session.flush()
    return workbook


def _source_offset(*values: str | None) -> int:
    """根据维度组合生成稳定来源行号偏移。

    参数：
        values: 参与区分来源坐标的维度文本。
    返回：
        小范围整数偏移，避免同月同指标测试数据撞唯一来源坐标。
    """

    return sum(ord(char) for value in values if value for char in value) % 1000


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
    is_consigned: int = 0,
) -> None:
    """写入一条产销存标准月度事实。

    参数：
        session: 当前测试数据库会话。
        workbook: 来源工作簿版本。
        month: 业务月份。
        metric_code/metric_name/metric_category/aggregation_type: 标准指标信息。
        value: 业务数值，统一按 MW 或百分比分子分母事实保存。
        base_name/model_type/trade_scope: 可选业务维度。
        is_default_external_sales/is_consigned: 业务口径标记。
    返回：
        无返回值。
    """

    row_no = 1000 + month + _source_offset(metric_code, base_name, model_type, trade_scope)
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
            is_consigned=is_consigned,
            is_default_external_sales=is_default_external_sales,
            source_file_name=workbook.source_file_name,
            source_file_sha256=workbook.source_file_sha256,
            source_sheet="M4-6真实问法验收",
            source_row_index=row_no,
            source_col_index=month + 20,
            source_cell_ref=f"B{row_no}",
            raw_category=metric_category,
            raw_item=metric_name,
            raw_unit="MW",
            parser_version="m4_6_acceptance",
            quality_flags="{}",
        )
    )


def _seed_acceptance_facts(session) -> None:
    """写入覆盖 A/B/C 边界的产销存验收事实。

    业务逻辑：
        1. 2024 销量默认采用“剔除内部交易”的对外销量口径；
        2. 2026 只发布到 4 月，全年/累计问法只能使用 1-4 月；
        3. 库存/寄存是时点指标，按最后已发布月份取数；
        4. 版型、基地拆分只使用白名单维度和标准指标。
    返回：
        无返回值。
    """

    workbook_2023 = _seed_workbook(session, year=2023, cutoff_month=12)
    workbook_2024 = _seed_workbook(session, year=2024, cutoff_month=12)
    workbook_2025 = _seed_workbook(session, year=2025, cutoff_month=12)
    workbook_2026 = _seed_workbook(session, year=2026, cutoff_month=4)

    for month, actual, budget in [(1, "80", "100"), (2, "120", "100")]:
        _add_fact(
            session,
            workbook=workbook_2023,
            month=month,
            metric_code="production_actual_including_oem",
            metric_name="实际产量（含委外）",
            metric_category="production",
            aggregation_type="flow_sum",
            value=actual,
        )
        _add_fact(
            session,
            workbook=workbook_2023,
            month=month,
            metric_code="production_budget",
            metric_name="产量预算/目标",
            metric_category="budget",
            aggregation_type="flow_sum",
            value=budget,
        )

    _add_fact(
        session,
        workbook=workbook_2024,
        month=12,
        metric_code="shipment_external_excluding_internal",
        metric_name="对外销量（剔除内部交易）",
        metric_category="shipment",
        aggregation_type="flow_sum",
        value="385.332353",
        trade_scope="剔除内部交易",
        is_default_external_sales=1,
    )

    for month, value in [(1, "10"), (2, "20"), (3, "30")]:
        _add_fact(
            session,
            workbook=workbook_2025,
            month=month,
            metric_code="shipment_volume",
            metric_name="发货量/销量",
            metric_category="shipment",
            aggregation_type="flow_sum",
            value=value,
        )
    _add_fact(
        session,
        workbook=workbook_2025,
        month=12,
        metric_code="invoice_sales_volume",
        metric_name="开票销量",
        metric_category="shipment",
        aggregation_type="flow_sum",
        value="55",
    )
    for model_type, value in [("N型", "150"), ("P型", "80")]:
        _add_fact(
            session,
            workbook=workbook_2025,
            month=12,
            metric_code="production_by_model_type",
            metric_name="版型产量",
            metric_category="production",
            aggregation_type="flow_sum",
            value=value,
            model_type=model_type,
        )
    for base_name, value in [("合肥", "260"), ("阜宁", "140")]:
        _add_fact(
            session,
            workbook=workbook_2025,
            month=12,
            metric_code="ending_inventory_by_base",
            metric_name="基地期末库存/存货",
            metric_category="inventory",
            aggregation_type="period_end",
            value=value,
            base_name=base_name,
        )

    for month, value in [(1, "10"), (2, "20"), (3, "30"), (4, "40")]:
        _add_fact(
            session,
            workbook=workbook_2026,
            month=month,
            metric_code="shipment_volume",
            metric_name="发货量/销量",
            metric_category="shipment",
            aggregation_type="flow_sum",
            value=value,
        )
    _add_fact(
        session,
        workbook=workbook_2026,
        month=4,
        metric_code="ending_inventory_volume",
        metric_name="期末库存/存货",
        metric_category="inventory",
        aggregation_type="period_end",
        value="374.23911",
    )
    _add_fact(
        session,
        workbook=workbook_2026,
        month=4,
        metric_code="consigned_inventory_volume",
        metric_name="寄存库存",
        metric_category="consignment",
        aggregation_type="period_end",
        value="40.978995",
        is_consigned=1,
    )
    session.commit()


def _ask(session, question: str):
    """调用产销存 QA 服务执行真实问法。

    参数：
        session: 当前测试数据库会话。
        question: 真实业务问法。
    返回：
        InventorySalesProductionQaResponse。
    """

    return InventorySalesProductionQaService(session).ask(question, trace_id="trace-m4-6")


def _assert_no_user_visible_technical_leak(payload: Any) -> None:
    """校验用户可见结果不包含内部技术实现词。

    参数：
        payload: 字符串、列表或字典形式的用户可见内容。
    返回：
        无返回值；发现泄露时断言失败。
    """

    text = str(payload)
    for word in FORBIDDEN_VISIBLE_WORDS:
        assert word.lower() not in text.lower()


@pytest.mark.parametrize(
    ("question", "expected_value", "expected_phrases"),
    [
        ("2024年销量是多少？", "385.33235300", ["剔除内部交易"]),
        ("2025年Q1销量是多少？", "60.00000000", ["2025-Q1", "1月,2月,3月"]),
        ("2025年一季度销售量是多少？", "60.00000000", ["2025-Q1", "1月,2月,3月"]),
        ("2026年截至4月累计销量是多少？", "100.00000000", ["1月,2月,3月,4月"]),
        ("2026年截止4月累计销量是多少？", "100.00000000", ["1月,2月,3月,4月"]),
        ("2026年累计到4月销量是多少？", "100.00000000", ["1月,2月,3月,4月"]),
        ("2026年前4个月发货量多少？", "100.00000000", ["1月,2月,3月,4月"]),
        ("2026年4月存货合计是多少？", "374.23911000", ["最后已发布月份", "4月"]),
        ("2026年4月寄存仓还有多少？", "40.97899500", ["最后已发布月份", "4月"]),
        ("2023年预算达成率是多少？", "100.00000000", ["预算达成率"]),
        ("2025年开票销量是多少？", "55.00000000", ["开票销量"]),
    ],
)
def test_m4_6_real_question_success_samples_are_stable(db_session, question: str, expected_value: str, expected_phrases: list[str]) -> None:
    """真实问法 A 类样例必须稳定返回业务结果。

    参数：
        db_session: 已写入验收事实的临时中间库。
        question: 业务用户自然语言问法。
        expected_value: 期望核心数值。
        expected_phrases: 期望出现在回答、表格或口径提醒中的业务短语。
    返回：
        无返回值。
    """

    result = _ask(db_session, question)

    assert result.status["code"] == "OK"
    assert result.result_table is not None
    visible_payload = {
        "answer": result.answer_summary,
        "presentation": result.presentation,
        "warnings": result.warnings,
        "table": result.result_table,
    }
    assert expected_value in str(visible_payload)
    for phrase in expected_phrases:
        assert phrase in str(visible_payload)
    _assert_no_user_visible_technical_leak(visible_payload)


def test_m4_6_real_question_model_type_breakdown_uses_standard_model_metric(db_session) -> None:
    """按版型拆分产量时必须使用标准版型指标，不能误查无版型维度的总产量。"""

    result = _ask(db_session, "2025年各版型产量排名")

    assert result.status["code"] == "OK"
    assert result.result_table is not None
    rows = result.result_table["rows"]
    assert [(row["版型"], row["数值"]) for row in rows] == [("N型", "150.00000000"), ("P型", "80.00000000")]
    _assert_no_user_visible_technical_leak(result.result_table)


def test_m4_6_real_question_inventory_breakdown_by_base_uses_period_end(db_session) -> None:
    """按基地看库存时必须走基地库存时点指标，并按最后已发布月份取数。"""

    result = _ask(db_session, "2025年按基地看库存情况")

    assert result.status["code"] == "OK"
    assert result.result_table is not None
    rows = result.result_table["rows"]
    assert [(row["基地"], row["数值"]) for row in rows] == [("合肥", "260.00000000"), ("阜宁", "140.00000000")]
    assert any("最后已发布月份" in warning for warning in result.warnings)
    _assert_no_user_visible_technical_leak({"warnings": result.warnings, "table": result.result_table})


@pytest.mark.parametrize(
    ("question", "expected_status", "expected_phrase"),
    [
        ("2025年销量同比增长率是多少？", "UNSUPPORTED", "同比"),
        ("2025年销量环比趋势如何？", "UNSUPPORTED", "环比"),
        ("2026年2月至4月销量是多少？", "UNSUPPORTED", "月份区间"),
        ("2026年4月至6月销量是多少？", "UNSUPPORTED", "月份区间"),
        ("2025年库存周转率是多少？", "CLARIFICATION_REQUIRED", "库存周转率"),
        ("2027年销量是多少？", "CLARIFICATION_REQUIRED", "尚未导入"),
    ],
)
def test_m4_6_real_question_boundary_samples_fail_closed(db_session, question: str, expected_status: str, expected_phrase: str) -> None:
    """真实问法 B/C 类边界必须业务化阻断，不能编造或误答。"""

    result = _ask(db_session, question)

    assert result.status["code"] == expected_status
    assert result.result_table is None
    assert expected_phrase in result.answer_summary or expected_phrase in result.status["message"]
    _assert_no_user_visible_technical_leak({"answer": result.answer_summary, "presentation": result.presentation})
