from __future__ import annotations

from typing import Any

from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService


class _FakeRepository:
    """只暴露本测试所需仓储方法，验证服务层不会在空结果时回退全量汇总。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def hist_mw_by_all_regions(
        self,
        *,
        year: int,
        carrier_name: str | None = None,
        regions: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """记录查询过滤条件并模拟当前库无该承运商数据。"""
        self.calls.append({"year": year, "carrier_name": carrier_name, "regions": regions})
        return []


def test_historical_carrier_uses_candidate_provider_not_planner_name_whitelist() -> None:
    """历史承运商应来自注入候选源，而不是 planner 代码内的少量姓名白名单。"""

    planner = LogisticsDataQaPlanner(
        historical_carrier_candidate_provider=lambda: ["英赋嘉", "苏州晶茂物流有限公司", "德邦物流"]
    )

    yingfujia_plan = planner.build_plan("2023年英赋嘉发运多少量?")
    assert yingfujia_plan.query_key == "hist_mw_summary"
    assert yingfujia_plan.filters["carrier_name"] == "英赋嘉"

    debang_plan = planner.build_plan("2024年德邦物流在各区域的承运量分别是多少？")
    assert debang_plan.query_key == "hist_mw_by_all_regions"
    assert debang_plan.filters["carrier_name"] == "德邦"

    jingmao_plan = planner.build_plan("2024年晶茂在华东、华北分别发运量是多少？")
    assert jingmao_plan.filters["carrier_name"] == "晶茂"

    origin_fee_plan = planner.build_plan("2024年合肥始发德邦物流总运费是多少")
    assert origin_fee_plan.query_key == "hist_total_fee_by_origin_and_carrier"
    assert origin_fee_plan.filters["carrier_name"] == "德邦"

    origin_mw_plan = planner.build_plan("2024年合肥始发德邦物流发运量是多少")
    assert origin_mw_plan.query_key == "hist_mw_by_origin_and_carrier"
    assert origin_mw_plan.filters["carrier_name"] == "德邦"


def test_unknown_explicit_logistics_carrier_is_extracted_by_safe_grammar() -> None:
    """点名“京东物流”这类明确承运商短语时，即便候选源暂无记录，也要保留下推过滤。"""

    planner = LogisticsDataQaPlanner()

    plan = planner.build_plan("24 年 京东物流 在各区域的承运量分别是多少")

    assert plan.query_key == "hist_mw_by_all_regions"
    assert plan.filters["year"] == 2024
    assert plan.filters["carrier_name"] == "京东"


def test_generic_logistics_terms_are_not_misread_as_carrier() -> None:
    """泛词“物流发运/历史物流”不是承运商，不能因为包含“物流”就生成 carrier_name。"""

    planner = LogisticsDataQaPlanner(historical_carrier_candidate_provider=lambda: ["德邦物流"])

    total_plan = planner.build_plan("2023年物流发运合计多少量?")
    assert total_plan.query_key == "hist_mw_summary"
    assert "carrier_name" not in total_plan.filters

    region_plan = planner.build_plan("2024年历史物流在各区域的承运量分别是多少？")
    assert region_plan.query_key == "hist_mw_by_all_regions"
    assert "carrier_name" not in region_plan.filters


def test_empty_named_carrier_region_result_does_not_fallback_to_all_carriers() -> None:
    """指定承运商为空结果时，答案必须提示未找到该承运商，而不是返回全承运商口径。"""

    repository = _FakeRepository()
    planner = LogisticsDataQaPlanner()
    service = LogisticsDataQaService(db=None, repository=repository, planner=planner)  # type: ignore[arg-type]
    plan = planner.build_plan("24 年 京东物流 在各区域的承运量分别是多少")

    result = service._execute_plan("24 年 京东物流 在各区域的承运量分别是多少", plan)
    status = service._resolve_status(result)

    assert repository.calls == [{"year": 2024, "carrier_name": "京东", "regions": None}]
    assert result.result_table.rows == []
    assert status.code == "EMPTY_RESULT"
    assert "未找到承运商“京东”" in result.answer_summary
    assert "未返回全承运商汇总" in result.answer_summary
