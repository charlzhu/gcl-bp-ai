from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.app.domains.logistics.services.error_code_registry import LogisticsErrorCodeRegistry
from backend.app.domains.logistics.services.result_count_helper import LogisticsResultCountHelper


class LogisticsQueryResponseStandardizer:
    """物流查询响应标准化器（V10）。

    设计目标：
    1. 给 parse_and_query 的返回结果统一补 response_meta / query_result.status；
    2. 把“空结果、参数修正、执行异常、fallback”等状态整理成稳定错误码；
    3. 保持向后兼容，不破坏当前 question / parsed / query_result 三段结构。
    """

    def build_status(
        self,
        *,
        parsed: dict[str, Any],
        query_result: dict[str, Any],
        probe_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """根据解析结果和执行结果生成统一状态码。"""
        execution_mode = query_result.get("execution_mode")
        total = self._extract_total(query_result)
        validation = parsed.get("validation") or {}
        validation_issues = validation.get("issues") or []
        selected_domain = parsed.get("selected_domain")

        if execution_mode == "error_fallback":
            return LogisticsErrorCodeRegistry.build_status(
                code=LogisticsErrorCodeRegistry.EXECUTION_ERROR,
                message="查询主执行链路发生异常，系统已返回兜底结果。",
                success=False,
                severity="error",
                extras={"execution_mode": execution_mode},
            )

        if selected_domain and selected_domain != "logistics":
            return LogisticsErrorCodeRegistry.build_status(
                code=LogisticsErrorCodeRegistry.UNSUPPORTED_DOMAIN_EXECUTION,
                message="当前请求已识别为非物流域，但当前版本仍由物流域执行兜底处理。",
                success=True,
                severity="warning",
                extras={"execution_mode": execution_mode},
            )

        if total == 0 and probe_result and probe_result.get("exists") is False:
            return LogisticsErrorCodeRegistry.build_status(
                code=LogisticsErrorCodeRegistry.DETAIL_NOT_FOUND,
                message=f"未找到{probe_result.get('field_label')}“{probe_result.get('field_value')}”对应的明细数据。",
                success=True,
                severity="warning",
                extras={"execution_mode": execution_mode},
            )

        if total == 0:
            # 空结果优先级高于 fallback。
            # 说明：
            # 1. fallback 只是执行路径说明，不应覆盖“没有匹配数据”这类更具体的业务状态；
            # 2. 这样前端在 fallback + 空结果场景下仍能稳定展示空结果分析，而不是只看到兼容模式提示。
            return LogisticsErrorCodeRegistry.build_status(
                code=LogisticsErrorCodeRegistry.EMPTY_RESULT,
                message="查询已执行完成，但未返回匹配数据。",
                success=True,
                severity="warning",
                extras={"execution_mode": execution_mode},
            )

        if execution_mode == "fallback":
            # 只有在“已有有效结果”时，才把 fallback 作为主状态码。
            # 若本次本身就是空结果/编号不存在，应优先给更具体的业务状态。
            return LogisticsErrorCodeRegistry.build_status(
                code=LogisticsErrorCodeRegistry.FALLBACK_MODE,
                message="当前请求已执行，但使用的是 fallback 兼容模式。",
                success=True,
                severity="warning",
                extras={"execution_mode": execution_mode},
            )

        if validation_issues:
            return LogisticsErrorCodeRegistry.build_status(
                code=LogisticsErrorCodeRegistry.OK_WITH_ADJUSTMENTS,
                message="查询已执行完成，部分参数已按系统规则自动修正。",
                success=True,
                severity="info",
                extras={"execution_mode": execution_mode},
            )

        return LogisticsErrorCodeRegistry.build_status(
            code=LogisticsErrorCodeRegistry.OK,
            message="查询执行成功。",
            success=True,
            severity="info",
            extras={"execution_mode": execution_mode},
        )

    def build_response_meta(
        self,
        *,
        question: str,
        parsed: dict[str, Any],
        query_result: dict[str, Any],
        status: dict[str, Any],
    ) -> dict[str, Any]:
        """构建顶层响应元信息。"""
        return {
            "question": question,
            "domain": parsed.get("selected_domain", "logistics"),
            "mode": parsed.get("mode"),
            "metric_type": parsed.get("metric_type"),
            "source_scope": parsed.get("source_scope"),
            "status": deepcopy(status),
            "config_version": parsed.get("config_version"),
            "trace_ready": True,
            "result_count": self._extract_total(query_result),
        }

    @staticmethod
    def _extract_total(query_result: dict[str, Any]) -> int:
        """从查询结果中提取统一结果数量。

        这里不能只看 `total` 字段。
        compare 总量对比、aggregate summary 等场景并不总是返回 `total`，
        因此统一复用结果数量辅助工具，避免前端再次看到“有结果却显示 EMPTY_RESULT”。
        """
        return LogisticsResultCountHelper.extract_count(query_result)
