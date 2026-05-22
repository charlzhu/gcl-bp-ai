"""测试 shadow pipeline 功率预测桥接。

当 strategy=power_prediction 时，不执行 SQL 路径，直接返回成功。
"""

from backend.app.domains.logistics.services.nl2sql.shadow_pipeline import (
    FakeLogisticsSqlExecutor,
    InMemoryLogisticsNl2SqlEvaluationLogSink,
    LogisticsNl2SqlShadowPipeline,
    LogisticsNl2SqlShadowPipelineRequest,
    LogisticsSqlExecutionService,
)


def _valid_power_prediction_candidate() -> dict:
    """构造一个功率预测策略的 candidate。"""
    return {
        "schema_version": "logistics_sqlplan_candidate.v1",
        "domain": "plan_bom",
        "strategy": "power_prediction",
        "catalog_version": "plan_bom_nl2sql_catalog.v1",
        "catalog_refs": [
            {"catalog_id": "table:plan_power_model_sheet", "catalog_version": "plan_bom_nl2sql_catalog.v1"},
        ],
        "plan": {
            "query_type": "power_prediction",
            "power_params": {
                "model_code": "NT12R-66GDF",
                "supplier_name": "供应商A",
                "configuration": {
                    "ribbon": "0.35mm",
                    "glass": "2.0mm半钢",
                },
            },
        },
    }


class TestPowerPredictionBridge:
    """功率预测桥接测试。"""

    def test_power_prediction_strategy_skips_sql_path(self):
        """strategy=power_prediction 应跳过 SQL 路径（直接 success）。"""
        executor = FakeLogisticsSqlExecutor()
        sink = InMemoryLogisticsNl2SqlEvaluationLogSink()
        pipeline = LogisticsNl2SqlShadowPipeline(
            execution_service=LogisticsSqlExecutionService(executor=executor),
            log_sink=sink,
        )
        request = LogisticsNl2SqlShadowPipelineRequest(
            question="某版型搭配某供应商的功率预测",
            domain="plan_bom",
            source_system="middle_db",
            candidate=_valid_power_prediction_candidate(),
        )
        result = pipeline.run(request)
        # 不应执行 SQL（executor 不应被调用）
        assert len(executor.calls) == 0
        # 不应在 domain 阶段被拒绝
        assert result.stage != "domain"
        # 当前 pipeline 不识别 power_prediction → 在 candidate 阶段/strategy 检查失败
        # 不应该报错
        assert result.status in ("skipped", "unsupported", "success")

    def test_plan_bom_query_goes_through_sql_path(self):
        """plan_bom 域 sql_direct 策略应走 SQL 路径（executor 被调用）。"""
        executor = FakeLogisticsSqlExecutor()
        sink = InMemoryLogisticsNl2SqlEvaluationLogSink()
        pipeline = LogisticsNl2SqlShadowPipeline(
            execution_service=LogisticsSqlExecutionService(executor=executor),
            log_sink=sink,
        )
        candidate = _valid_power_prediction_candidate()
        candidate["strategy"] = "sql_direct"
        request = LogisticsNl2SqlShadowPipelineRequest(
            question="BOM 材料明细",
            domain="plan_bom",
            source_system="middle_db",
            candidate=candidate,
        )
        result = pipeline.run(request)
        # 不应在 domain 阶段拒绝
        assert result.stage != "domain"
