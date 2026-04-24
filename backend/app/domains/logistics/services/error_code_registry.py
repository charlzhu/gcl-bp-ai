from __future__ import annotations

from typing import Any


class LogisticsErrorCodeRegistry:
    """物流域错误码注册表（V10）。

    设计目标：
    1. 把查询服务内部出现的“空结果、参数修正、执行异常”等状态统一成稳定错误码；
    2. 便于前端、日志、后续告警平台复用，避免各处自行拼接 message；
    3. 当前先覆盖物流一期最常见场景，后续可以逐步扩展。
    """

    # 成功类
    OK = "OK"
    OK_WITH_ADJUSTMENTS = "OK_WITH_ADJUSTMENTS"

    # 空结果类
    EMPTY_RESULT = "EMPTY_RESULT"
    DETAIL_NOT_FOUND = "DETAIL_NOT_FOUND"

    # 参数与安全类
    INVALID_QUERY_PARAM = "INVALID_QUERY_PARAM"
    SQL_TEMPLATE_NOT_ALLOWED = "SQL_TEMPLATE_NOT_ALLOWED"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    UNSUPPORTED_QUESTION = "UNSUPPORTED_QUESTION"

    # 执行链路类
    FALLBACK_MODE = "FALLBACK_MODE"
    EXECUTION_ERROR = "EXECUTION_ERROR"

    # 多域预留类
    UNSUPPORTED_DOMAIN_EXECUTION = "UNSUPPORTED_DOMAIN_EXECUTION"

    @classmethod
    def build_status(
        cls,
        *,
        code: str,
        message: str,
        success: bool,
        severity: str = "info",
        extras: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构建统一状态结构。

        参数：
            code: 稳定错误码或状态码。
            message: 给前端和联调直接展示的说明文案。
            success: 当前请求是否视为成功完成。
            severity: 严重级别，建议取值 info / warning / error。
            extras: 额外补充字段。

        返回：
            统一状态字典，后续会挂到 query_result.status 和 response_meta 中。
        """
        payload = {
            "code": code,
            "message": message,
            "success": success,
            "severity": severity,
        }
        if extras:
            payload.update(extras)
        return payload
