from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from source_router import EXCEL_SOURCE, MYSQL_SOURCE, route_logistics_sources
from logistics_excel_calculator import LogisticsExcelOracleCalculator
from logistics_excel_loader import LogisticsExcelSourceConfig, LogisticsExcelWorkbookLoader


ORACLE_READY_CANDIDATE = "ORACLE_READY_CANDIDATE"
NEED_CLARIFICATION = "NEED_CLARIFICATION"
ORACLE_ENGINE_VERSION = "p2.2-logistics-excel-oracle"

LOGISTICS_METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "shipment_watt": ("运量", "发运量", "发货量", "出货量", "瓦数"),
    "freight_cost": ("运费", "运输费用", "总运费", "总费用", "物流费用"),
    "vehicle_count": ("车次", "车辆数", "派车数"),
    "sign_rate": ("签收率", "签收达标率"),
    "unit_price": ("元/瓦", "单瓦", "运价", "报价", "单价"),
    "extra_fee": ("额外费用", "异常费用", "压车费", "放空费"),
}


@dataclass(frozen=True)
class OraclePreparation:
    """Oracle Engine 对单个验收 case 的准备结果。

    参数：
        oracle_status：转换后的 oracle 状态。
        years：识别出的可路由年份。
        metrics：识别出的指标编码。
        source_routes：年份到数据源的路由列表。
        missing_slots：缺失槽位，例如 year 或 metric。
        reasons：状态转换原因。
        expected_results：Excel Oracle 计算出的标准答案结果列表。
    返回值：无。
    """

    oracle_status: str
    years: list[int]
    metrics: list[str]
    source_routes: list[dict[str, Any]]
    missing_slots: list[str]
    reasons: list[str]
    expected_results: list[dict[str, Any]] = field(default_factory=list)


class OracleEngine(Protocol):
    """Oracle Engine 基础接口。

    参数：由实现类决定。
    返回值：由实现类返回 OraclePreparation。

    业务逻辑：
        P2.1 只定义可复用接口和数据源路由，不计算复杂业务指标，
        后续 Excel/MySQL 计算器可以在该接口后面继续扩展。
    """

    def prepare_case(self, case: Mapping[str, Any]) -> OraclePreparation:
        """准备单个标准化验收 case。

        参数：
            case：normalized_cases.json 中的一条 case。
        返回值：
            OraclePreparation 状态转换与数据源路由结果。
        """


def detect_logistics_metrics(question: str) -> list[str]:
    """识别物流标准答案候选指标。

    参数：
        question：业务问题文本。
    返回值：
        去重后的指标编码列表。

    业务逻辑：
        本阶段只判断是否具备可计算指标入口，不计算指标值。
        指标别名沿用物流一期常见口径，其中“运量”统一映射为 shipment_watt。
    """

    metrics: list[str] = []
    for metric, aliases in LOGISTICS_METRIC_ALIASES.items():
        if any(alias.lower() in question.lower() for alias in aliases):
            metrics.append(metric)
    return metrics


class LogisticsOracleEngine:
    """物流 Oracle Engine 基础实现。

    参数：
        excel_source_config：2023-2025 年历史 Excel 来源配置；为空时只执行 P2.1 路由准备逻辑。
    返回值：无。

    业务逻辑：
        默认执行年份数据源路由和 oracle_status 转换：
        logistics + 可识别年份 + 可识别指标 -> ORACLE_READY_CANDIDATE；
        logistics + 缺年份/缺指标 -> NEED_CLARIFICATION。
        当提供 excel_source_config 时，再对 2023-2025 Excel 路由执行 P2.2 月度指标计算。
    """

    def __init__(self, excel_source_config: LogisticsExcelSourceConfig | None = None) -> None:
        self.excel_source_config = excel_source_config
        self.excel_calculator = (
            LogisticsExcelOracleCalculator(LogisticsExcelWorkbookLoader(excel_source_config))
            if excel_source_config
            else None
        )

    def prepare_case(self, case: Mapping[str, Any]) -> OraclePreparation:
        """准备物流验收 case。

        参数：
            case：normalized_cases.json 中的一条 case。
        返回值：
            OraclePreparation。
        """

        question = str(case.get("question") or "")
        routes = route_logistics_sources(question)
        usable_routes = [route for route in routes if route.source in {EXCEL_SOURCE, MYSQL_SOURCE}]
        years = [route.year for route in usable_routes]
        metrics = detect_logistics_metrics(question)
        expected_results = self._calculate_excel_expected_results(case, question, usable_routes, metrics)
        missing_slots: list[str] = []
        reasons: list[str] = []

        if not usable_routes:
            missing_slots.append("year")
            reasons.append("未识别到 2023 年及之后可路由的物流业务年份。")
        if not metrics:
            missing_slots.append("metric")
            reasons.append("未识别到物流标准答案计算器可处理的指标。")

        if missing_slots:
            return OraclePreparation(
                oracle_status=NEED_CLARIFICATION,
                years=years,
                metrics=metrics,
                source_routes=[route.to_dict() for route in routes],
                missing_slots=missing_slots,
                reasons=reasons,
                expected_results=expected_results,
            )

        return OraclePreparation(
            oracle_status=ORACLE_READY_CANDIDATE,
            years=years,
            metrics=metrics,
            source_routes=[route.to_dict() for route in routes],
            missing_slots=[],
            reasons=["已识别物流年份和指标，可进入后续 Excel/MySQL 标准答案计算器候选队列。"],
            expected_results=expected_results,
        )

    def _calculate_excel_expected_results(
        self,
        case: Mapping[str, Any],
        question: str,
        routes: list[Any],
        metrics: list[str],
    ) -> list[dict[str, Any]]:
        """计算 2023-2025 Excel expected_result。

        参数：
            case：normalized case。
            question：业务问题文本。
            routes：已识别的数据源路由。
            metrics：已识别指标。
        返回值：
            expected_result 字典列表。

        业务逻辑：
            只有显式配置 Excel 来源时才执行真实计算，保证原 business-oracle 测试模式保持 P2.1 行为。
            本轮只计算 Excel 路由，2026+ MySQL 路由不在 P2.2 范围内。
        """

        if self.excel_calculator is None or not metrics:
            return []

        case_id = str(case.get("case_id") or "")
        results: list[dict[str, Any]] = []
        for route in routes:
            if route.source != EXCEL_SOURCE:
                continue
            month = extract_single_logistics_month(question, route.year)
            for metric in metrics:
                result = self.excel_calculator.calculate(
                    case_id=case_id,
                    metric=metric,
                    year=route.year,
                    month=month,
                )
                results.append(result.to_dict())
        return results


def extract_single_logistics_month(question: str, year: int) -> int | None:
    """识别单一业务月份。

    参数：
        question：业务问题文本。
        year：已识别业务年份。
    返回值：
        月份数字；未识别或识别到多个不同月份时返回 None。

    业务逻辑：
        P2.2 只支持单月指标计算。若问题包含多个月份，应留给后续 compare/趋势类计算器。
    """

    compact = re.sub(r"\s+", "", question)
    candidates: list[int] = []
    patterns = [
        rf"{year}年(\d{{1,2}})月",
        rf"{str(year)[2:]}年(\d{{1,2}})月",
        rf"{year}[-/](\d{{1,2}})",
    ]
    for pattern in patterns:
        for matched in re.finditer(pattern, compact):
            month = int(matched.group(1))
            if 1 <= month <= 12:
                candidates.append(month)

    if not candidates:
        for matched in re.finditer(r"(?<!\d)(\d{1,2})月", compact):
            month = int(matched.group(1))
            if 1 <= month <= 12:
                candidates.append(month)

    unique_months = sorted(set(candidates))
    return unique_months[0] if len(unique_months) == 1 else None


def convert_case_oracle_status(
    case: Mapping[str, Any],
    excel_source_config: LogisticsExcelSourceConfig | None = None,
) -> dict[str, Any]:
    """转换单条 normalized case 的 oracle 状态。

    参数：
        case：normalized_cases.json 中的一条 case。
        excel_source_config：可选 Excel 来源配置；为空时只做路由准备。
    返回值：
        带 oracle_engine 元数据的新 case 字典。

    业务逻辑：
        本轮只处理 logistics；BOM 和 unknown 保持导入阶段状态，
        避免 P2.1 误扩 BOM 或其他业务域。
    """

    converted = dict(case)
    original_status = str(case.get("oracle_status") or "")
    converted["import_oracle_status"] = original_status

    if original_status == "UNSUPPORTED":
        converted["oracle_engine"] = {
            "engine_version": ORACLE_ENGINE_VERSION,
            "handled": False,
            "reason": "导入阶段已判定为预测、开放分析或策略设计类问题，Oracle Engine 不降级改写该边界。",
        }
        return converted

    if case.get("domain") != "logistics":
        converted["oracle_engine"] = {
            "engine_version": ORACLE_ENGINE_VERSION,
            "handled": False,
            "reason": "P2.1 仅建设物流 Oracle Engine，非物流 case 保持导入阶段状态。",
        }
        return converted

    preparation = LogisticsOracleEngine(excel_source_config=excel_source_config).prepare_case(case)
    converted["oracle_status"] = preparation.oracle_status
    converted["oracle_reasons"] = preparation.reasons
    converted["oracle_engine"] = {
        "engine_version": ORACLE_ENGINE_VERSION,
        "handled": True,
        "years": preparation.years,
        "metrics": preparation.metrics,
        "source_routes": preparation.source_routes,
        "missing_slots": preparation.missing_slots,
    }
    if preparation.expected_results:
        converted["expected_results"] = preparation.expected_results
        converted["expected_result"] = preparation.expected_results[0]
        converted["oracle_engine"]["expected_result_count"] = len(preparation.expected_results)
    return converted


def convert_normalized_cases(
    normalized_cases: Mapping[str, Any],
    excel_source_config: LogisticsExcelSourceConfig | None = None,
) -> dict[str, Any]:
    """批量转换 normalized_cases.json 的 oracle 状态。

    参数：
        normalized_cases：业务问题导入阶段生成的标准化 cases。
        excel_source_config：可选 Excel 来源配置；为空时只做路由准备。
    返回值：
        Oracle Engine 处理后的 cases 对象。
    """

    items = [
        convert_case_oracle_status(case, excel_source_config=excel_source_config)
        for case in normalized_cases.get("items", [])
    ]
    route_counter: Counter[str] = Counter()
    expected_status_counter: Counter[str] = Counter()
    for case in items:
        engine_meta = case.get("oracle_engine") or {}
        for route in engine_meta.get("source_routes") or []:
            route_counter[str(route.get("source"))] += 1
        for expected_result in case.get("expected_results") or []:
            expected_status_counter[str(expected_result.get("calculation_status"))] += 1

    return {
        "generated_at": normalized_cases.get("generated_at"),
        "source_file": normalized_cases.get("source_file"),
        "oracle_engine_version": ORACLE_ENGINE_VERSION,
        "total_cases": len(items),
        "oracle_status_distribution": dict(Counter(str(case.get("oracle_status")) for case in items)),
        "source_route_distribution": dict(route_counter),
        "expected_result_status_distribution": dict(expected_status_counter),
        "items": items,
    }
