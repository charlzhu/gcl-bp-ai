from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Protocol

from logistics_excel_loader import LogisticsExcelDataset, LogisticsExcelWorkbookLoader


CALCULATION_SUCCESS = "CALCULATED"
NEED_ORACLE_IMPLEMENTATION = "NEED_ORACLE_IMPLEMENTATION"
NEED_SOURCE_DATA = "NEED_SOURCE_DATA"
NEED_CALCULATION_CLARIFICATION = "NEED_CLARIFICATION"

METRIC_CONFIG: dict[str, dict[str, Any]] = {
    "shipment_watt": {
        "field": "shipment_watt",
        "unit": "W",
        "precision": 2,
        "label": "月度运量",
    },
    "freight_cost": {
        "field": "total_fee",
        "unit": "元",
        "precision": 2,
        "label": "月度运费",
    },
    "vehicle_count": {
        "field": "shipment_trip_count",
        "unit": "车次",
        "precision": 0,
        "label": "月度车次",
    },
}


@dataclass(frozen=True)
class LogisticsExpectedResult:
    """物流 Oracle expected_result。

    参数：
        case_id：验收 case ID。
        metric：标准指标编码。
        year：业务年份。
        month：业务月份。
        source_type：数据源类型，本轮固定为 excel。
        source_file：来源文件。
        value：计算结果。
        unit：计量单位。
        precision：结果精度。
        calculation_status：计算状态。
        reasons：计算说明或无法计算原因。
    返回值：无。
    """

    case_id: str
    metric: str
    year: int
    month: int | None
    source_type: str
    source_file: str | None
    value: Decimal | None
    unit: str | None
    precision: int | None
    calculation_status: str
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        """转换为 JSON 友好的字典。

        参数：无。
        返回值：
            expected_result 字典。
        """

        return {
            "case_id": self.case_id,
            "metric": self.metric,
            "year": self.year,
            "month": self.month,
            "source_type": self.source_type,
            "source_file": self.source_file,
            "value": self._json_value(),
            "unit": self.unit,
            "precision": self.precision,
            "calculation_status": self.calculation_status,
            "reasons": self.reasons,
        }

    def _json_value(self) -> int | float | None:
        """转换结果值。

        参数：无。
        返回值：
            int/float/None。
        """

        if self.value is None:
            return None
        if self.precision == 0:
            return int(self.value)
        return float(self.value)


class MetricCalculator(Protocol):
    """指标计算器基础接口。

    参数：由实现类决定。
    返回值：LogisticsExpectedResult。
    """

    def calculate(
        self,
        *,
        case_id: str,
        metric: str,
        year: int,
        month: int | None,
        dataset: LogisticsExcelDataset,
    ) -> LogisticsExpectedResult:
        """计算单个指标。

        参数：
            case_id：验收 case ID。
            metric：标准指标编码。
            year：业务年份。
            month：业务月份。
            dataset：标准化 Excel 数据集。
        返回值：
            LogisticsExpectedResult。
        """


class MonthlySumMetricCalculator:
    """月度汇总指标计算器。

    参数：无。
    返回值：无。

    业务逻辑：
        P2.2 基础版只支持 2023-2025 历史 Excel 的月度运量、月度运费和车次，
        其他指标必须显式返回 NEED_ORACLE_IMPLEMENTATION，不能猜测答案。
    """

    def calculate(
        self,
        *,
        case_id: str,
        metric: str,
        year: int,
        month: int | None,
        dataset: LogisticsExcelDataset,
    ) -> LogisticsExpectedResult:
        """计算月度汇总指标。

        参数：
            case_id：验收 case ID。
            metric：标准指标编码。
            year：业务年份。
            month：业务月份。
            dataset：标准化 Excel 数据集。
        返回值：
            LogisticsExpectedResult。
        """

        metric_config = METRIC_CONFIG.get(metric)
        if metric_config is None:
            return self._unsupported_result(case_id, metric, year, month, dataset.source_file)
        if month is None:
            return LogisticsExpectedResult(
                case_id=case_id,
                metric=metric,
                year=year,
                month=None,
                source_type="excel",
                source_file=dataset.source_file,
                value=None,
                unit=metric_config["unit"],
                precision=metric_config["precision"],
                calculation_status=NEED_CALCULATION_CLARIFICATION,
                reasons=["月度 Excel Oracle 基础版需要明确单一月份，当前问题未识别到月份。"],
            )

        value_field = str(metric_config["field"])
        total = Decimal("0")
        matched_rows = 0
        target_month = f"{year:04d}-{month:02d}"
        for row in dataset.rows:
            if row.biz_year != year or row.biz_month != target_month:
                continue
            matched_rows += 1
            value = getattr(row, value_field)
            if value is not None:
                total += value

        precision = int(metric_config["precision"])
        rounded = self._round_decimal(total, precision)
        return LogisticsExpectedResult(
            case_id=case_id,
            metric=metric,
            year=year,
            month=month,
            source_type="excel",
            source_file=dataset.source_file,
            value=rounded,
            unit=str(metric_config["unit"]),
            precision=precision,
            calculation_status=CALCULATION_SUCCESS,
            reasons=[
                f"按 {target_month} 过滤历史 Excel 标准行 {matched_rows} 条。",
                f"指标口径：{metric_config['label']} 使用标准字段 {value_field} 求和。",
            ],
        )

    def _unsupported_result(
        self,
        case_id: str,
        metric: str,
        year: int,
        month: int | None,
        source_file: str | None,
    ) -> LogisticsExpectedResult:
        """构造未支持指标结果。

        参数：
            case_id：验收 case ID。
            metric：标准指标编码。
            year：业务年份。
            month：业务月份。
            source_file：来源文件。
        返回值：
            LogisticsExpectedResult。
        """

        return LogisticsExpectedResult(
            case_id=case_id,
            metric=metric,
            year=year,
            month=month,
            source_type="excel",
            source_file=source_file,
            value=None,
            unit=None,
            precision=None,
            calculation_status=NEED_ORACLE_IMPLEMENTATION,
            reasons=[f"P2.2 Excel Oracle 基础版尚未实现指标 {metric} 的标准答案计算。"],
        )

    def _round_decimal(self, value: Decimal, precision: int) -> Decimal:
        """按精度舍入 Decimal。

        参数：
            value：原始 Decimal。
            precision：小数位数。
        返回值：
            舍入后的 Decimal。
        """

        quantize_unit = Decimal("1") if precision == 0 else Decimal("1").scaleb(-precision)
        return value.quantize(quantize_unit, rounding=ROUND_HALF_UP)


class LogisticsExcelOracleCalculator:
    """物流 Excel Oracle 计算编排器。

    参数：
        loader：物流 Excel loader。
        metric_calculator：指标计算器，默认使用月度汇总计算器。
    返回值：无。
    """

    def __init__(
        self,
        loader: LogisticsExcelWorkbookLoader,
        metric_calculator: MetricCalculator | None = None,
    ) -> None:
        self.loader = loader
        self.metric_calculator = metric_calculator or MonthlySumMetricCalculator()

    def calculate(
        self,
        *,
        case_id: str,
        metric: str,
        year: int,
        month: int | None,
    ) -> LogisticsExpectedResult:
        """计算单个 case 的 Excel expected_result。

        参数：
            case_id：验收 case ID。
            metric：标准指标编码。
            year：业务年份。
            month：业务月份。
        返回值：
            LogisticsExpectedResult。
        """

        source_file = self.loader.get_source_file(year)
        if metric not in METRIC_CONFIG:
            return MonthlySumMetricCalculator()._unsupported_result(
                case_id,
                metric,
                year,
                month,
                str(source_file) if source_file else None,
            )
        try:
            dataset = self.loader.load_year(year)
        except FileNotFoundError as exc:
            return LogisticsExpectedResult(
                case_id=case_id,
                metric=metric,
                year=year,
                month=month,
                source_type="excel",
                source_file=str(source_file) if source_file else None,
                value=None,
                unit=METRIC_CONFIG[metric]["unit"],
                precision=METRIC_CONFIG[metric]["precision"],
                calculation_status=NEED_SOURCE_DATA,
                reasons=[str(exc)],
            )
        return self.metric_calculator.calculate(
            case_id=case_id,
            metric=metric,
            year=year,
            month=month,
            dataset=dataset,
        )
