"""NQE PowerPredictionEngine fallback adapter.

NQE-SQL-MAIN-31：非侵入式接入。包装 PowerPredictionEngine.predict()。
不修改预测公式、不重写引擎。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NqePowerPredictionResult:
    """NQE 功率预测 fallback 统一输出。"""
    domain: str = "plan_bom"
    requested: bool = False
    executed: bool = False
    fallback_reason: str = ""
    missing_slots: list[str] = field(default_factory=list)
    model_code: str = ""
    supplier_name: str = ""
    center_power: float = 0.0
    bin_distribution: dict[str, float] = field(default_factory=dict)
    trace_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain, "requested": self.requested, "executed": self.executed,
            "fallback_reason": self.fallback_reason, "missing_slots": self.missing_slots,
            "model_code": self.model_code, "supplier_name": self.supplier_name,
            "center_power": self.center_power,
        }


class NqePowerPredictionAdapter:
    """NQE PowerPredictionEngine fallback adapter。

    参数：
        db_session: SQLAlchemy session（predict 需要读库）。
    """

    def __init__(self, db_session: Any = None) -> None:
        self._db = db_session

    def try_predict(
        self, *, model_code: str = "", supplier_name: str = "", configuration: dict[str, Any] | None = None
    ) -> NqePowerPredictionResult:
        """尝试调用 PowerPredictionEngine。

        参数：
            model_code: 组件版型编码。
            supplier_name: 供应商名称。
            configuration: 配置项字典。
        返回：
            统一 NqePowerPredictionResult。
        """
        result = NqePowerPredictionResult(requested=True)
        if not model_code:
            result.missing_slots = ["model_code"]
            result.fallback_reason = "missing_slots: model_code"
            return result

        try:
            from backend.app.domains.plan_bom.services.power_prediction_engine import PowerPredictionEngine

            engine = PowerPredictionEngine(db=self._db)
            prediction = engine.predict(
                model_code=model_code,
                supplier_name=supplier_name or None,
                configuration=configuration,
            )
            result.executed = True
            result.model_code = model_code
            result.supplier_name = supplier_name
            if prediction:
                result.center_power = float(getattr(prediction, "center_power", 0) or 0)
                if hasattr(prediction, "bin_distribution"):
                    result.bin_distribution = prediction.bin_distribution or {}
            result.trace_summary = f"predict({model_code}) success"
        except Exception as exc:
            result.fallback_reason = f"prediction_error: {exc}"
        return result
