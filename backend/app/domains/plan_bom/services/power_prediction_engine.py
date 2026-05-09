from __future__ import annotations

import json
import math
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy.orm import Session

from backend.app.domains.plan_bom.models import (
    PlanPowerBenchmarkFactor,
    PlanPowerFactorOption,
    PlanPowerModelSheet,
    PlanPowerModelValidationCase,
    PlanPowerModelVersion,
    PlanPowerPowerBin,
    PlanPowerSupplierEfficiencyDistribution,
)
from backend.app.domains.plan_bom.services.power_excel_parser_service import FORMULA_POLICY, dumps_power_json


OPTIONAL_FACTOR_KEYS = {"process"}
STANDARD_FACTOR_KEYS = ("ribbon", "glass", "supplier", "cell_size", "cable", "busbar")
PROCESS_FACTOR_KEY = "process"
CENTER_ROW_NUMBER = 36
EFFICIENCY_FIRST_ROW_NUMBER = 29
EFFICIENCY_STEP = 0.001
H_COLUMN_STEP = 0.0015
DEFAULT_BIN_STEP = 5.0


class PowerPredictionError(ValueError):
    """功率预测计算异常。

    设计说明：
        M3 计算引擎遇到无 active 版本、版型不存在、配置无法解析等问题时，
        使用该异常向调用方返回可解释错误，禁止静默编造预测结果。
    """


@dataclass(slots=True)
class PowerFactorTrace:
    """单个配置项对中心功率的影响追溯。"""

    factor_key: str
    input_value: str | None
    matched_label: str | None
    normalized_label: str | None
    effect_value: float
    source: str
    source_cell_ref: str | None = None
    is_default: bool = False
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """返回接口 / 测试友好的字典。"""
        return {
            "factor_key": self.factor_key,
            "input_value": self.input_value,
            "matched_label": self.matched_label,
            "normalized_label": self.normalized_label,
            "effect_value": self.effect_value,
            "source": self.source,
            "source_cell_ref": self.source_cell_ref,
            "is_default": self.is_default,
            "note": self.note,
        }


@dataclass(slots=True)
class PowerEfficiencyRow:
    """某个电池效率段的实际功率和功率档概率。"""

    efficiency_value: float
    ratio_value: float
    actual_power: float
    theoretical_power: float
    row_index: int
    source_cell_ref: str | None
    bin_probabilities: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        """返回接口 / 测试友好的字典。"""
        return {
            "efficiency_value": self.efficiency_value,
            "ratio_value": self.ratio_value,
            "actual_power": self.actual_power,
            "theoretical_power": self.theoretical_power,
            "row_index": self.row_index,
            "source_cell_ref": self.source_cell_ref,
            "bin_probabilities": self.bin_probabilities,
        }


@dataclass(slots=True)
class PowerPredictionResult:
    """确定性功率预测结果。"""

    version_id: int
    model_code: str
    sheet_id: int
    sheet_name: str
    supplier_name: str
    center_power: float
    base_power: float
    area: float
    std_dev: float
    cell_count: int
    center_efficiency: float
    factor_traces: list[PowerFactorTrace]
    efficiency_rows: list[PowerEfficiencyRow]
    power_bins: list[float]
    boundary_bins: list[float]
    weighted_distribution: dict[str, float]
    total_ratio: float
    unresolved_items: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """返回可直接 JSON 序列化的预测结果。"""
        return {
            "version_id": self.version_id,
            "model_code": self.model_code,
            "sheet_id": self.sheet_id,
            "sheet_name": self.sheet_name,
            "supplier_name": self.supplier_name,
            "center_power": self.center_power,
            "base_power": self.base_power,
            "area": self.area,
            "std_dev": self.std_dev,
            "cell_count": self.cell_count,
            "center_efficiency": self.center_efficiency,
            "factor_traces": [trace.to_dict() for trace in self.factor_traces],
            "efficiency_rows": [row.to_dict() for row in self.efficiency_rows],
            "power_bins": self.power_bins,
            "boundary_bins": self.boundary_bins,
            "weighted_distribution": self.weighted_distribution,
            "total_ratio": self.total_ratio,
            "unresolved_items": self.unresolved_items,
            "warnings": self.warnings,
        }


class PowerPredictionEngine:
    """计划 BOM 功率预测确定性计算引擎。

    职责边界：
        1. 只读取 M2 已结构化入库的 active 功率模型版本；
        2. 不读取用户自然语言，不调用 LLM，不执行 Excel VBA；
        3. 按 `semantic_fixed_mode` 复现中心功率、效率段实际功率和功率档概率；
        4. 对无法解析的配置返回受控错误，禁止伪造预测结果。
    """

    def __init__(self, db: Session) -> None:
        """初始化计算引擎。

        参数：
            db: SQLAlchemy 会话，用于读取 `plan_power_*` 模型版本数据。
        """
        self.db = db

    @staticmethod
    def normal_cdf(x: float) -> float:
        """复现 Excel `NORMSDIST` 标准正态分布函数。

        参数：
            x: 标准化后的 z 值。

        返回：
            标准正态累计概率。
        """
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def predict(
        self,
        *,
        model_code: str,
        configuration: Mapping[str, Any] | None = None,
        supplier_name: str | None = None,
        version_id: int | None = None,
    ) -> PowerPredictionResult:
        """执行单供应商功率预测。

        参数：
            model_code: 组件版型编码，例如 `NT12R-66GDF`。
            configuration: 配置项字典，支持 ribbon/glass/supplier/cell_size/cable/busbar/benchmark/process。
            supplier_name: 指定供应商；为空时优先使用 configuration['supplier']，再回退 Excel 默认供应商。
            version_id: 指定模型版本；为空时读取当前 active 版本。

        返回：
            `PowerPredictionResult`，包含中心功率、效率段、功率档分布和追溯信息。
        """
        configuration = dict(configuration or {})
        version = self._get_version(version_id)
        sheet = self._get_model_sheet(version.id, model_code)
        raw_meta = self._loads_json(sheet.raw_meta_json) or {}
        warnings: list[str] = []

        factor_traces: list[PowerFactorTrace] = []
        unresolved_items: list[dict[str, Any]] = []

        # 1. 常规配置项影响值。未显式传入时使用 Excel 当前默认项，保证可做默认配置 parity。
        selected_values: dict[str, str | None] = {}
        total_delta = 0.0
        area = self._decimal_to_float(sheet.area_default)
        std_dev = self._decimal_to_float(sheet.std_dev_default)
        for factor_key in STANDARD_FACTOR_KEYS:
            input_value = self._config_value(configuration, factor_key)
            if factor_key == "supplier" and supplier_name:
                input_value = supplier_name
            trace, option = self._resolve_factor_option(sheet.id, factor_key, input_value)
            if trace is None:
                unresolved_items.append(
                    {
                        "factor_key": factor_key,
                        "input_value": input_value,
                        "reason": "配置项未命中有效功率模型选项",
                    }
                )
                continue
            factor_traces.append(trace)
            selected_values[factor_key] = trace.matched_label
            total_delta += trace.effect_value
            if factor_key == "cell_size":
                area = self._decimal_to_float(option.area_value) or area
                std_dev = self._decimal_to_float(option.std_dev_value) or std_dev

        # 2. 标板基准使用专表优先匹配；缺省时复用 Excel 当前默认基准。
        benchmark_trace = self._resolve_benchmark(sheet, configuration.get("benchmark"))
        if benchmark_trace is None:
            unresolved_items.append(
                {
                    "factor_key": "benchmark",
                    "input_value": configuration.get("benchmark"),
                    "reason": "标板基准未命中有效功率模型选项",
                }
            )
        else:
            factor_traces.append(benchmark_trace)
            total_delta += benchmark_trace.effect_value

        # 3. 工艺选项属于可选项：模型页存在有效 process 时必须精确匹配；模型页不存在时才按 0 影响兼容。
        process_trace = self._resolve_process_option(sheet.id, configuration.get(PROCESS_FACTOR_KEY))
        if process_trace is None:
            unresolved_items.append(
                {
                    "factor_key": PROCESS_FACTOR_KEY,
                    "input_value": configuration.get(PROCESS_FACTOR_KEY),
                    "reason": "工艺配置项未命中有效功率模型选项",
                }
            )
        else:
            factor_traces.append(process_trace)
            total_delta += process_trace.effect_value
            if process_trace.source == "optional_missing_as_zero":
                warnings.append("当前模型页未结构化 process 配置项，已按 0 影响处理。")

        if unresolved_items:
            raise PowerPredictionError(f"功率预测配置无法解析：{unresolved_items}")
        if area is None or std_dev is None or not sheet.cell_count:
            raise PowerPredictionError(f"版型 {model_code} 缺少面积、标准差或电池片数量，无法计算。")
        if std_dev <= 0:
            raise PowerPredictionError(f"版型 {model_code} 标准差必须大于 0。")

        distribution_supplier = supplier_name or self._config_value(configuration, "supplier") or selected_values.get("supplier")
        if not distribution_supplier:
            raise PowerPredictionError("未能确定供应商，无法读取供应商效率分布。")
        supplier_rows = self._load_supplier_distribution(sheet.id, distribution_supplier)
        if not supplier_rows:
            raise PowerPredictionError(f"供应商无有效效率分布，不能参与功率预测：{distribution_supplier}")

        base_power = self._decimal_to_float(sheet.base_power)
        if base_power is None:
            raise PowerPredictionError(f"版型 {model_code} 缺少 base_power，无法计算。")
        center_power = base_power + total_delta

        efficiency_meta = self._resolve_efficiency_meta(sheet.normalized_model_code, raw_meta)
        if efficiency_meta["fallback"]:
            warnings.append("模型版本缺少效率网格 raw_meta，已按新版 TOPCon Excel 固定结构兜底。")
        center_efficiency = efficiency_meta["center_efficiency"]
        theoretical_at_center = self._theoretical_power(center_efficiency, area, sheet.cell_count)
        if theoretical_at_center <= 0:
            raise PowerPredictionError("中心效率理论功率必须大于 0。")
        center_ratio = center_power / theoretical_at_center

        output_bins, boundary_bins = self._load_power_grid(sheet)
        if not output_bins:
            raise PowerPredictionError(f"版型 {model_code} 未配置有效功率档边界。")

        weighted = {self._bin_key(power_bin): 0.0 for power_bin in output_bins}
        efficiency_rows: list[PowerEfficiencyRow] = []
        total_ratio = 0.0
        for row in supplier_rows:
            efficiency = self._decimal_to_float(row.efficiency_value)
            ratio = self._decimal_to_float(row.ratio_value) or 0.0
            if efficiency is None or ratio <= 0:
                continue
            row_index = self._efficiency_row_index(efficiency, efficiency_meta)
            theoretical = self._theoretical_power(efficiency, area, sheet.cell_count)
            row_offset = efficiency_meta["center_index"] - row_index
            actual_power = theoretical * (center_ratio + row_offset * H_COLUMN_STEP)
            probabilities = self._bin_probabilities(actual_power, std_dev, boundary_bins)
            for key, probability in probabilities.items():
                weighted[key] += ratio * probability
            total_ratio += ratio
            efficiency_rows.append(
                PowerEfficiencyRow(
                    efficiency_value=efficiency,
                    ratio_value=ratio,
                    actual_power=actual_power,
                    theoretical_power=theoretical,
                    row_index=row_index,
                    source_cell_ref=row.source_cell_ref,
                    bin_probabilities=probabilities,
                )
            )

        if total_ratio <= 0:
            raise PowerPredictionError(f"供应商效率分布总比例为 0，不能参与功率预测：{distribution_supplier}")
        if abs(total_ratio - 1.0) > 0.01:
            warnings.append(f"供应商效率分布总比例为 {total_ratio:.6f}，不等于 1，请检查模型版本。")

        return PowerPredictionResult(
            version_id=version.id,
            model_code=sheet.normalized_model_code,
            sheet_id=sheet.id,
            sheet_name=sheet.sheet_name,
            supplier_name=distribution_supplier,
            center_power=center_power,
            base_power=base_power,
            area=area,
            std_dev=std_dev,
            cell_count=sheet.cell_count,
            center_efficiency=center_efficiency,
            factor_traces=factor_traces,
            efficiency_rows=efficiency_rows,
            power_bins=output_bins,
            boundary_bins=boundary_bins,
            weighted_distribution={key: weighted[key] for key in sorted(weighted, key=lambda item: float(item))},
            total_ratio=total_ratio,
            unresolved_items=unresolved_items,
            warnings=warnings,
        )

    def record_validation_case(
        self,
        *,
        version_id: int,
        model_code: str,
        case_name: str,
        input_payload: Mapping[str, Any],
        excel_expected: Mapping[str, Any],
        system_result: Mapping[str, Any],
        diff_payload: Mapping[str, Any],
        status: str,
    ) -> PlanPowerModelValidationCase:
        """写入 M3 功率模型校验用例。

        参数：
            version_id: 模型版本 ID。
            model_code: 版型编码。
            case_name: 校验用例名称。
            input_payload: 输入配置。
            excel_expected: Excel / 公式链期望值。
            system_result: 系统计算值。
            diff_payload: 差异信息。
            status: pass / failed。

        返回：
            新增的 `PlanPowerModelValidationCase` ORM 对象。
        """
        row = PlanPowerModelValidationCase(
            version_id=version_id,
            model_code=model_code,
            case_name=case_name,
            input_json=dumps_power_json(dict(input_payload)),
            excel_expected_json=dumps_power_json(dict(excel_expected)),
            system_result_json=dumps_power_json(dict(system_result)),
            diff_json=dumps_power_json(dict(diff_payload)),
            status=status,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def _get_version(self, version_id: int | None) -> PlanPowerModelVersion:
        """读取指定版本或当前 active 版本。"""
        query = self.db.query(PlanPowerModelVersion)
        if version_id is not None:
            version = query.filter(PlanPowerModelVersion.id == version_id).first()
        else:
            version = query.filter(PlanPowerModelVersion.is_active == 1).order_by(PlanPowerModelVersion.id.desc()).first()
        if version is None:
            raise PowerPredictionError("未找到 active 功率模型版本，请先完成 M2 导入并激活模型。")
        if version.formula_policy != FORMULA_POLICY:
            raise PowerPredictionError(f"不支持的公式策略：{version.formula_policy}")
        if version.parse_status == "failed" or version.error_count:
            raise PowerPredictionError(f"功率模型版本解析失败，不允许计算：{version.id}")
        return version

    def _get_model_sheet(self, version_id: int, model_code: str) -> PlanPowerModelSheet:
        """按版型编码读取模型页。"""
        normalized = self._normalize_model_code(model_code)
        sheet = (
            self.db.query(PlanPowerModelSheet)
            .filter(PlanPowerModelSheet.version_id == version_id)
            .all()
        )
        for row in sheet:
            if self._normalize_model_code(row.normalized_model_code) == normalized:
                return row
        raise PowerPredictionError(f"功率模型版型不存在：{model_code}")

    def _resolve_factor_option(
        self,
        sheet_id: int,
        factor_key: str,
        input_value: Any,
    ) -> tuple[PowerFactorTrace | None, PlanPowerFactorOption | None]:
        """解析普通配置项选项。

        参数：
            sheet_id: 模型页 ID。
            factor_key: 配置项 key。
            input_value: 用户 / 上游传入配置值；为空时使用 Excel 默认项。

        返回：
            `(trace, option)`；无法命中时返回 `(None, None)`。
        """
        query = self.db.query(PlanPowerFactorOption).filter(
            PlanPowerFactorOption.sheet_id == sheet_id,
            PlanPowerFactorOption.factor_key == factor_key,
            PlanPowerFactorOption.is_valid == 1,
        )
        options = query.order_by(PlanPowerFactorOption.id.asc()).all()
        selected: PlanPowerFactorOption | None = None
        source = "input"
        if input_value is None or self._stringify(input_value) == "":
            selected = next((row for row in options if row.is_default), None) or (options[0] if options else None)
            source = "excel_default"
        else:
            normalized_input = self._normalize_label(input_value)
            selected = next(
                (
                    row
                    for row in options
                    if self._normalize_label(row.normalized_option_label) == normalized_input
                    or self._normalize_label(row.option_label) == normalized_input
                ),
                None,
            )
        if selected is None:
            return None, None
        trace = PowerFactorTrace(
            factor_key=factor_key,
            input_value=self._stringify(input_value),
            matched_label=selected.option_label,
            normalized_label=selected.normalized_option_label,
            effect_value=self._decimal_to_float(selected.effect_value) or 0.0,
            source=source,
            source_cell_ref=selected.source_cell_ref,
            is_default=bool(selected.is_default),
        )
        return trace, selected

    def _resolve_process_option(self, sheet_id: int, input_value: Any) -> PowerFactorTrace | None:
        """解析工艺配置项。

        参数：
            sheet_id: 模型页 ID。
            input_value: 输入工艺；为空时优先使用 Excel 默认工艺。

        返回：
            工艺影响值追溯；模型页没有 process 选项且未显式传入 process 时返回 0 影响追溯；有显式输入但无有效选项/无匹配时返回 None。
        """
        process_options = (
            self.db.query(PlanPowerFactorOption)
            .filter(
                PlanPowerFactorOption.sheet_id == sheet_id,
                PlanPowerFactorOption.factor_key == PROCESS_FACTOR_KEY,
                PlanPowerFactorOption.is_valid == 1,
            )
            .order_by(PlanPowerFactorOption.id.asc())
            .all()
        )
        if process_options:
            trace, _ = self._resolve_factor_option(sheet_id, PROCESS_FACTOR_KEY, input_value)
            return trace
        if input_value is not None and self._stringify(input_value) != "":
            return None
        return PowerFactorTrace(
            factor_key=PROCESS_FACTOR_KEY,
            input_value=self._stringify(input_value),
            matched_label=None,
            normalized_label=None,
            effect_value=0.0,
            source="optional_missing_as_zero",
            note="当前模型页未结构化 process 配置项，M3 按 0 影响处理。",
        )

    def _resolve_benchmark(
        self,
        sheet: PlanPowerModelSheet,
        input_value: Any,
    ) -> PowerFactorTrace | None:
        """解析标板基准影响值。

        参数：
            sheet: 模型页 ORM。
            input_value: 输入标板名称；为空时使用 Excel 默认标板。

        返回：
            影响值追溯；无法命中时返回 None。
        """
        default_input_value = input_value
        fallback_default_trace: PowerFactorTrace | None = None
        if input_value is None or self._stringify(input_value) == "":
            fallback_default_trace, _ = self._resolve_factor_option(sheet.id, "benchmark", None)
            default_input_value = fallback_default_trace.matched_label if fallback_default_trace else None
        if default_input_value is None:
            return PowerFactorTrace(
                factor_key="benchmark",
                input_value=None,
                matched_label=None,
                normalized_label=None,
                effect_value=0.0,
                source="missing_as_zero",
                note="模型未找到默认标板基准，按 0 影响处理。",
            )
        normalized_input = self._normalize_label(default_input_value)
        rows = (
            self.db.query(PlanPowerBenchmarkFactor)
            .filter(
                PlanPowerBenchmarkFactor.version_id == sheet.version_id,
                PlanPowerBenchmarkFactor.model_code == sheet.normalized_model_code,
            )
            .order_by(PlanPowerBenchmarkFactor.id.asc())
            .all()
        )
        for row in rows:
            if self._normalize_label(row.normalized_benchmark_name) == normalized_input or self._normalize_label(row.benchmark_name) == normalized_input:
                return PowerFactorTrace(
                    factor_key="benchmark",
                    input_value=self._stringify(default_input_value),
                    matched_label=row.benchmark_name,
                    normalized_label=row.normalized_benchmark_name,
                    effect_value=self._decimal_to_float(row.effect_value) or 0.0,
                    source="benchmark_table",
                    source_cell_ref=row.source_cell_ref,
                    is_default=fallback_default_trace is not None,
                )
        # 兼容 M2 factor_option 中保存的 benchmark 当前值。
        fallback_trace, _ = self._resolve_factor_option(sheet.id, "benchmark", default_input_value)
        return fallback_trace

    def _load_supplier_distribution(
        self,
        sheet_id: int,
        supplier_name: str,
    ) -> list[PlanPowerSupplierEfficiencyDistribution]:
        """读取指定供应商有效效率分布。"""
        normalized = self._normalize_label(supplier_name)
        rows = (
            self.db.query(PlanPowerSupplierEfficiencyDistribution)
            .filter(PlanPowerSupplierEfficiencyDistribution.sheet_id == sheet_id, PlanPowerSupplierEfficiencyDistribution.is_valid == 1)
            .order_by(PlanPowerSupplierEfficiencyDistribution.efficiency_value.asc())
            .all()
        )
        return [row for row in rows if self._normalize_label(row.normalized_supplier_name) == normalized or self._normalize_label(row.supplier_name) == normalized]

    def _load_power_grid(self, sheet: PlanPowerModelSheet) -> tuple[list[float], list[float]]:
        """读取功率档输出列和边界列。

        参数：
            sheet: 模型页 ORM，raw_meta 可提供 `power_bin_has_terminal_boundary`。

        返回：
            `(output_bins, boundary_bins)`；当模型缺少末尾上边界时，按相邻档距补一档上边界。
        """
        rows = (
            self.db.query(PlanPowerPowerBin)
            .filter(PlanPowerPowerBin.sheet_id == sheet.id, PlanPowerPowerBin.is_valid == 1)
            .order_by(PlanPowerPowerBin.bin_order.asc())
            .all()
        )
        bins = [self._decimal_to_float(row.power_bin) for row in rows if self._decimal_to_float(row.power_bin) is not None]
        if len(bins) < 2:
            return bins, bins
        raw_meta = self._loads_json(sheet.raw_meta_json) or {}
        output_count = self._to_int(raw_meta.get("probability_output_bin_count"))
        has_terminal_boundary = raw_meta.get("power_bin_has_terminal_boundary")
        if output_count is not None and output_count > 0:
            output_bins = bins[:output_count]
            if len(bins) >= output_count + 1:
                return output_bins, bins[: output_count + 1]
            step = self._infer_bin_step(bins)
            return output_bins, output_bins + [output_bins[-1] + step]
        if has_terminal_boundary is False:
            step = self._infer_bin_step(bins)
            return bins, bins + [bins[-1] + step]
        return bins[:-1], bins

    def _infer_bin_step(self, bins: list[float]) -> float:
        """推断相邻功率档步长。"""
        if len(bins) >= 2:
            steps = [round(bins[index + 1] - bins[index], 6) for index in range(len(bins) - 1) if bins[index + 1] > bins[index]]
            if steps:
                return steps[-1]
        return DEFAULT_BIN_STEP

    def _bin_probabilities(self, actual_power: float, std_dev: float, boundary_bins: list[float]) -> dict[str, float]:
        """计算某效率段在各功率档上的概率。"""
        probabilities: dict[str, float] = {}
        for lower, upper in zip(boundary_bins[:-1], boundary_bins[1:]):
            probability = self.normal_cdf((actual_power - lower) / std_dev) - self.normal_cdf((actual_power - upper) / std_dev)
            probabilities[self._bin_key(lower)] = max(0.0, min(1.0, probability))
        return probabilities

    def _resolve_efficiency_meta(self, model_code: str, raw_meta: Mapping[str, Any]) -> dict[str, Any]:
        """解析效率网格元数据。

        参数：
            model_code: 版型编码。
            raw_meta: M2 sheet raw_meta。

        返回：
            包含 efficiency_start/center_efficiency/center_index/fallback 等字段的字典。
        """
        start = self._to_float(raw_meta.get("efficiency_start"))
        center = self._to_float(raw_meta.get("center_efficiency"))
        step = self._to_float(raw_meta.get("efficiency_step")) or EFFICIENCY_STEP
        fallback = False
        if start is None or center is None:
            fallback = True
            normalized = self._normalize_model_code(model_code)
            if "(2.0)" in normalized:
                start, center = 0.255, 0.262
            elif any(token in normalized for token in ("48GDF", "48BGDF", "54GDF", "54BGDF")):
                start, center = 0.253, 0.260
            else:
                start, center = 0.247, 0.254
        center_index = int(round((center - start) / step))
        return {
            "efficiency_start": start,
            "center_efficiency": center,
            "efficiency_step": step,
            "center_index": center_index,
            "fallback": fallback,
        }

    def _efficiency_row_index(self, efficiency: float, meta: Mapping[str, Any]) -> int:
        """把效率值转换为 Excel C29:C48 中的 0 基位置。"""
        return int(round((efficiency - meta["efficiency_start"]) / meta["efficiency_step"]))

    def _theoretical_power(self, efficiency: float, area: float, cell_count: int) -> float:
        """计算某效率段的组件理论功率。"""
        return efficiency * area / 1000.0 * cell_count

    def _config_value(self, configuration: Mapping[str, Any], key: str) -> str | None:
        """读取配置值并兼容空字符串。"""
        if key not in configuration:
            return None
        value = self._stringify(configuration.get(key))
        return value or None

    def _normalize_label(self, value: Any) -> str:
        """归一化配置标签，便于精确匹配。"""
        text = self._stringify(value)
        text = unicodedata.normalize("NFKC", text)
        return "".join(text.split()).lower()

    def _normalize_model_code(self, value: Any) -> str:
        """归一化版型编码，保留 2.0 后缀语义。"""
        return unicodedata.normalize("NFKC", self._stringify(value)).strip().upper()

    def _stringify(self, value: Any) -> str:
        """把任意值转成去首尾空格字符串。"""
        if value is None:
            return ""
        return str(value).strip()

    def _loads_json(self, value: str | None) -> Any:
        """解析 JSON 文本。"""
        if not value:
            return None
        return json.loads(value)

    def _decimal_to_float(self, value: Decimal | int | float | None) -> float | None:
        """把 Decimal / 数字转成 float。"""
        if value is None:
            return None
        return float(value)

    def _to_float(self, value: Any) -> float | None:
        """宽松转换数字。"""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _to_int(self, value: Any) -> int | None:
        """宽松转换整数。"""
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _bin_key(self, value: float) -> str:
        """统一功率档 key 格式。"""
        if abs(value - round(value)) < 1e-9:
            return str(int(round(value)))
        return f"{value:.2f}".rstrip("0").rstrip(".")


__all__ = [
    "PowerEfficiencyRow",
    "PowerFactorTrace",
    "PowerPredictionEngine",
    "PowerPredictionError",
    "PowerPredictionResult",
]
