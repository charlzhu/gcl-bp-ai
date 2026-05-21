"""
产销存 ISP M8 灰度接管门禁。

业务逻辑：
    当 isp_m8_live_provider_enabled feature flag 开启时，先尝试 M6 live provider 链路；
    失败时返回 None 信号，由调用方（InventorySalesProductionQaService）fallback 到 M4 确定性链路。

规则：
    1. M8 门禁不暴露任何内部技术实现到用户可见回答。
    2. M8 失败只记录内部日志，不抛出用户可见异常。
    3. M8 成功时将 M6 链路结果转换为与 M4 完全相同的 QA 响应格式。
    4. M8 不修改物流/计划 BOM/功率预测主链路。
"""

from __future__ import annotations

import logging
from typing import Any

from backend.app.core.config import Settings
from backend.app.domains.business_analysis.schemas.inventory_sales_production_qa import (
    InventorySalesProductionQaResponse,
)
from backend.app.domains.business_analysis.schemas.inventory_sales_production_query import (
    InventorySalesProductionQueryRow,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.m6_live_provider_gate import (
    InventorySalesProductionM6CatalogRecallDocumentBuilder,
    InventorySalesProductionM6CatalogRecallService,
    InventorySalesProductionM6OpenAiSqlPlanProvider,
    InventorySalesProductionM6SqlPlanGenerator,
    InventorySalesProductionM6SqlPlanGenerationResult,
    InventorySalesProductionM6ReadonlyMiddleDbShadowExecutor,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.sql_plan import (
    InventorySalesProductionSqlPlan,
)

logger = logging.getLogger(__name__)

M8_LIVE_GATE_VERSION = "business_analysis_inventory_sales_production_m8_live_gate.v1"


class InventorySalesProductionM8LiveGate:
    """ISP M8 灰度接管门禁。

    参数：
        settings: 应用配置，用于读取 feature flag 和 LLM 配置。
        db_factory: 数据库会话工厂，用于只读中间库 shadow 查询。

    返回：
        try_ask() 返回 (success: bool, response: InventorySalesProductionQaResponse | None)。
    """

    def __init__(
        self,
        *,
        settings: Settings,
        db_factory: Any | None = None,
    ) -> None:
        """初始化 M8 门禁。

        参数：
            settings: 应用配置。
            db_factory: 数据库会话工厂，可为空（使用默认 SessionLocal）。
        返回：
            无。
        """
        self._settings = settings
        self._db_factory = db_factory

        # 延迟初始化 M6 组件，避免 import 时触发 LLM 连接。
        self._recall_service: InventorySalesProductionM6CatalogRecallService | None = None
        self._llm_provider: InventorySalesProductionM6OpenAiSqlPlanProvider | None = None
        self._generator: InventorySalesProductionM6SqlPlanGenerator | None = None
        self._executor: InventorySalesProductionM6ReadonlyMiddleDbShadowExecutor | None = None

    def _ensure_components(self) -> bool:
        """初始化 M6 组件；若任一组件不可用，返回 False 以触发 fallback。

        返回：
            True 表示所有组件就绪；False 表示应 fallback 到 M4。
        """
        if self._generator is not None:
            return True

        try:
            # 1. 构建召回文档
            builder = InventorySalesProductionM6CatalogRecallDocumentBuilder()
            documents = builder.build_documents()
            self._recall_service = InventorySalesProductionM6CatalogRecallService(documents)

            # 2. 初始化 LLM provider（读取项目配置）
            self._llm_provider = InventorySalesProductionM6OpenAiSqlPlanProvider(
                base_url=self._settings.llm_base_url,
                api_key=self._settings.llm_api_key,
                model=self._settings.llm_model,
            )
            if not self._llm_provider.is_available():
                logger.info("m8_live_gate_provider_not_available: LLM 配置不完整，M8 链路不可用")
                return False

            # 3. 初始化生成器（recall + provider + validator）
            self._generator = InventorySalesProductionM6SqlPlanGenerator(
                recall_service=self._recall_service,
                llm_provider=self._llm_provider,
            )

            # 4. 初始化只读 shadow executor
            self._executor = InventorySalesProductionM6ReadonlyMiddleDbShadowExecutor(
                session_factory=self._db_factory,
            )

            logger.info("m8_live_gate_components_ready: M8 所有组件初始化完成")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("m8_live_gate_components_init_failed: %s", exc)
            return False

    def try_ask(
        self,
        question: str,
        *,
        trace_id: str | None = None,
    ) -> tuple[bool, InventorySalesProductionQaResponse | None]:
        """尝试通过 M6 live provider 链路回答产销存问题。

        参数：
            question: 用户自然语言问题。
            trace_id: 请求链路 ID，可为空。

        返回：
            (success, response):
            - success=True: M6 链路成功，返回统一 QA 响应。
            - success=False: M6 链路失败，response 为 None，调用方必须 fallback 到 M4。
        """
        if not self._ensure_components():
            return False, None

        try:
            # 1. M6 生成 SQLPlan candidate
            generation = self._generator.generate(question) if self._generator else None
            if generation is None or not generation.validation.ok or generation.normalized_plan is None:
                self._log_generation_failure(generation, trace_id)
                return False, None

            # 2. 只读 shadow 执行
            if self._executor is None:
                return False, None
            rows = self._executor.execute(generation.normalized_plan)

            # 3. 将 shadow 结果转换为 QA 响应格式
            response = self._build_response_from_shadow_rows(
                question=question,
                trace_id=trace_id,
                normalized_plan=generation.normalized_plan,
                rows=rows,
            )
            logger.info(
                "m8_live_gate_success trace_id=%s row_count=%d",
                trace_id,
                len(rows),
            )
            return True, response

        except Exception as exc:  # noqa: BLE001
            # M8 失败只记录内部日志，不向用户暴露异常细节
            logger.warning(
                "m8_live_gate_failed trace_id=%s reason=%s",
                trace_id,
                str(exc),
            )
            return False, None

    @staticmethod
    def _log_generation_failure(
        generation: InventorySalesProductionM6SqlPlanGenerationResult | None,
        trace_id: str | None,
    ) -> None:
        """记录 M6 生成失败日志，不暴露内部技术细节到用户可见回答。"""
        error_codes = generation.error_codes if generation else ["generation_none"]
        logger.info(
            "m8_live_gate_generation_failed trace_id=%s error_codes=%s",
            trace_id,
            error_codes,
        )

    @staticmethod
    def _build_response_from_shadow_rows(
        *,
        question: str,
        trace_id: str | None,
        normalized_plan: InventorySalesProductionSqlPlan,
        rows: list[dict[str, Any]],
    ) -> InventorySalesProductionQaResponse:
        """将 M6 shadow 执行行转换为与 M4 相同格式的 QA 响应。

        说明：
            这里走的是 M6 → 只读执行 → 结构化事实的路径；
            响应格式与 M4 完全一致，确保前端流式体验不退化、用户不可见内部技术实现。
        """
        from decimal import Decimal, ROUND_HALF_UP

        _DECIMAL_SCALE = Decimal("0.00000001")

        # 维度中文标签映射（与 M4 qa_service.py 保持一致）
        _DIMENSION_LABELS = {
            "base_name": "基地",
            "factory_name": "工厂",
            "model_type": "版型",
            "production_mode": "生产模式",
            "trade_scope": "交易范围",
            "business_month": "月份",
        }

        def _format_decimal(value):
            if value is None:
                return ""
            decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
            return str(decimal_value.quantize(_DECIMAL_SCALE, rounding=ROUND_HALF_UP))

        def _format_months(months):
            if not months:
                return ""
            return ",".join(f"{int(month)}月" for month in months)

        def _safe_business_text(text, fallback):
            candidate = (text or "").strip()
            forbidden = (
                "sql", "query_key", "planner", "guardrail", "schema",
                "raw", "debug", "llm", "ba_isp", "metric_code",
            )
            if not candidate or any(word in candidate.lower() for word in forbidden):
                return fallback
            return candidate

        # 构建业务化摘要
        answer_summary = _build_business_summary(normalized_plan, rows)
        status_payload = {
            "code": "OK",
            "message": "查询成功",
            "success": True,
            "severity": "success",
        }

        # 构建结果表（与 M4 格式一致）
        query_rows = [
            InventorySalesProductionQueryRow(
                metric_code=(normalized_plan.metrics or [""])[0],
                metric_name=row.get("metric_name", (normalized_plan.metrics or [""])[0]),
                value_decimal=_safe_decimal(row.get("value_decimal")),
                dimensions=row.get("dimensions") if isinstance(row.get("dimensions"), dict) else None,
                months_covered=row.get("months_covered", []) if isinstance(row.get("months_covered"), list) else [],
                unit_standard=row.get("unit_standard", "MW"),
                aggregation_type=normalized_plan.calculation_policy or row.get("aggregation_type", "sum"),
                row_count=int(row.get("row_count", 0)),
            )
            for row in rows
        ]

        # 提取维度列
        dimension_keys = ["base_name", "factory_name", "model_type", "production_mode", "trade_scope", "business_month"]
        present_keys = {key for row in query_rows for key in (row.dimensions or {}) if key in _DIMENSION_LABELS}
        ordered_keys = [key for key in dimension_keys if key in present_keys]

        columns = [_DIMENSION_LABELS[key] for key in ordered_keys]
        columns.extend(["期间", "指标", "数值", "单位", "覆盖月份", "数据行数"])

        period_label = _period_label_from_plan(normalized_plan)
        table_rows: list[dict[str, Any]] = []
        for row in query_rows:
            table_row: dict[str, Any] = {}
            for key in ordered_keys:
                table_row[_DIMENSION_LABELS[key]] = row.dimensions.get(key) if row.dimensions else None
            table_row.update({
                "期间": period_label or _format_months(row.months_covered),
                "指标": row.metric_name,
                "数值": _format_decimal(row.value_decimal),
                "单位": "%" if row.unit_standard == "percent" else row.unit_standard,
                "覆盖月份": _format_months(row.months_covered),
                "数据行数": row.row_count,
            })
            table_rows.append(table_row)

        result_table = {"columns": columns, "rows": table_rows} if table_rows else None

        # 构建 presentation（与 M4 格式一致）
        highlights = []
        if query_rows:
            first = query_rows[0]
            highlights.append({
                "label": first.metric_name,
                "value": _format_decimal(first.value_decimal),
                "unit": "%" if first.unit_standard == "percent" else first.unit_standard,
            })

        presentation = {
            "display_type": "business_analysis_result" if result_table else "narrative",
            "title": "产销存经营分析",
            "answer": answer_summary,
            "highlights": highlights,
            "table_spec": result_table,
            "caveats": [],
        }

        return InventorySalesProductionQaResponse(
            question=question,
            classification="A",
            status=status_payload,
            answer_summary=_safe_business_text(answer_summary, fallback=status_payload["message"]),
            result_table=result_table,
            presentation=presentation,
            warnings=[],
            trace_id=trace_id,
        )


def _safe_decimal(value: Any) -> Any:
    """安全转换 shadow 返回值为 Decimal 或保持原值。"""
    if value is None:
        return None
    from decimal import Decimal, InvalidOperation

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return value


def _build_business_summary(plan: InventorySalesProductionSqlPlan, rows: list[dict[str, Any]]) -> str:
    """基于 SQLPlan 和执行结果构建业务化摘要。

    说明：摘要不暴露表名、字段名、query_key 等内部技术实现。
    """
    if not rows:
        metric_label = _metric_business_label(plan)
        year_info = _year_business_label(plan)
        return f"{year_info}{metric_label}查询结果为空，请调整条件后重试。"

    metric_label = _metric_business_label(plan)
    year_info = _year_business_label(plan)
    row_count = len(rows)

    # 尝试从结果行中提取值
    first_row = rows[0]
    value = first_row.get("value_decimal") if rows else None
    unit = first_row.get("unit_standard", "") if rows else ""

    if value is not None:
        return f"{year_info}{metric_label}为 {_format_value(value)} {unit}，共 {row_count} 条记录。"

    return f"{year_info}{metric_label}查询成功，共 {row_count} 条记录。"


def _metric_business_label(plan: InventorySalesProductionSqlPlan) -> str:
    """从 SQLPlan 提取指标业务化标签。"""
    metric_map = {
        "shipment_volume": "发货量",
        "production_actual": "实际产量",
        "production_actual_including_oem": "实际产量（含代工）",
        "production_budget": "预算产量",
        "production_budget_achievement_rate": "预算达成率",
        "ending_inventory_volume": "期末库存",
        "consigned_inventory_volume": "寄存仓库存",
        "production_sales_ratio": "产销率",
    }
    metrics = plan.metrics or []
    labels = [metric_map.get(m, str(m)) for m in metrics if m]
    return "、".join(labels) if labels else "指标"


def _year_business_label(plan: InventorySalesProductionSqlPlan) -> str:
    """从 SQLPlan 提取年份业务化标签。"""
    if plan.year:
        return f"{plan.year}年"
    return ""


def _format_value(value: Any) -> str:
    """格式化数值为业务化展示。"""
    from decimal import Decimal

    try:
        d = Decimal(str(value))
        # 格式化：保留适当小数位
        formatted = f"{d:.4f}".rstrip("0").rstrip(".")
        return formatted
    except Exception:
        return str(value)


def _period_label_from_plan(plan: InventorySalesProductionSqlPlan) -> str | None:
    """从 SQLPlan 提取期间标签。"""
    if plan.period_type == "year" and plan.year:
        return f"{plan.year}年"
    if plan.period_type == "month" and plan.month:
        return f"{plan.year}年{plan.month}月"
    if plan.period_type == "quarter" and plan.quarter:
        return f"{plan.year}年Q{plan.quarter}"
    return None


__all__ = [
    "InventorySalesProductionM8LiveGate",
    "M8_LIVE_GATE_VERSION",
]
