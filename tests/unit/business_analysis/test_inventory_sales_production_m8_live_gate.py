"""
产销存 ISP M8 灰度接管门禁 focused tests。

测试范围：
    1. M8 feature flag 关闭时 M4 链路不受影响
    2. M8 feature flag 开启但 provider 不可用时 fallback 到 M4
    3. M8 响应格式与 M4 一致
    4. M8 响应不暴露内部技术实现
    5. M8 gate 组件不可用时返回 False（触发 fallback）

禁止：
    - 不修改物流/计划 BOM/功率预测主链路
    - 不连接真实 LLM provider
    - 不访问真实数据库
"""

from __future__ import annotations

import importlib
import json
from typing import Any
from unittest.mock import MagicMock

M8_GATE_VERSION = "business_analysis_inventory_sales_production_m8_live_gate.v1"


def _m8_module():
    """加载产销存 M8 live gate 模块。"""
    return importlib.import_module(
        "backend.app.domains.business_analysis.services.inventory_sales_production.m8_live_gate"
    )


def _qa_module():
    """加载产销存 QA 服务模块。"""
    return importlib.import_module(
        "backend.app.domains.business_analysis.services.inventory_sales_production.qa_service"
    )


def _safe_text(payload: object) -> str:
    """把对象转成小写 JSON 文本，便于统一检查脱敏结果。"""
    return json.dumps(payload, ensure_ascii=False, default=str).lower()


class FakeSettings:
    """测试用配置对象，模拟 pydantic Settings。"""

    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


# ==================== M8 gate 独立单测 ====================


def test_m8_live_gate_version_is_stable() -> None:
    """M8 gate 版本号必须稳定，防止下游误匹配。"""
    m8 = _m8_module()
    assert m8.M8_LIVE_GATE_VERSION == M8_GATE_VERSION


def test_m8_live_gate_returns_false_when_provider_not_available() -> None:
    """M8 gate 在 LLM provider 不可用时应返回 (False, None)，触发 fallback。"""
    m8 = _m8_module()

    settings = FakeSettings(
        isp_m8_live_provider_enabled=True,
        llm_base_url="",
        llm_api_key="",
        llm_model="",
    )
    gate = m8.InventorySalesProductionM8LiveGate(settings=settings)
    success, response = gate.try_ask(question="2025年发货量是多少", trace_id="test-m8-001")
    assert success is False
    assert response is None


def test_m8_live_gate_returns_false_when_feature_flag_off_in_settings() -> None:
    """当 feature flag 关闭时，M8 gate 不应被 QA 服务调用；
    此处验证 gate 本身在无 LLM 配置时返回 False（与 flag 无关）。"""
    m8 = _m8_module()

    settings = FakeSettings(
        isp_m8_live_provider_enabled=False,
        llm_base_url="",
        llm_api_key="",
        llm_model="",
    )
    gate = m8.InventorySalesProductionM8LiveGate(settings=settings)
    success, response = gate.try_ask(question="测试问题", trace_id="test-m8-002")
    assert success is False
    assert response is None


def test_m8_live_gate_no_technical_leakage_in_failure() -> None:
    """M8 gate 失败时不应在返回结果中暴露技术细节。"""
    m8 = _m8_module()

    settings = FakeSettings(
        isp_m8_live_provider_enabled=True,
        llm_base_url="",
        llm_api_key="",
        llm_model="",
    )
    gate = m8.InventorySalesProductionM8LiveGate(settings=settings)
    # M8 失败返回 None，不暴露任何内容 - 这是正确的行为
    success, response = gate.try_ask(question="2025年发货量是多少", trace_id="test-m8-003")
    assert success is False
    assert response is None


# ==================== QA 服务 M8 集成单测 ====================


def test_qa_service_feature_flag_off_uses_m4_directly() -> None:
    """feature flag 关闭时，QA 服务直接走 M4 链路，不尝试 M8。"""
    qa = _qa_module()

    # 构造 M4 所需的 mock planner 和 executor
    mock_planner = MagicMock()
    mock_plan = MagicMock()
    mock_planner.build_plan.return_value = mock_plan

    mock_executor = MagicMock()
    mock_executor.execute.return_value = _fake_success_query_result()

    mock_log_repo = MagicMock()
    mock_log_repo.write_query_log.return_value = 1

    settings = FakeSettings(isp_m8_live_provider_enabled=False)

    service = qa.InventorySalesProductionQaService(
        db=MagicMock(),
        planner=mock_planner,
        executor=mock_executor,
        query_log_repository=mock_log_repo,
        settings=settings,
    )

    response = service.ask(question="2025年发货量是多少", trace_id="test-m4-001")

    # 验证 M4 链路被调用
    assert mock_planner.build_plan.called
    assert mock_executor.execute.called

    # 验证响应结构
    result = response.model_dump(mode="json")
    assert result["classification"] == "A"
    assert result["status"]["code"] == "OK"
    assert result["domain"] == "business_analysis"
    assert result["sub_domain"] == "inventory_sales_production"

    # 验证无技术泄漏
    safe = _safe_text(result)
    for forbidden in ("sql", "query_key", "planner", "guardrail", "ba_isp", "metric_code", "dwd_ba_isp"):
        assert forbidden not in safe


def test_qa_service_feature_flag_on_m8_fails_falls_back_to_m4() -> None:
    """feature flag 开启但 M8 provider 不可用，应 fallback 到 M4。"""
    qa = _qa_module()

    mock_planner = MagicMock()
    mock_plan = MagicMock()
    mock_planner.build_plan.return_value = mock_plan

    mock_executor = MagicMock()
    mock_executor.execute.return_value = _fake_success_query_result()

    mock_log_repo = MagicMock()
    mock_log_repo.write_query_log.return_value = 1

    # feature flag 开启但无真实 LLM 配置 → M8 会失败，应 fallback 到 M4
    settings = FakeSettings(
        isp_m8_live_provider_enabled=True,
        llm_base_url="",
        llm_api_key="",
        llm_model="",
    )

    service = qa.InventorySalesProductionQaService(
        db=MagicMock(),
        planner=mock_planner,
        executor=mock_executor,
        query_log_repository=mock_log_repo,
        settings=settings,
    )

    response = service.ask(question="2025年发货量是多少", trace_id="test-m8-fallback-001")

    # M8 失败后应正确 fallback 到 M4
    assert mock_planner.build_plan.called
    assert mock_executor.execute.called

    result = response.model_dump(mode="json")
    assert result["classification"] == "A"
    assert result["status"]["code"] == "OK"


def test_qa_service_no_settings_uses_m4() -> None:
    """未注入 settings 时，QA 服务应等同于 M4 行为。"""
    qa = _qa_module()

    mock_planner = MagicMock()
    mock_plan = MagicMock()
    mock_planner.build_plan.return_value = mock_plan

    mock_executor = MagicMock()
    mock_executor.execute.return_value = _fake_success_query_result()

    mock_log_repo = MagicMock()
    mock_log_repo.write_query_log.return_value = 1

    # 不传 settings → _is_m8_enabled 返回 False
    service = qa.InventorySalesProductionQaService(
        db=MagicMock(),
        planner=mock_planner,
        executor=mock_executor,
        query_log_repository=mock_log_repo,
    )

    response = service.ask(question="2025年发货量是多少", trace_id="test-no-settings-001")
    assert mock_planner.build_plan.called
    assert mock_executor.execute.called

    result = response.model_dump(mode="json")
    assert result["classification"] == "A"


def test_qa_service_is_m8_enabled_returns_false_without_settings() -> None:
    """_is_m8_enabled 在 settings 为 None 时必须返回 False。"""
    qa = _qa_module()

    service = qa.InventorySalesProductionQaService(
        db=MagicMock(),
        planner=MagicMock(),
        executor=MagicMock(),
    )
    assert service._is_m8_enabled() is False


def test_qa_service_is_m8_enabled_returns_true_with_flag_on() -> None:
    """_is_m8_enabled 在 feature flag 开启时必须返回 True。"""
    qa = _qa_module()

    settings = FakeSettings(isp_m8_live_provider_enabled=True)
    service = qa.InventorySalesProductionQaService(
        db=MagicMock(),
        planner=MagicMock(),
        executor=MagicMock(),
        settings=settings,
    )
    assert service._is_m8_enabled() is True


def test_qa_service_is_m8_enabled_returns_false_with_flag_off() -> None:
    """_is_m8_enabled 在 feature flag 关闭时必须返回 False。"""
    qa = _qa_module()

    settings = FakeSettings(isp_m8_live_provider_enabled=False)
    service = qa.InventorySalesProductionQaService(
        db=MagicMock(),
        planner=MagicMock(),
        executor=MagicMock(),
        settings=settings,
    )
    assert service._is_m8_enabled() is False


def test_qa_service_error_response_no_technical_leakage() -> None:
    """QA 服务异常响应不应暴露技术细节。"""
    qa = _qa_module()

    mock_planner = MagicMock()
    # 模拟 M4 planner 抛异常
    mock_planner.build_plan.side_effect = RuntimeError("database connection failed dwd_ba_isp_monthly_fact")

    mock_executor = MagicMock()
    mock_log_repo = MagicMock()
    mock_log_repo.write_query_log.return_value = 1

    settings = FakeSettings(isp_m8_live_provider_enabled=False)

    service = qa.InventorySalesProductionQaService(
        db=MagicMock(),
        planner=mock_planner,
        executor=mock_executor,
        query_log_repository=mock_log_repo,
        settings=settings,
    )

    response = service.ask(question="测试", trace_id="test-err-001")
    result = response.model_dump(mode="json")

    # 错误响应不应暴露内部细节
    assert result["classification"] == "D"
    safe = _safe_text(result)
    for forbidden in ("dwd_ba_isp", "database connection", "monthly_fact", "sql"):
        assert forbidden not in safe, f"发现技术泄漏: {forbidden}"


# ==================== 辅助函数 ====================


def _fake_success_query_result() -> Any:
    """构造模拟的 M3 QueryResult。"""
    from backend.app.domains.business_analysis.schemas.inventory_sales_production_query import (
        InventorySalesProductionQueryResult,
        InventorySalesProductionQueryRow,
    )
    from decimal import Decimal

    return InventorySalesProductionQueryResult(
        status="success",
        answer_summary="2025年发货量为 1234.56000000 MW，共 12 条记录。",
        rows=[
            InventorySalesProductionQueryRow(
                metric_code="shipment_volume",
                metric_name="发货量",
                value_decimal=Decimal("1234.56"),
                dimensions={"business_year": 2025},
                months_covered=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
                unit_standard="MW",
                aggregation_type="sum",
                row_count=12,
            )
        ],
        warnings=[],
        calculation_policy="sum",
        period_label="2025年",
        query_key="ba_isp_metric_summary",
    )
