from __future__ import annotations

import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy.orm import Session

from backend.app.domains.business_analysis.schemas.inventory_sales_production_qa import (
    InventorySalesProductionQaClassification,
    InventorySalesProductionQaResponse,
)
from backend.app.domains.business_analysis.schemas.inventory_sales_production_query import (
    InventorySalesProductionQueryResult,
    InventorySalesProductionQueryRow,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.nl_query_planner import (
    InventorySalesProductionNlQueryPlanner,
    InventorySalesProductionPlanningError,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.query_executor import (
    InventorySalesProductionQueryExecutor,
)
from backend.app.domains.logistics.repositories.query_repository import LogisticsQueryRepository

logger = logging.getLogger(__name__)

_DECIMAL_SCALE = Decimal("0.00000001")
_DIMENSION_LABELS = {
    "base_name": "基地",
    "factory_name": "工厂",
    "model_type": "版型",
    "production_mode": "生产模式",
    "trade_scope": "交易范围",
    "business_month": "月份",
}


class InventorySalesProductionQaService:
    """产销存自然语言问答服务。

    业务边界：
        1. M4 紧急接入阶段只负责把自然语言转换成受控 QueryPlan；
        2. 业务事实、聚合、预算达成率等计算全部复用 M3 QueryExecutor；
        3. 服务层只整理用户可见状态、摘要、表格和追溯日志；
        4. 不让 LLM 直接生成 SQL、直接计算指标或直接读取 Excel/数据库表。
        5. ISP M8：当 isp_m8_live_provider_enabled 开启时，优先走 M6 live provider 链路，
           失败时自动 fallback 到 M4 确定性链路。
    """

    def __init__(
        self,
        db: Session,
        *,
        planner: InventorySalesProductionNlQueryPlanner | None = None,
        executor: InventorySalesProductionQueryExecutor | None = None,
        query_log_repository: LogisticsQueryRepository | None = None,
        settings: Any | None = None,
    ) -> None:
        """初始化产销存 QA 服务。

        参数：
            db: 当前数据库会话。
            planner: 自然语言临时规划器，测试可注入。
            executor: M3 QueryExecutor，测试可注入。
            query_log_repository: 统一查询历史仓储，失败时不影响主链路。
            settings: 应用配置，ISP M8 灰度接管时必需。
        返回：
            无返回值。
        """

        self.db = db
        self.planner = planner or InventorySalesProductionNlQueryPlanner()
        self.executor = executor or InventorySalesProductionQueryExecutor(db)
        self.query_log_repository = query_log_repository or LogisticsQueryRepository()
        self._settings = settings

        # M8 灰度接管门禁（延迟初始化，避免 import 时触发 LLM 连接）
        self._m8_gate: Any = None

    def ask(self, question: str, *, trace_id: str | None = None) -> InventorySalesProductionQaResponse:
        """回答一个产销存自然语言问题。

        参数：
            question: 用户原始自然语言问题。
            trace_id: 请求链路 ID，可为空。
        返回：
            InventorySalesProductionQaResponse，包含业务化摘要、结果表和状态。
        """

        # ISP M8：feature flag 开启时优先走 M6 live provider 链路
        if self._is_m8_enabled():
            m8_success, m8_response = self._try_m8_ask(question=question, trace_id=trace_id)
            if m8_success and m8_response is not None:
                self._write_history_snapshot(question=question, trace_id=trace_id, response=m8_response)
                return m8_response
            # M8 失败：记录内部日志后 fallback 到 M4 确定性链路
            logger.info(
                "m8_fallback_to_m4 trace_id=%s question=%s",
                trace_id,
                question[:80],
            )

        # M4 确定性链路（现有逻辑不变）
        try:
            plan = self.planner.build_plan(question)
            query_result = self.executor.execute(plan)
            response = self._build_response_from_query_result(
                question=question,
                trace_id=trace_id,
                query_result=query_result,
            )
        except InventorySalesProductionPlanningError as exc:
            response = self._build_blocked_response(
                question=question,
                trace_id=trace_id,
                status=exc.status,
                message=exc.message,
            )
        except Exception as exc:  # noqa: BLE001
            # 业务问答主链路 fail closed：异常只返回业务化错误，不暴露表名、字段、SQL 或栈信息。
            logger.exception("inventory_sales_production_qa_failed trace_id=%s", trace_id)
            response = self._build_error_response(question=question, trace_id=trace_id, message=str(exc))

        self._write_history_snapshot(question=question, trace_id=trace_id, response=response)
        return response

    def _is_m8_enabled(self) -> bool:
        """判断 ISP M8 feature flag 是否开启。

        返回：
            True 当 isp_m8_live_provider_enabled 配置为 True 且 settings 已注入时。
        """
        if self._settings is None:
            return False
        return bool(getattr(self._settings, "isp_m8_live_provider_enabled", False))

    def _try_m8_ask(
        self,
        *,
        question: str,
        trace_id: str | None,
    ) -> tuple[bool, Any]:
        """尝试通过 M8 灰度接管门禁回答问题。

        返回：
            (success, qa_response_or_none)
        """
        try:
            from backend.app.domains.business_analysis.services.inventory_sales_production.m8_live_gate import (
                InventorySalesProductionM8LiveGate,
            )

            if self._m8_gate is None:
                self._m8_gate = InventorySalesProductionM8LiveGate(settings=self._settings)
            return self._m8_gate.try_ask(question=question, trace_id=trace_id)
        except Exception as exc:  # noqa: BLE001
            # M8 异常不向用户暴露，静默 fallback 到 M4
            logger.warning("m8_gate_unexpected_error trace_id=%s reason=%s", trace_id, str(exc))
            return False, None

    def write_error_log(self, *, question: str, trace_id: str | None, message: str) -> int:
        """写入 API 异常兜底日志。

        参数：
            question: 用户原始问题。
            trace_id: 请求链路 ID。
            message: 异常摘要，仅进入内部日志快照。
        返回：
            新写入的日志 ID；失败返回 0。
        """

        response = self._build_error_response(question=question, trace_id=trace_id, message=message)
        return self._write_history_snapshot(question=question, trace_id=trace_id, response=response)

    def _build_response_from_query_result(
        self,
        *,
        question: str,
        trace_id: str | None,
        query_result: InventorySalesProductionQueryResult,
    ) -> InventorySalesProductionQaResponse:
        """把 M3 QueryExecutor 结果转换为 M4 QA 响应。"""

        classification, status_payload = self._map_status(query_result.status, query_result.answer_summary)
        result_table = self._build_result_table(query_result.rows, period_label=query_result.period_label)
        answer_summary = self._safe_business_text(query_result.answer_summary, fallback=status_payload["message"])
        if query_result.status != "success":
            result_table = None
        presentation = self._build_presentation(
            answer_summary=answer_summary,
            result_table=result_table,
            rows=query_result.rows,
            warnings=query_result.warnings,
        )
        return InventorySalesProductionQaResponse(
            question=question,
            classification=classification,
            status=status_payload,
            answer_summary=answer_summary,
            result_table=result_table,
            presentation=presentation,
            warnings=query_result.warnings,
            trace_id=trace_id,
        )

    def _build_blocked_response(
        self,
        *,
        question: str,
        trace_id: str | None,
        status: str,
        message: str,
    ) -> InventorySalesProductionQaResponse:
        """构造规划阶段澄清/不支持响应。"""

        classification, status_payload = self._map_status(status, message)
        answer_summary = self._safe_business_text(message, fallback=status_payload["message"])
        return InventorySalesProductionQaResponse(
            question=question,
            classification=classification,
            status=status_payload,
            answer_summary=answer_summary,
            result_table=None,
            presentation=self._build_presentation(
                answer_summary=answer_summary,
                result_table=None,
                rows=[],
                warnings=[],
            ),
            warnings=[],
            trace_id=trace_id,
        )

    def _build_error_response(
        self,
        *,
        question: str,
        trace_id: str | None,
        message: str,
    ) -> InventorySalesProductionQaResponse:
        """构造系统异常响应，避免向用户暴露内部异常。"""

        _ = message  # 异常原文只写 Python 日志，不进入用户可见结果。
        status_payload = {
            "code": "EXECUTION_ERROR",
            "message": "当前产销存问答执行失败，请稍后重试；如持续失败，请联系管理员。",
            "success": False,
            "severity": "error",
        }
        answer_summary = status_payload["message"]
        return InventorySalesProductionQaResponse(
            question=question,
            classification="D",
            status=status_payload,
            answer_summary=answer_summary,
            result_table=None,
            presentation=self._build_presentation(
                answer_summary=answer_summary,
                result_table=None,
                rows=[],
                warnings=[],
            ),
            warnings=[],
            trace_id=trace_id,
        )

    def _map_status(
        self,
        status: str,
        message: str,
    ) -> tuple[InventorySalesProductionQaClassification, dict[str, Any]]:
        """将执行器状态映射为前端统一业务状态。"""

        if status == "success":
            return "A", {"code": "OK", "message": "查询成功", "success": True, "severity": "success"}
        if status == "clarification":
            return "B", {
                "code": "CLARIFICATION_REQUIRED",
                "message": self._safe_business_text(message, fallback="请补充查询条件后再试。"),
                "success": False,
                "severity": "warning",
            }
        if status == "empty_result":
            return "C", {
                "code": "NO_DATA",
                "message": self._safe_business_text(message, fallback="当前条件下没有找到产销存数据。"),
                "success": False,
                "severity": "info",
            }
        return "C", {
            "code": "UNSUPPORTED",
            "message": self._safe_business_text(message, fallback="当前暂不支持该产销存问题。"),
            "success": False,
            "severity": "warning",
        }

    def _build_result_table(
        self,
        rows: list[InventorySalesProductionQueryRow],
        *,
        period_label: str | None,
    ) -> dict[str, Any] | None:
        """把结构化事实行转换为用户可见结果表。

        说明：
            维度字段在这里统一转换为中文业务标签，避免前端展示内部编码。
        """

        if not rows:
            return None
        dimension_keys = self._ordered_dimension_keys(rows)
        columns = [_DIMENSION_LABELS[key] for key in dimension_keys]
        columns.extend(["期间", "指标", "数值", "单位", "覆盖月份", "数据行数"])
        table_rows: list[dict[str, Any]] = []
        for row in rows:
            table_row: dict[str, Any] = {}
            for key in dimension_keys:
                table_row[_DIMENSION_LABELS[key]] = row.dimensions.get(key) if row.dimensions else None
            table_row.update(
                {
                    "期间": period_label or self._format_months(row.months_covered),
                    "指标": row.metric_name,
                    "数值": self._format_decimal(row.value_decimal),
                    "单位": "%" if row.unit_standard == "percent" else row.unit_standard,
                    "覆盖月份": self._format_months(row.months_covered),
                    "数据行数": row.row_count,
                }
            )
            table_rows.append(table_row)
        return {"columns": columns, "rows": table_rows}

    def _build_presentation(
        self,
        *,
        answer_summary: str,
        result_table: dict[str, Any] | None,
        rows: list[InventorySalesProductionQueryRow],
        warnings: list[str],
    ) -> dict[str, Any]:
        """生成前端统一智能问答展示结构。"""

        highlights = []
        if rows:
            first_row = rows[0]
            highlights.append(
                {
                    "label": first_row.metric_name,
                    "value": self._format_decimal(first_row.value_decimal),
                    "unit": "%" if first_row.unit_standard == "percent" else first_row.unit_standard,
                }
            )
        return {
            "display_type": "business_analysis_result" if result_table else "narrative",
            "title": "产销存经营分析",
            "answer": answer_summary,
            "highlights": highlights,
            "table_spec": result_table,
            "caveats": warnings,
        }

    @staticmethod
    def _ordered_dimension_keys(rows: list[InventorySalesProductionQueryRow]) -> list[str]:
        """按固定顺序收集结果中出现的维度编码。"""

        ordered = ["base_name", "factory_name", "model_type", "production_mode", "trade_scope", "business_month"]
        present = {key for row in rows for key in (row.dimensions or {}) if key in _DIMENSION_LABELS}
        return [key for key in ordered if key in present]

    @staticmethod
    def _format_decimal(value: Decimal | None) -> str:
        """格式化数值，统一保留 8 位小数以便追溯。"""

        if value is None:
            return ""
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
        return str(decimal_value.quantize(_DECIMAL_SCALE, rounding=ROUND_HALF_UP))

    @staticmethod
    def _format_months(months: list[int]) -> str:
        """格式化覆盖月份。"""

        if not months:
            return ""
        return ",".join(f"{int(month)}月" for month in months)

    @staticmethod
    def _safe_business_text(text: str, *, fallback: str) -> str:
        """兜底清理用户可见文案中的内部技术痕迹。

        说明：
            产销存问答结果不应出现 SQL、表名、字段名、query_key、planner、raw/debug 等内部实现词。
        """

        candidate = (text or "").strip()
        forbidden = (
            "sql",
            "query_key",
            "planner",
            "guardrail",
            "schema",
            "raw",
            "debug",
            "llm",
            "ba_isp",
            "metric_code",
        )
        if not candidate or any(word in candidate.lower() for word in forbidden):
            return fallback
        return candidate

    def _write_history_snapshot(
        self,
        *,
        question: str,
        trace_id: str | None,
        response: InventorySalesProductionQaResponse,
    ) -> int:
        """写入统一查询历史快照。

        参数：
            question: 用户原始问题。
            trace_id: 请求链路 ID。
            response: 已生成的产销存 QA 响应。
        返回：
            新写入日志 ID；日志失败返回 0 且不影响问答主流程。
        """

        try:
            result_count = len((response.result_table or {}).get("rows", []))
            response_snapshot = response.model_dump(mode="json")
            payload_snapshot = {
                "question": question,
                "request_payload": {"question": question, "domain": "business_analysis", "sub_domain": "inventory_sales_production"},
                "response_meta": {
                    "question": question,
                    "domain": "business_analysis",
                    "sub_domain": "inventory_sales_production",
                    "mode": "inventory_sales_production_qa",
                    "status": response.status,
                    "result_count": result_count,
                    "trace_ready": bool(trace_id),
                },
                "query_result": {
                    **response_snapshot,
                    "query_type": "inventory_sales_production_qa",
                    "execution_mode": "query_plan_executor_bridge",
                    "item_count": result_count,
                },
            }
            log_id = self.query_log_repository.write_query_log(
                self.db,
                {
                    "trace_id": trace_id or "local-dev",
                    "query_type": "BA_ISP_QA",
                    "question_text": question,
                    "request_payload": json.dumps(payload_snapshot, ensure_ascii=False, default=str),
                    "route_type": "business_analysis_qa",
                    "metric_type": "inventory_sales_production",
                    "result_count": result_count,
                    "status": "SUCCESS" if response.status.get("success") else "FAILED",
                    "message": response.status.get("message") or response.answer_summary,
                },
            )
            self.db.commit()
            return log_id
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            logger.warning("write inventory sales production qa log failed: %s", exc)
            return 0


__all__ = ["InventorySalesProductionQaService"]
