from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

from sqlalchemy.orm import Session

from backend.app.domains.plan_bom.models import PlanPowerModelSheet, PlanPowerModelVersion, PlanPowerSupplierEfficiencyDistribution
from backend.app.domains.plan_bom.services.power_prediction_engine import PowerPredictionEngine, PowerPredictionError, PowerPredictionResult


@dataclass(slots=True)
class PowerRecommendationItem:
    """单个供应商推荐结果。"""

    supplier_name: str
    score: float
    predicted_target_ratio: dict[str, float]
    target_diff: dict[str, float]
    leakage_ratio: float
    coverage_ratio: float
    suggested_efficiency_segments: list[dict[str, float]]
    prediction: PowerPredictionResult
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        """返回可 JSON 序列化的推荐项。"""
        return {
            "supplier_name": self.supplier_name,
            "score": self.score,
            "predicted_target_ratio": self.predicted_target_ratio,
            "target_diff": self.target_diff,
            "leakage_ratio": self.leakage_ratio,
            "coverage_ratio": self.coverage_ratio,
            "suggested_efficiency_segments": self.suggested_efficiency_segments,
            "prediction": self.prediction.to_dict(),
            "warnings": self.warnings,
        }


@dataclass(slots=True)
class PowerRecommendationResult:
    """供应商功率推荐结果。"""

    model_code: str
    target_power_ratio: dict[str, float]
    recommendations: list[PowerRecommendationItem]
    rejected_suppliers: list[dict[str, Any]]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        """返回可 JSON 序列化的推荐结果。"""
        return {
            "model_code": self.model_code,
            "target_power_ratio": self.target_power_ratio,
            "recommendations": [item.to_dict() for item in self.recommendations],
            "rejected_suppliers": self.rejected_suppliers,
            "warnings": self.warnings,
        }


class PowerRecommendationService:
    """计划 BOM 功率预测供应商推荐服务。

    职责边界：
        1. 基于 `PowerPredictionEngine` 的确定性结果评分排序；
        2. 不做 BOM 配置自动映射，不接入 QA，不调用 LLM；
        3. 无有效效率分布的供应商不能参与推荐。
    """

    def __init__(self, db: Session, engine: PowerPredictionEngine | None = None) -> None:
        """初始化推荐服务。

        参数：
            db: SQLAlchemy 会话。
            engine: 可选计算引擎；为空时使用当前 db 创建。
        """
        self.db = db
        self.engine = engine or PowerPredictionEngine(db)

    def recommend(
        self,
        *,
        model_code: str,
        configuration: Mapping[str, Any] | None = None,
        target_power_ratio: Mapping[str | int | float, float] | None = None,
        supplier_names: Sequence[str] | None = None,
        version_id: int | None = None,
    ) -> PowerRecommendationResult:
        """按目标功率比例推荐供应商。

        参数：
            model_code: 版型编码。
            configuration: 显式配置项；其中 supplier 会在遍历供应商时被覆盖。
            target_power_ratio: 目标功率档比例，例如 {"620": 0.5, "625": 0.5}。
            supplier_names: 指定候选供应商；为空时遍历该版型所有有效供应商。
            version_id: 指定模型版本；为空时读取 active 版本。

        返回：
            推荐结果，按 score 降序排列。
        """
        target = self._normalize_target_ratio(target_power_ratio)
        configuration = dict(configuration or {})
        candidates = list(supplier_names) if supplier_names else self._list_suppliers(model_code, version_id)
        if not candidates:
            raise PowerPredictionError(f"版型 {model_code} 没有有效供应商效率分布，无法推荐。")

        recommendations: list[PowerRecommendationItem] = []
        rejected: list[dict[str, Any]] = []
        warnings: list[str] = []
        for supplier in candidates:
            try:
                supplier_config = dict(configuration)
                supplier_config["supplier"] = supplier
                prediction = self.engine.predict(
                    model_code=model_code,
                    configuration=supplier_config,
                    supplier_name=supplier,
                    version_id=version_id,
                )
                item = self._score_prediction(supplier, prediction, target)
                recommendations.append(item)
            except PowerPredictionError as exc:
                if "目标功率档不在模型输出范围" in str(exc):
                    raise
                rejected.append({"supplier_name": supplier, "reason": str(exc)})
        recommendations.sort(key=lambda item: item.score, reverse=True)
        if not recommendations:
            raise PowerPredictionError(f"所有候选供应商均无法推荐：{rejected}")
        return PowerRecommendationResult(
            model_code=model_code,
            target_power_ratio=target,
            recommendations=recommendations,
            rejected_suppliers=rejected,
            warnings=warnings,
        )

    def _score_prediction(
        self,
        supplier: str,
        prediction: PowerPredictionResult,
        target: Mapping[str, float],
    ) -> PowerRecommendationItem:
        """对单个供应商预测结果计算匹配度。"""
        missing_targets = [key for key in target if key not in prediction.weighted_distribution]
        if missing_targets:
            raise PowerPredictionError(f"目标功率档不在模型输出范围内：{missing_targets}")
        predicted = {key: prediction.weighted_distribution.get(key, 0.0) for key in target}
        diffs = {key: predicted[key] - target[key] for key in target}
        target_abs_error = sum(abs(value) for value in diffs.values())
        target_predicted_sum = sum(predicted.values())
        leakage_ratio = max(0.0, sum(prediction.weighted_distribution.values()) - target_predicted_sum)
        coverage_ratio = min(1.0, max(0.0, prediction.total_ratio))
        missing_distribution_penalty = max(0.0, 1.0 - coverage_ratio) * 100.0
        unresolved_penalty = len(prediction.unresolved_items) * 20.0
        score = 100.0 - target_abs_error * 100.0 - leakage_ratio * 50.0 - missing_distribution_penalty - unresolved_penalty
        score = round(max(0.0, min(100.0, score)), 6)
        return PowerRecommendationItem(
            supplier_name=supplier,
            score=score,
            predicted_target_ratio={key: round(value, 10) for key, value in predicted.items()},
            target_diff={key: round(value, 10) for key, value in diffs.items()},
            leakage_ratio=round(leakage_ratio, 10),
            coverage_ratio=round(coverage_ratio, 10),
            suggested_efficiency_segments=self._suggest_efficiency_segments(prediction, list(target.keys())),
            prediction=prediction,
            warnings=list(prediction.warnings),
        )

    @staticmethod
    def _suggest_efficiency_segments(prediction: PowerPredictionResult, target_bins: list[str]) -> list[dict[str, float]]:
        """按目标功率档贡献度推荐电池效率段。

        参数：
            prediction: 单供应商 M3 确定性预测结果。
            target_bins: 用户关注的目标功率档 key 列表。

        返回：
            最多 3 个建议效率段；字段保留效率值、百分比、目标档贡献和供应商效率占比，供 QA/API 展示直接使用。
        """
        scored: list[tuple[float, float, float]] = []
        for row in prediction.efficiency_rows:
            contribution = float(row.ratio_value) * sum(float(row.bin_probabilities.get(power_bin, 0.0)) for power_bin in target_bins)
            if contribution <= 0:
                continue
            scored.append((contribution, float(row.efficiency_value), float(row.ratio_value)))
        top_rows = sorted(scored, key=lambda item: item[0], reverse=True)[:3]
        return [
            {
                "efficiency_value": round(efficiency, 6),
                "efficiency_percent": round(efficiency * 100.0, 3),
                "target_contribution_ratio": round(contribution, 10),
                "supplier_efficiency_ratio": round(ratio, 10),
            }
            for contribution, efficiency, ratio in top_rows
        ]

    def _normalize_target_ratio(self, target_power_ratio: Mapping[str | int | float, float] | None) -> dict[str, float]:
        """归一化目标功率比例。"""
        if not target_power_ratio:
            raise PowerPredictionError("推荐服务必须提供目标功率档比例。")
        target: dict[str, float] = {}
        total = 0.0
        for key, value in target_power_ratio.items():
            try:
                bin_value = float(key)
                ratio = float(value)
            except (TypeError, ValueError) as exc:
                raise PowerPredictionError(f"目标功率档和比例必须是数字：{key}={value}") from exc
            if not math.isfinite(bin_value) or not math.isfinite(ratio):
                raise PowerPredictionError(f"目标功率档和比例必须是有限数字：{key}={value}")
            if ratio < 0:
                raise PowerPredictionError(f"目标功率档比例不能为负数：{key}={value}")
            normalized_key = self._bin_key(bin_value)
            if normalized_key in target:
                raise PowerPredictionError(f"目标功率档重复：{normalized_key}")
            target[normalized_key] = ratio
            total += ratio
        if total <= 0:
            raise PowerPredictionError("目标功率档比例总和必须大于 0。")
        return {key: value / total for key, value in target.items()}

    def _list_suppliers(self, model_code: str, version_id: int | None) -> list[str]:
        """列出版型下所有有效供应商。"""
        version = self._get_version(version_id)
        normalized_model_code = model_code.strip().upper()
        sheets = (
            self.db.query(PlanPowerModelSheet)
            .filter(PlanPowerModelSheet.version_id == version.id)
            .all()
        )
        sheet = next((row for row in sheets if row.normalized_model_code.strip().upper() == normalized_model_code), None)
        if sheet is None:
            raise PowerPredictionError(f"功率模型版型不存在：{model_code}")
        rows = (
            self.db.query(PlanPowerSupplierEfficiencyDistribution.supplier_name)
            .filter(PlanPowerSupplierEfficiencyDistribution.sheet_id == sheet.id, PlanPowerSupplierEfficiencyDistribution.is_valid == 1)
            .distinct()
            .order_by(PlanPowerSupplierEfficiencyDistribution.supplier_name.asc())
            .all()
        )
        return [row[0] for row in rows]

    def _get_version(self, version_id: int | None) -> PlanPowerModelVersion:
        """读取指定版本或当前 active 版本。"""
        query = self.db.query(PlanPowerModelVersion)
        if version_id is not None:
            version = query.filter(PlanPowerModelVersion.id == version_id).first()
        else:
            version = query.filter(PlanPowerModelVersion.is_active == 1).order_by(PlanPowerModelVersion.id.desc()).first()
        if version is None:
            raise PowerPredictionError("未找到 active 功率模型版本，请先导入并激活模型。")
        return version

    def _bin_key(self, value: float) -> str:
        """统一功率档 key 格式。"""
        if abs(value - round(value)) < 1e-9:
            return str(int(round(value)))
        return f"{value:.2f}".rstrip("0").rstrip(".")


__all__ = [
    "PowerRecommendationItem",
    "PowerRecommendationResult",
    "PowerRecommendationService",
]
