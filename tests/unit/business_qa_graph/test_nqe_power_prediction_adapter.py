"""NQE PowerPredictionEngine adapter tests."""
from __future__ import annotations
from unittest.mock import patch

from backend.app.domains.business_qa_graph.nqe_power_prediction_adapter import NqePowerPredictionAdapter, NqePowerPredictionResult


def test_missing_model_code() -> None:
    adapter = NqePowerPredictionAdapter()
    result = adapter.try_predict(model_code="")
    assert result.requested and not result.executed
    assert "model_code" in result.missing_slots


def test_engine_error() -> None:
    adapter = NqePowerPredictionAdapter()
    with patch.object(adapter, "try_predict", return_value=NqePowerPredictionResult(
        requested=True, executed=False, fallback_reason="prediction_error: engine down"
    )):
        result = adapter.try_predict(model_code="NT12R-66GDF")
        assert result.executed is False
        assert "prediction_error" in result.fallback_reason


def test_not_prediction_question_no_trigger() -> None:
    """非预测类问题不触发。adapter 仅在显式调用 try_predict 时执行。"""
    adapter = NqePowerPredictionAdapter()
    result = adapter.try_predict(model_code="")
    assert result.requested and not result.executed  # 请求了但缺参


def test_result_to_dict() -> None:
    result = NqePowerPredictionResult(
        requested=True, executed=True, model_code="NT12R", supplier_name="supplier_a",
        center_power=450.0, trace_summary="ok"
    )
    d = result.to_dict()
    assert d["model_code"] == "NT12R"
    assert d["executed"] is True
