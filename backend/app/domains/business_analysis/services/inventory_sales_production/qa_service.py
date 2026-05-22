from __future__ import annotations

import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
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
from backend.app.domains.business_analysis.services.inventory_sales_production.nl2sql_query_planner import (
    InventorySalesProductionNl2SqlQueryPlanner,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.query_executor import (
    InventorySalesProductionQueryExecutor,
)
from backend.app.domains.logistics.repositories.query_repository import LogisticsQueryRepository
from backend.app.domains.logistics.services.nl2sql.m15_grayscale_gate import (
    LogisticsNl2SqlGrayscaleConfig,
    LogisticsNl2SqlGrayscaleGate,
)
from backend.app.domains.logistics.services.nl2sql.live_shadow_adapter import (
    LogisticsNl2SqlLiveShadowAdapter,
)

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
        5. M8 新增 live gate 注入点：ask_with_live_gate 支持 off/shadow/assist 三种模式。
    """

    def __init__(
        self,
        db: Session,
        *,
        planner: InventorySalesProductionNlQueryPlanner | None = None,
        nl2sql_planner: InventorySalesProductionNl2SqlQueryPlanner | None = None,
        executor: InventorySalesProductionQueryExecutor | None = None,
        query_log_repository: LogisticsQueryRepository | None = None,
        live_gate_enabled: bool = False,
        live_gate_mode: str = "off",
        live_gate_runner: Any = None,
        live_gate_artifact_dir: Path | None = None,
    ) -> None:
        """初始化产销存 QA 服务。

        参数：
            db: 当前数据库会话。
            planner: 自然语言规则规划器，测试可注入。
            nl2sql_planner: LLM Catalog Recall 规划器（S3），仅在 live_gate 模式启用时使用。
            executor: M3 QueryExecutor，测试可注入。
            query_log_repository: 统一查询历史仓储，失败时不影响主链路。
            live_gate_enabled: M8 feature flag 是否启用。
            live_gate_mode: M8 feature flag 模式（off/shadow/assist/nl2sql）。
            live_gate_runner: 可注入的 M6 live shadow gate runner。
            live_gate_artifact_dir: M8 shadow 模式下的验收材料目录。
        返回：
            无返回值。
        """

        self.db = db
        self.planner = planner or InventorySalesProductionNlQueryPlanner()
        self.nl2sql_planner = nl2sql_planner or InventorySalesProductionNl2SqlQueryPlanner()
        self.executor = executor or InventorySalesProductionQueryExecutor(db)
        self.query_log_repository = query_log_repository or LogisticsQueryRepository()
        self.live_gate_enabled = live_gate_enabled
        self.live_gate_mode = live_gate_mode
        self.live_gate_runner = live_gate_runner
        self.live_gate_artifact_dir = live_gate_artifact_dir

    def ask(self, question: str, *, trace_id: str | None = None) -> InventorySalesProductionQaResponse:
        """回答一个产销存自然语言问题（NL2SQL 主线模式，已移除规则引擎回退）。

        参数：
            question: 用户原始自然语言问题。
            trace_id: 请求链路 ID，可为空。
        返回：
            InventorySalesProductionQaResponse，包含业务化摘要、结果表和状态。
        """

        # NL2SQL 主线：先执行 NL2SQL shadow，成功则直接返回
        response: InventorySalesProductionQaResponse | None = None
        try:
            import os
            from dotenv import load_dotenv
            load_dotenv(os.getenv("BACKEND_ENV_PATH", ""), override=True)
            config = LogisticsNl2SqlGrayscaleConfig.from_env()
            if config.enabled_domains and "business_analysis" in config.enabled_domains:
                adapter = LogisticsNl2SqlLiveShadowAdapter()
                shadow_summary = adapter.run_shadow(
                    question=question,
                    trace_id=trace_id,
                    domain="business_analysis",
                )
                if shadow_summary.enabled and shadow_summary.status in ("success", "skipped"):
                    response = InventorySalesProductionQaResponse(
                        question=question,
                        classification="A",
                        status={"code": "SUCCESS", "message": "NL2SQL 主线模式", "success": True},
                        answer_summary=shadow_summary.error_message or "NL2SQL 主线模式",
                        presentation={"answer_summary": shadow_summary.error_message or "NL2SQL 主线模式"},
                        warnings=["NL2SQL 主线模式：本回答由 NL2SQL 链路生成。"],
                    )
        except Exception as exc:
            logger.warning("nl2sql_mainline_failed trace_id=%s %s", trace_id, exc)

        if response is not None:
            self._write_history_snapshot(question=question, trace_id=trace_id, response=response)
            return response

        # NL2SQL 不可用 → 返回错误（不再降级到规则引擎）
        response = self._build_error_response(
            question=question,
            trace_id=trace_id,
            message="当前 NL2SQL 链路暂不可用，请稍后再试。",
        )
        self._write_history_snapshot(question=question, trace_id=trace_id, response=response)
        return response

    def ask_with_live_gate(
        self,
        question: str,
        *,
        trace_id: str | None = None,
    ) -> InventorySalesProductionQaResponse:
        """M8 可选 live gate / S3 NL2SQL / S8 NL2SQL-Extended 问答入口。

        参数：
            question: 用户原始自然语言问题。
            trace_id: 请求链路 ID。
        返回：
            InventorySalesProductionQaResponse；gate/NL2SQL 失败时自动 fallback 到 M4 确定性结果。

        业务逻辑：
            off 模式：与 ask() 完全相同，不走 gate，使用规则规划器。
            shadow 模式：使用规则规划器，NL2SQL 结果仅记录到日志。
            assist 模式：使用规则规划器，gate 结果仅记录（向后兼容 M6）。
            nl2sql 模式：使用 S3 LLM Catalog Recall 规划器（Nl2SqlQueryPlanner），
                    成功时返回 NL2SQL 结果，失败时 fallback 到规则规划器。
            nl2sql_extended 模式：使用 S7 LLM 完整 SQLPlan 规划器（Nl2SqlSqlPlanPlanner），
                    输出完整 SqlPlanCandidate 经 Validator 校验后执行，
                    失败时 fallback 到规则规划器。
        """

        if not self.live_gate_enabled or self.live_gate_mode == "off":
            return self.ask(question=question, trace_id=trace_id)

        # nl2sql / nl2sql_extended 模式：都使用 NL2SQL 规划器（接口兼容）
        if self.live_gate_mode in ("nl2sql", "nl2sql_extended"):
            return self._ask_with_nl2sql_planner(question=question, trace_id=trace_id)

        # shadow/assist 模式：向后兼容 M6（规则规划器 + gate 记录）
        return self._ask_with_shadow_gate(question=question, trace_id=trace_id)

    def _ask_with_nl2sql_planner(
        self,
        question: str,
        *,
        trace_id: str | None = None,
    ) -> InventorySalesProductionQaResponse:
        """使用 LLM Catalog Recall 规划器（S3）回答问题。

        参数：
            question: 用户自然语言问题。
            trace_id: 请求链路 ID。
        返回：
            InventorySalesProductionQaResponse；LLM 规划器失败时自动 fallback 到规则规划器。
        """
        # 尝试 LLM 规划器
        try:
            plan = self.nl2sql_planner.build_plan(question)
            query_result = self.executor.execute(plan)
            response = self._build_response_from_query_result(
                question=question,
                trace_id=trace_id,
                query_result=query_result,
            )
            logger.info("isp_nl2sql_planner_success question=%s", question[:50])
            self._write_history_snapshot(question=question, trace_id=trace_id, response=response)
            return response
        except InventorySalesProductionPlanningError:
            # LLM 规划器返回 clarification/unsupported —— fallback 到规则规划器
            pass
        except Exception:  # noqa: BLE001
            # LLM 规划器异常 —— fallback 到规则规划器
            logger.warning("isp_nl2sql_planner_fallback question=%s", question[:50], exc_info=True)

        # fallback 到规则规划器
        try:
            plan = self.planner.build_plan(question)
            query_result = self.executor.execute(plan)
            response = self._build_response_from_query_result(
                question=question,
                trace_id=trace_id,
                query_result=query_result,
            )
            logger.info("isp_nl2sql_fallback_rule_success question=%s", question[:50])
            self._write_history_snapshot(question=question, trace_id=trace_id, response=response)
            return response
        except InventorySalesProductionPlanningError as exc:
            response = self._build_blocked_response(
                question=question,
                trace_id=trace_id,
                status=exc.status,
                message=exc.message,
            )
            self._write_history_snapshot(question=question, trace_id=trace_id, response=response)
            return response
        except Exception as exc:  # noqa: BLE001
            logger.exception("inventory_sales_production_qa_failed trace_id=%s", trace_id)
            response = self._build_error_response(question=question, trace_id=trace_id, message=str(exc))
            self._write_history_snapshot(question=question, trace_id=trace_id, response=response)
            return response

    def _ask_with_shadow_gate(
        self,
        question: str,
        *,
        trace_id: str | None = None,
    ) -> InventorySalesProductionQaResponse:
        """M6 live shadow gate 模式（向后兼容）。

        参数：
            question: 用户原始自然语言问题。
            trace_id: 请求链路 ID。
        返回：
            InventorySalesProductionQaResponse；gate 失败时自动 fallback 到 M4 确定性结果。

        业务逻辑：
            shadow 模式：M4 确定性结果作为正式答案，gate 结果仅记录。
            assist 模式：gate 成功时记录，失败时退回到 M4 结果。
        """

        # 先获取 M4 确定性结果（基线安全结果）
        m4_response = self.ask(question=question, trace_id=trace_id)

        if not self.live_gate_runner:
            return m4_response

        # 执行 M6 live gate（异常不中断，fallback 到 M4）
        try:
            from backend.app.domains.business_analysis.services.inventory_sales_production.m6_live_provider_gate import (
                InventorySalesProductionM6LiveShadowSample,
            )

            samples = [
                InventorySalesProductionM6LiveShadowSample(
                    sample_id=f"m8_live_gate_{hash(question) % 100000:05d}",
                    question=question,
                    expected_status="matched",
                )
            ]
            artifact_dir = self.live_gate_artifact_dir or Path("/tmp/hermes/m8_live_gate")
            run = self.live_gate_runner.run(samples=samples, artifact_dir=artifact_dir)
            gate_ok = bool(
                run.report.get("expected_status_mismatch_count") == 0
                and run.report.get("success_count", 0) > 0
            )
        except Exception:  # noqa: BLE001
            gate_ok = False

        if self.live_gate_mode == "shadow":
            # shadow 模式：M4 结果不变，gate 结果仅记录到日志
            logger.info(
                "isp_m8_live_gate_shadow question=%s gate_ok=%s",
                question[:50],
                gate_ok,
            )
            return m4_response

        if self.live_gate_mode == "assist" and gate_ok:
            # assist 模式且 gate 成功：返回 M4 结果（gate 成功但未正式接入）
            # 后续 M8 验收通过后，可在此处将门禁结果替换为正式 NL2SQL 结果
            logger.info(
                "isp_m8_live_gate_assist_gate_ok question=%s",
                question[:50],
            )

        return m4_response

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
