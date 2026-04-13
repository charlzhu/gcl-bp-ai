
from __future__ import annotations

import json
import logging
from typing import Any

from backend.app.domains.logistics.services.result_count_helper import LogisticsResultCountHelper

logger = logging.getLogger(__name__)


class LogisticsExecutionAuditService:
    """查询执行审计服务（V8）。

    这一层的定位不是替代 sys_query_log，而是给 nl2query_service 增加一份
    “更贴近执行链路”的审计摘要，方便后续排查：
    - 参数是否合法
    - 是否命中 SQL 白名单
    - 最终走了什么执行模式
    - 是否返回了空结果
    """

    def build_audit_payload(
        self,
        *,
        trace_id: str | None,
        question: str,
        parsed: dict[str, Any],
        validation_result: dict[str, Any],
        whitelist_result: dict[str, Any],
        execution_binding: dict[str, Any],
        query_result: dict[str, Any],
    ) -> dict[str, Any]:
        # 统一通过结果数量辅助工具提取数量，避免 aggregate 场景因 total 缺失或为 0 被误判。
        total = LogisticsResultCountHelper.extract_count(query_result)

        return {
            "trace_id": trace_id,
            "question": question,
            "selected_domain": parsed.get("selected_domain"),
            "mode": parsed.get("mode"),
            "metric_type": parsed.get("metric_type"),
            "source_scope": parsed.get("source_scope"),
            "template_id": parsed.get("template_id"),
            "sql_template_id": parsed.get("sql_template_id"),
            "validation_ok": validation_result.get("ok"),
            "validation_issues": validation_result.get("issues", []),
            "sql_whitelist_allowed": whitelist_result.get("allowed"),
            "sql_whitelist_reason": whitelist_result.get("reason"),
            "execution_mode": query_result.get("execution_mode") if isinstance(query_result, dict) else None,
            "result_count": total,
            "is_empty_result": total == 0,
            "execution_binding": execution_binding,
        }

    def log_summary(self, audit_payload: dict[str, Any]) -> None:
        """把审计摘要写到应用日志。

        这里先走普通日志，后面如果你想再落独立表，可以在此基础上继续扩展。
        """
        try:
            logger.info("logistics execution audit: %s", json.dumps(audit_payload, ensure_ascii=False))
        except Exception as exc:
            logger.warning("failed to write execution audit log: %s", exc)
