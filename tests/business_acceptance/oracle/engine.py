from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from source_router import EXCEL_SOURCE, MYSQL_SOURCE, route_logistics_sources


ORACLE_READY_CANDIDATE = "ORACLE_READY_CANDIDATE"
NEED_CLARIFICATION = "NEED_CLARIFICATION"
ORACLE_ENGINE_VERSION = "p2.1-logistics-source-router"

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
    返回值：无。
    """

    oracle_status: str
    years: list[int]
    metrics: list[str]
    source_routes: list[dict[str, Any]]
    missing_slots: list[str]
    reasons: list[str]


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
    """物流 Oracle Engine P2.1 基础实现。

    参数：无。
    返回值：无。

    业务逻辑：
        仅执行年份数据源路由和 oracle_status 转换：
        logistics + 可识别年份 + 可识别指标 -> ORACLE_READY_CANDIDATE；
        logistics + 缺年份/缺指标 -> NEED_CLARIFICATION。
    """

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
            )

        return OraclePreparation(
            oracle_status=ORACLE_READY_CANDIDATE,
            years=years,
            metrics=metrics,
            source_routes=[route.to_dict() for route in routes],
            missing_slots=[],
            reasons=["已识别物流年份和指标，可进入后续 Excel/MySQL 标准答案计算器候选队列。"],
        )


def convert_case_oracle_status(case: Mapping[str, Any]) -> dict[str, Any]:
    """转换单条 normalized case 的 oracle 状态。

    参数：
        case：normalized_cases.json 中的一条 case。
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

    preparation = LogisticsOracleEngine().prepare_case(case)
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
    return converted


def convert_normalized_cases(normalized_cases: Mapping[str, Any]) -> dict[str, Any]:
    """批量转换 normalized_cases.json 的 oracle 状态。

    参数：
        normalized_cases：业务问题导入阶段生成的标准化 cases。
    返回值：
        Oracle Engine 处理后的 cases 对象。
    """

    items = [convert_case_oracle_status(case) for case in normalized_cases.get("items", [])]
    route_counter: Counter[str] = Counter()
    for case in items:
        engine_meta = case.get("oracle_engine") or {}
        for route in engine_meta.get("source_routes") or []:
            route_counter[str(route.get("source"))] += 1

    return {
        "generated_at": normalized_cases.get("generated_at"),
        "source_file": normalized_cases.get("source_file"),
        "oracle_engine_version": ORACLE_ENGINE_VERSION,
        "total_cases": len(items),
        "oracle_status_distribution": dict(Counter(str(case.get("oracle_status")) for case in items)),
        "source_route_distribution": dict(route_counter),
        "items": items,
    }
