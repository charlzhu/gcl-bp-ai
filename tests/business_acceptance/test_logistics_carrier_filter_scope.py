"""物流承运商过滤口径回归测试。

本文件覆盖“用户显式点名承运商时不能退回全承运商汇总”的问题：
1. Planner 必须把已校验承运商简称下推到 filters.carrier_name；
2. 服务层在该承运商无数据时应返回空结果提示，而不是返回所有承运商的区域汇总。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.domains.logistics.repositories.data_qa_repository import LogisticsDataQaRepository
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService


class _CarrierAwareFakeRepository:
    """只模拟本用例需要的历史区域发运量查询。

    说明：
        1. 如果服务层没有传入 carrier_name，就返回一条“全承运商汇总”假数据，用于暴露误回退问题；
        2. 如果服务层传入了 carrier_name，则模拟该承运商无记录，返回空列表；
        3. 这样测试不依赖本地数据库数据，也能验证过滤条件是否真实下推。
    """

    def __init__(self) -> None:
        self.observed_carrier_name: str | None = None

    def hist_mw_by_all_regions(
        self,
        *,
        year: int,
        carrier_name: str | None = None,
        regions: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """记录服务层传入的过滤条件并返回受控假数据。

        参数：
            year: 查询年份。
            carrier_name: 服务层下推的承运商过滤条件。
            regions: 服务层下推的区域过滤条件。
        返回：
            当 carrier_name 缺失时返回假汇总行；当 carrier_name 存在时返回空结果。
        """

        self.observed_carrier_name = carrier_name
        if carrier_name:
            return []
        return [{"region_name": "西北", "shipment_mw": 4942.238}]


class _YearlyCarrierFakeRepository:
    """只模拟本用例需要的历史承运商逐年发运量查询。

    说明：
        1. 如果服务层没有传入 carrier_name，就返回一条“全承运商汇总”假数据，用于暴露过滤丢失问题；
        2. 如果服务层传入了 carrier_name，则返回 2023/2024/2025 三个请求年份，其中 2024 模拟无匹配记录；
        3. 这样既能验证年份范围完整下推，也能验证显式承运商不会被服务层丢弃。
    """

    def __init__(self) -> None:
        self.observed_years: list[int] | None = None
        self.observed_carrier_name: str | None = None

    def hist_mw_by_year(self, *, years: list[int], carrier_name: str | None = None) -> dict[str, Any]:
        """记录服务层传入的逐年查询过滤条件并返回受控假数据。

        参数：
            years: 服务层下推的业务年份列表。
            carrier_name: 服务层下推的承运商过滤条件。
        返回：
            包含 items 与 missing_years 的逐年发运量结果。
        """

        self.observed_years = years
        self.observed_carrier_name = carrier_name
        if not carrier_name:
            return {
                "items": [{"biz_year": 2023, "shipment_mw": 9999.0, "row_count": 99}],
                "missing_years": [],
            }
        return {
            "items": [
                {"biz_year": 2023, "shipment_mw": 10.5, "row_count": 2},
                {"biz_year": 2024, "shipment_mw": None, "row_count": 0},
                {"biz_year": 2025, "shipment_mw": 3.0, "row_count": 1},
            ],
            "missing_years": [2024],
        }


class _FakeDb:
    """占位数据库对象。

    说明：
        当前测试直接调用 _execute_plan，不写查询历史，不需要真实数据库连接。
    """


QUESTION = "24 年 京东物流 在各区域的承运量分别是多少"
YEARLY_CARRIER_QUESTION = "23年-25年，苏州晶茂物流 每年发运量分别是多少"


def test_planner_keeps_explicit_jd_carrier_filter_for_region_mw_breakdown() -> None:
    """验证点名“京东物流”时，区域发运量查询必须保留承运商过滤。"""

    plan = LogisticsDataQaPlanner().build_plan(QUESTION)

    assert plan.query_key == "hist_mw_by_all_regions"
    assert plan.filters["year"] == 2024
    assert plan.filters["carrier_name"] == "京东"
    assert plan.dimensions == ["region_name"]
    assert plan.group_by == ["region_name"]


def test_planner_does_not_treat_generic_history_logistics_as_carrier() -> None:
    """验证“历史物流”等泛词不会被误抽成承运商。"""

    plan = LogisticsDataQaPlanner().build_plan("2024年历史物流在各区域的发运量分别是多少")

    assert plan.query_key == "hist_mw_by_all_regions"
    assert plan.filters["year"] == 2024
    assert "carrier_name" not in plan.filters


def test_planner_keeps_year_range_and_explicit_carrier_for_yearly_mw_breakdown() -> None:
    """验证点名承运商并要求“每年”时，必须按年份拆分且保留承运商过滤。"""

    plan = LogisticsDataQaPlanner().build_plan(YEARLY_CARRIER_QUESTION)

    assert plan.query_key == "hist_mw_by_year"
    assert plan.filters["years"] == [2023, 2024, 2025]
    assert plan.filters["carrier_name"] == "晶茂"
    assert plan.dimensions == ["biz_year"]
    assert plan.group_by == ["biz_year"]
    assert plan.sort == [{"field": "biz_year", "direction": "asc"}]


def test_service_keeps_year_range_and_carrier_when_executing_yearly_mw_breakdown() -> None:
    """验证服务层执行逐年发运量时，不丢失 2023-2025 年份范围和显式承运商。"""

    planner = LogisticsDataQaPlanner()
    fake_repository = _YearlyCarrierFakeRepository()
    service = LogisticsDataQaService(db=_FakeDb(), repository=fake_repository, planner=planner)  # type: ignore[arg-type]

    plan = planner.build_plan(YEARLY_CARRIER_QUESTION)
    result = service._execute_plan(YEARLY_CARRIER_QUESTION, plan)  # noqa: SLF001 - 回归测试直接验证受控执行分支

    assert fake_repository.observed_years == [2023, 2024, 2025]
    assert fake_repository.observed_carrier_name == "晶茂"
    assert result.result_table.columns == ["biz_year", "shipment_mw", "row_count"]
    assert [row["biz_year"] for row in result.result_table.rows] == [2023, 2024, 2025]
    assert result.result_table.rows[1]["shipment_mw"] is None
    assert result.result_table.rows[1]["row_count"] == 0
    assert "晶茂" in result.answer_summary
    assert "2023-2025" in result.answer_summary
    assert any("2024年" in warning and "无匹配记录" in warning for warning in result.warnings)


def test_repository_yearly_mw_filters_named_carrier_and_keeps_missing_year() -> None:
    """验证仓储层按承运商逐年统计时，不把其他承运商数据混入结果。"""

    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as db:
        db.execute(
            text(
                """
                CREATE TABLE dwd_logistics_hist_shipment_detail (
                    biz_year INTEGER,
                    actual_watt NUMERIC,
                    logistics_company_name TEXT
                )
                """
            )
        )
        db.execute(
            text(
                """
                INSERT INTO dwd_logistics_hist_shipment_detail
                    (biz_year, actual_watt, logistics_company_name)
                VALUES
                    (2023, 10500000, '苏州晶茂物流有限公司'),
                    (2023, 100000000, '其他物流'),
                    (2024, 999000000, '其他物流'),
                    (2025, 3000000, '晶茂运输')
                """
            )
        )
        db.commit()

        # 这里仅验证本方法的 SQL 过滤逻辑，跳过仓储初始化时面向 MySQL 的运行列自检。
        repository = object.__new__(LogisticsDataQaRepository)
        repository.db = db
        data = repository.hist_mw_by_year(years=[2023, 2024, 2025], carrier_name="晶茂")

    rows_by_year = {row["biz_year"]: row for row in data["items"]}
    assert list(rows_by_year) == [2023, 2024, 2025]
    assert rows_by_year[2023]["shipment_mw"] == 10.5
    assert rows_by_year[2023]["row_count"] == 1
    assert rows_by_year[2024]["shipment_mw"] is None
    assert rows_by_year[2024]["row_count"] == 0
    assert rows_by_year[2025]["shipment_mw"] == 3.0
    assert data["missing_years"] == [2024]


def test_service_does_not_fallback_to_all_carriers_when_jd_has_no_rows() -> None:
    """验证承运商无记录时返回空结果提示，不能返回全承运商区域汇总。"""

    planner = LogisticsDataQaPlanner()
    fake_repository = _CarrierAwareFakeRepository()
    service = LogisticsDataQaService(db=_FakeDb(), repository=fake_repository, planner=planner)  # type: ignore[arg-type]

    plan = planner.build_plan(QUESTION)
    result = service._execute_plan(QUESTION, plan)  # noqa: SLF001 - 回归测试直接验证受控执行分支
    status = service._resolve_status(result)  # noqa: SLF001 - 验证空结果状态文案与业务摘要保持一致

    assert fake_repository.observed_carrier_name == "京东"
    assert result.result_table.rows == []
    assert "京东" in result.answer_summary
    assert "未找到" in result.answer_summary or "未查到" in result.answer_summary
    assert "未返回全承运商汇总" in result.answer_summary
    assert result.warnings == ["未在历史物流台账中找到承运商“京东”匹配记录。"]
    assert status.code == "EMPTY_RESULT"
    assert status.severity == "warning"
