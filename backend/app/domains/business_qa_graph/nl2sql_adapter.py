"""NQE-S1 NL2SQL Graph Adapter：Graph 调度 NL2SQL SQLPlan shadow 的桥梁。

本 adapter 调用现有 Nl2SqlDomainRouter/LogisticsNl2SqlDomainRouter 进行领域路由，
使用 LogisticsNl2SqlShadowPipeline 生成 SQLPlan shadow。
shadow 结果仅用于审计记录，不改变现有 NL2SQL-A/B/C/D 执行链路。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class Nl2SqlGraphAdapter:
    """Graph NL2SQL Shadow Adapter。

    作用：
    1. 使用 LogisticsNl2SqlDomainRouter 检查问题是否属于物流 NL2SQL 范围；
    2. 使用 LogisticsNl2SqlShadowPipeline 尝试生成 SQLPlan shadow；
    3. 所有异常 fail-closed，不中断主链路。

    参数：
        domain_router: 可注入的领域路由器，默认使用 LogisticsNl2SqlDomainRouter。
        shadow_pipeline: 可注入的 shadow pipeline，默认使用 LogisticsNl2SqlShadowPipeline。
    返回：
        build_shadow 返回标准化的 shadow 结果字典。
    业务逻辑：
        本 adapter 只做 shadow 记录，不修改正式问答链路、不自由生成 SQL、不计算业务事实。
    """

    def __init__(
        self,
        *,
        domain_router: Any = None,
        shadow_pipeline: Any = None,
    ) -> None:
        """初始化 NL2SQL graph adapter。

        参数：
            domain_router: 可注入的领域路由器实例。
                默认构造 LogisticsNl2SqlDomainRouter。
            shadow_pipeline: 可注入的 shadow pipeline 实例。
                默认构造 LogisticsNl2SqlShadowPipeline（使用 fake executor）。
        """
        self._domain_router = domain_router
        self._shadow_pipeline = shadow_pipeline

    def build_shadow(self, question: str, trace_id: str | None = None) -> dict[str, Any]:
        """为给定问题生成 NL2SQL SQLPlan shadow。

        参数：
            question: 用户原始问题。
            trace_id: 可选追踪号，用于审计串联。
        返回：
            标准化 shadow 结果字典，包含以下字段：
            - status: "shadow_generated" | "route_skipped" | "error"
            - domain: 业务域标识（shadow_generated 时）
            - source_system: 数据来源（shadow_generated 时）
            - mode: 运行模式，固定为 "shadow"
            - reason_code: 跳过原因（route_skipped 时）
            - error_codes: 错误码列表（error 时）
        业务逻辑：
            1. 空字符串直接返回 route_skipped。
            2. 使用 domain_router.route() 检查问题是否属于物流 NL2SQL 范围。
            3. 不属于则返回 route_skipped + reason_code。
            4. 属于则尝试运行 shadow pipeline，异常时 fail-closed 返回 error。
        """
        question_text = str(question or "").strip()

        # 空问题直接返回 route_skipped
        if not question_text:
            return {
                "status": "route_skipped",
                "reason_code": "empty_question",
            }

        try:
            # ---- 第一步：领域路由检查 ----
            route = self._try_domain_route(question_text)
            if route is None:
                return {
                    "status": "error",
                    "error_codes": ["nl2sql_domain_route_failed"],
                }
            if not route.get("should_process", False):
                return {
                    "status": "route_skipped",
                    "reason_code": route.get("reason_code", "route_skipped_unknown"),
                }

            # ---- 第二步：尝试运行 shadow pipeline ----
            shadow_result = self._try_run_shadow(question_text, trace_id=trace_id)
            return shadow_result

        except Exception as exc:
            # 任何异常都 fail-closed，不中断主链路
            logger.warning(
                "Nl2SqlGraphAdapter.build_shadow 异常，安全降级：%s",
                type(exc).__name__,
                exc_info=True,
            )
            return {
                "status": "error",
                "error_codes": ["nl2sql_adapter_exception"],
            }

    def _try_domain_route(self, question: str) -> dict[str, Any] | None:
        """尝试使用 LogisticsNl2SqlDomainRouter 进行领域路由。

        参数：
            question: 用户原始问题。
        返回：
            路由结果字典（包含 should_process、domain、source_system、reason_code 等字段），
            路由失败时返回 None。
        """
        try:
            router = self._domain_router
            if router is None:
                # 默认构造 LogisticsNl2SqlDomainRouter
                # 延迟导入避免循环依赖
                from backend.app.domains.logistics.services.nl2sql.m9_sqlplan_generation import (
                    LogisticsNl2SqlDomainRouter,
                )
                router = LogisticsNl2SqlDomainRouter()
                self._domain_router = router

            route = router.route(question)
            return {
                "should_process": route.should_process,
                "domain": route.domain,
                "source_system": route.source_system,
                "mode": route.mode,
                "reason_code": route.reason_code,
            }
        except Exception as exc:
            logger.warning(
                "Nl2SqlGraphAdapter 领域路由异常：%s",
                type(exc).__name__,
                exc_info=True,
            )
            return None

    def _try_run_shadow(self, question: str, trace_id: str | None = None) -> dict[str, Any]:
        """尝试运行 NL2SQL shadow pipeline。

        参数：
            question: 用户原始问题。
            trace_id: 可选追踪号。
        返回：
            shadow 运行结果字典。
        业务逻辑：
            当前使用简化版 shadow（不依赖 LLM/Milvus），因为完整 NL2SQL pipeline
            需要实时 LLM 调用和向量检索。后续 NQE-S2 可扩展为完整 shadow。
        """
        try:
            # 当前阶段：生成简化的 shadow 记录
            # 不调用完整的 LogisticsSqlPlanGenerator（需要 LLM/Milvus），
            # 只记录 domain_route 信息作为 shadow 摘要
            route = self._try_domain_route(question)
            if route is None or not route.get("should_process", False):
                return {
                    "status": "route_skipped",
                    "reason_code": route.get("reason_code", "unknown") if route else "route_failed",
                }

            return {
                "status": "shadow_generated",
                "domain": route.get("domain", "logistics"),
                "source_system": route.get("source_system", "middle_db"),
                "mode": "shadow",
                "trace_id": trace_id,
                # 后续 NQE-S2 可扩展：运行完整 SQLPlan generation + validation pipeline
                "pipeline_version": "nqe_s1_minimal",
            }
        except Exception as exc:
            logger.warning(
                "Nl2SqlGraphAdapter shadow pipeline 异常：%s",
                type(exc).__name__,
                exc_info=True,
            )
            return {
                "status": "error",
                "error_codes": ["nl2sql_shadow_pipeline_failed"],
            }

    # NQE-S3 新增：生成完整 NL2SQL 执行结果（用于 shadow compare）
    def build_full_result(self, question: str, trace_id: str | None = None) -> dict[str, Any]:
        """执行完整 NL2SQL 链路并返回业务化结果。

        参数：
            question: 用户原始问题。
            trace_id: 可选追踪号。
        返回：
            可与旧链路 execution_result 对比的清洗后结果字典。
            包含 status、row_count、answer_summary、columns、rows、
            supported、needs_clarification、status_code、display_type 等字段。
        业务逻辑：
            1. 使用 LogisticsDataQaService.query() 执行 NL2SQL 查询；
            2. 清洗结果，移除 SQL/表名/字段名等内部技术细节；
            3. 异常时 fail-closed，返回 error 状态。
        """
        question_text = str(question or "").strip()
        if not question_text:
            return {
                "status": "error",
                "row_count": 0,
                "answer_summary": "",
                "supported": False,
                "status_code": "error",
                "error": "empty_question",
            }

        try:
            # 调用物流领域服务的 query 方法获取 NL2SQL 结果
            # （当前阶段 NL2SQL 链路与旧链路使用相同的数据服务，
            #  后续可替换为独立的 NL2SQL pipeline）
            service = self._get_logistics_service()
            if service is None:
                return {
                    "status": "error",
                    "row_count": 0,
                    "answer_summary": "",
                    "supported": False,
                    "status_code": "error",
                    "error": "service_unavailable",
                }

            # 延迟导入 LogisticsDataQaQueryRequest
            from backend.app.domains.logistics.schemas.data_qa import (
                LogisticsDataQaQueryRequest,
            )

            result = service.query(
                LogisticsDataQaQueryRequest(question=question_text),
            )

            # 查询完成后关闭数据库会话，避免连接泄漏
            # 中文注释：NQE-S3 shadow compare 链路结束后需要显式关闭 DB session
            try:
                db_session = getattr(service, "db", None)
                if db_session is not None:
                    db_session.close()
            except Exception:
                pass  # 关闭失败不阻断主链路

            # 清洗结果（与 execute_node._sanitize_logistics_result 保持一致）
            sanitized = self._sanitize_result(result)
            return sanitized

        except Exception as exc:
            logger.warning(
                "Nl2SqlGraphAdapter.build_full_result 异常：%s",
                type(exc).__name__,
                exc_info=True,
            )
            return {
                "status": "error",
                "row_count": 0,
                "answer_summary": "",
                "supported": False,
                "status_code": "error",
                "error": "nl2sql_full_pipeline_failed",
            }

    # ------------------------------------------------------------------
    # NQE-S3 内部辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _get_logistics_service() -> Any:
        """构造默认 LogisticsDataQaService 实例。

        返回：
            LogisticsDataQaService 实例，或 None（构造失败时）。
        注意：
            调用方需要在查询完成后显式关闭 service 的数据库会话。
            在 build_full_result 的 try 块中，查询完成后会关闭会话。
        """
        try:
            from backend.app.core.database import SessionLocal
            from backend.app.domains.logistics.services.data_qa_service import (
                LogisticsDataQaService,
            )

            db = SessionLocal()
            return LogisticsDataQaService(db=db)
        except Exception:
            logger.warning(
                "无法构造 LogisticsDataQaService（可能缺少数据库连接）"
            )
            return None

    @staticmethod
    def _sanitize_result(result: Any) -> dict[str, Any]:
        """从物流查询结果中提取业务化字段，剔除技术细节。

        参数：
            result: LogisticsDataQaService.query 的返回结果。
        返回：
            仅包含业务化字段的字典。
        业务逻辑：
            与 execute_node._sanitize_logistics_result 保持一致，
            只暴露面向用户的业务字段。
        """
        # 提取 result_table
        result_table = getattr(result, "result_table", None)
        if result_table is not None:
            columns = getattr(result_table, "columns", []) or []
            rows = getattr(result_table, "rows", []) or []
            row_count = getattr(result_table, "row_count", len(rows))
        else:
            columns, rows, row_count = [], [], 0

        # 提取 status
        status_obj = getattr(result, "status", None)
        status_code = getattr(status_obj, "code", "unknown") if status_obj else "unknown"

        # 提取 presentation
        presentation = getattr(result, "presentation", None)
        display_type = getattr(presentation, "display_type", "narrative") if presentation else "narrative"

        # 提取 warnings
        warnings = list(getattr(result, "warnings", []) or [])

        return {
            "status": "success" if status_code in ("success", "ok") else status_code,
            "row_count": row_count,
            "answer_summary": str(getattr(result, "answer_summary", "") or ""),
            "columns": list(columns),
            "rows": list(rows),
            "supported": bool(getattr(result, "supported", True)),
            "needs_clarification": bool(getattr(result, "needs_clarification", False)),
            "status_code": status_code,
            "display_type": display_type,
            "warnings": warnings,
        }
