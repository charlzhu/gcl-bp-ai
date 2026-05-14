"""物流问答“当地/本地物流公司”承运商归属口径回归测试。

本文件锁定“苏州的物流公司/苏州市当地物流公司”不能再被解释为目的城市=苏州，
而应按承运商公司名称或后续注册地可判定为苏州的物流公司统计。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.domains.logistics.repositories.data_qa_repository import LogisticsDataQaRepository
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.schemas.llm_understanding import LogisticsLlmGuardrailDecision
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.domains.logistics.services.llm_answer_presentation_service import LogisticsLlmAnswerPresentationService


class _FakeDb:
    """测试用空数据库会话，只承接查询日志链路的提交/回滚调用。"""

    def commit(self) -> None:
        """提交测试事务；本用例不需要真实落库。"""

    def rollback(self) -> None:
        """回滚测试事务；本用例不需要真实落库。"""


class _FakeQueryLogRepository:
    """测试用查询日志仓库，避免 service 回归依赖真实 sys_query_log。"""

    def write_query_log(self, db: Any, payload: Any) -> int:  # noqa: ANN401, ARG002
        """返回固定日志 ID，证明主查询链路已执行到日志写入。"""
        return 1


class _NoopGuardrailService:
    """测试用 Guardrail，保持规则 planner 结果不被 LLM 候选改写。"""

    def evaluate(
        self,
        *,
        question: str,
        rule_plan: Any,
        trace_id: str | None = None,
        write_audit: bool = False,
    ) -> LogisticsLlmGuardrailDecision:  # noqa: ARG002
        """构造 off 状态决策，让 service 使用规则计划继续执行。"""
        return LogisticsLlmGuardrailDecision(
            question=question,
            rule_intent=rule_plan.intent,
            rule_query_key=rule_plan.query_key,
            rule_needs_clarification=rule_plan.needs_clarification,
            rule_supported=rule_plan.intent not in {"clarification", "unsupported"},
            final_intent=rule_plan.intent,
            final_query_key=rule_plan.query_key,
            final_needs_clarification=rule_plan.needs_clarification,
            final_supported=rule_plan.intent not in {"clarification", "unsupported"},
        )

    def write_audit_log(self, *, trace_id: str | None, decision: Any) -> None:  # noqa: ARG002, ANN401
        """测试场景不写 Guardrail 审计日志。"""


def test_planner_extracts_local_carrier_city_instead_of_destination_city() -> None:
    """验证“苏州的物流公司/当地物流公司”生成承运商归属城市过滤，而不是目的城市过滤。

    参数：无。
    返回值：无；通过断言验证 query_key 与 filters。
    业务逻辑：“苏州的物流公司”在承运商 KPI 题中指苏州本地承运商，不能统计所有发往苏州的非苏州承运商。
    """

    planner = LogisticsDataQaPlanner()
    cases = [
        "25年苏州的物流公司发货量分别是多少",
        "25年苏州市当地物流公司发运量分别是多少",
        "25年苏州本地的物流公司发货量分别是多少",
    ]

    for question in cases:
        plan = planner.build_plan(question)

        assert plan.query_key == "hist_carrier_kpi_by_year", question
        assert not plan.needs_clarification, question
        assert plan.filters["year"] == 2025, question
        assert plan.filters["carrier_local_city"] == "苏州", question
        assert plan.filters.get("city") is None, question
        assert plan.dimensions == ["carrier_name"], question


def test_planner_keeps_explicit_destination_city_for_carrier_breakdown() -> None:
    """验证“发往苏州的各物流公司”仍保留目的城市过滤。

    参数：无。
    返回值：无；通过断言验证显式目的地问法不会被误改成本地承运商归属口径。
    业务逻辑：只有“苏州的物流公司/苏州本地物流公司”才按承运商归属过滤；“发往苏州”仍按目的城市过滤。
    """

    plan = LogisticsDataQaPlanner().build_plan("25年发往苏州的各物流公司发货量分别是多少")

    assert plan.query_key == "hist_carrier_kpi_by_year"
    assert plan.filters["year"] == 2025
    assert plan.filters["city"] == "苏州"
    assert "carrier_local_city" not in plan.filters


def test_repository_filters_local_carriers_by_carrier_name_not_destination_city() -> None:
    """验证仓储层按承运商名称识别苏州本地物流公司，排除发往苏州的非苏州公司。

    参数：无。
    返回值：无；通过 SQLite 明细数据断言汇总结果。
    业务逻辑：当前源表没有承运商注册地字段，因此“当地物流公司”先按物流公司名称包含城市关键词识别。
    """

    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as db:
        db.execute(
            text(
                """
                CREATE TABLE dwd_logistics_hist_shipment_detail (
                    biz_year INTEGER,
                    region_name TEXT,
                    city TEXT,
                    logistics_company_name TEXT,
                    actual_watt REAL,
                    total_fee REAL
                )
                """
            )
        )
        db.execute(
            text(
                """
                INSERT INTO dwd_logistics_hist_shipment_detail
                    (biz_year, region_name, city, logistics_company_name, actual_watt, total_fee)
                VALUES
                    (2025, '华东', '苏州', '宿迁市昆仑物流有限公司', 15235025, 106800),
                    (2025, '华东', '苏州', '苏州晶茂物流有限公司', 7300000, 38453),
                    (2025, '华东', '湖州', '苏州威洋供应链有限公司', 5900000, 40886),
                    (2025, '华东', '苏州', '常州安提物流有限公司', 509760, 3390),
                    (2024, '华东', '苏州', '苏州晶茂物流有限公司', 1000000, 1000)
                """
            )
        )
        db.commit()

        # 只测试 hist_carrier_kpi_by_year 的 SQL 口径；跳过仓储初始化里的 MySQL 运行期列补齐，
        # 避免 SQLite 单测被 information_schema 兼容性噪声干扰。
        repository = LogisticsDataQaRepository.__new__(LogisticsDataQaRepository)
        repository.db = db
        result = repository.hist_carrier_kpi_by_year(
            year=2025,
            carrier_local_city="苏州",
        )

    carrier_names = [item["carrier_name"] for item in result["items"]]
    assert carrier_names == ["苏州晶茂物流有限公司", "苏州威洋供应链有限公司"]
    assert result["total_shipment_mw"] == 13.2
    assert all("苏州" in name for name in carrier_names)
    assert "宿迁市昆仑物流有限公司" not in carrier_names
    assert "常州安提物流有限公司" not in carrier_names


def test_service_passes_local_carrier_scope_and_explains_business_rule() -> None:
    """验证 service 将本地承运商城市传给仓储层，并在答案口径中说明识别规则。

    参数：无。
    返回值：无；通过断言验证仓储调用参数、结果表和口径说明。
    业务逻辑：前端展示必须让用户看到这是“苏州本地物流公司”口径，而不是“苏州城市目的地”口径。
    """

    class _FakeLogisticsRepository:
        """测试用物流仓储，记录承运商 KPI 查询参数并返回固定苏州本地承运商。"""

        def __init__(self) -> None:
            self.kwargs: dict[str, Any] | None = None

        def hist_carrier_kpi_by_year(self, **kwargs: Any) -> dict[str, Any]:
            """返回仅包含苏州本地物流公司的固定结果。"""
            self.kwargs = kwargs
            return {
                "total_shipment_mw": 13.2,
                "items": [
                    {
                        "carrier_name": "苏州晶茂物流有限公司",
                        "shipment_mw": 7.3,
                        "shipment_share_pct": 55.3,
                        "total_fee": 38453,
                    },
                    {
                        "carrier_name": "苏州威洋供应链有限公司",
                        "shipment_mw": 5.9,
                        "shipment_share_pct": 44.7,
                        "total_fee": 40886,
                    },
                ],
            }

    repository = _FakeLogisticsRepository()
    service = LogisticsDataQaService(
        db=_FakeDb(),
        repository=repository,
        query_log_repository=_FakeQueryLogRepository(),
        guardrail_service=_NoopGuardrailService(),
        answer_presentation_service=LogisticsLlmAnswerPresentationService(enabled=False),
    )

    result = service.query(
        LogisticsDataQaQueryRequest(question="25年苏州的物流公司发货量分别是多少"),
        trace_id="local-carrier-scope",
    )

    assert repository.kwargs == {
        "year": 2025,
        "region_name": None,
        "carrier_local_city": "苏州",
    }
    assert not result.needs_clarification
    assert "苏州本地物流公司" in result.answer_summary
    assert result.data_scope["carrier_local_city"] == "苏州"
    assert result.data_scope.get("city") is None
    assert [row["carrier_name"] for row in result.result_table.rows] == [
        "苏州晶茂物流有限公司",
        "苏州威洋供应链有限公司",
    ]
    assert any("承运商名称" in item and "苏州" in item for item in result.calculation_logic)
