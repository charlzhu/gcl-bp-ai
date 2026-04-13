
from __future__ import annotations

import json
import logging
from copy import deepcopy
from typing import Any, TYPE_CHECKING

try:
    from sqlalchemy.exc import SQLAlchemyError
except Exception:  # pragma: no cover - 兼容未安装 SQLAlchemy 的轻量测试环境
    class SQLAlchemyError(Exception):
        pass

if TYPE_CHECKING:
    from backend.app.domains.logistics.services.query_service import LogisticsQueryService

logger = logging.getLogger(__name__)


class LogisticsQueryPlanStore:
    """查询计划落库器（V8）。

    V8 的优化点：
    1. 避免在 import 阶段强依赖 SQLAlchemy；
    2. 保持当前优先复用 sys_query_log 的方案；
    3. 对落库失败继续保持“记录 warning，但不影响主查询返回”。
    """

    def __init__(self, query_service: "LogisticsQueryService") -> None:
        self.query_service = query_service

    def save_plan(
        self,
        *,
        trace_id: str | None,
        question: str,
        parsed: dict[str, Any],
        execution_binding: dict[str, Any],
        execution_summary: dict[str, Any] | None = None,
        response_meta: dict[str, Any] | None = None,
        query_result: dict[str, Any] | None = None,
    ) -> None:
        db = getattr(self.query_service, "db", None)
        repository = getattr(self.query_service, "repository", None)
        if db is None or repository is None:
            return

        # 这里不能直接把 parsed 原样序列化：
        # parsed 里已经挂了 execution_binding / execution_audit，
        # 而 execution_audit 又会引用 execution_binding，容易形成重复引用链。
        parsed_snapshot = deepcopy(parsed)
        parsed_snapshot.pop("execution_audit", None)
        parsed_snapshot.pop("execution_binding", None)
        execution_binding_snapshot = deepcopy(execution_binding)

        payload = {
            "trace_id": trace_id,
            "query_type": "NL_QUERY_PLAN",
            "question_text": question,
            "request_payload": self._safe_json_dumps(
                {
                    "parsed": parsed_snapshot,
                    "execution_binding": execution_binding_snapshot,
                    "execution_summary": execution_summary or {},
                    "response_meta": self._build_response_meta_snapshot(response_meta),
                    "query_result": self._build_query_result_snapshot(query_result),
                }
            ),
            "route_type": parsed.get("source_scope") or "all",
            "metric_type": parsed.get("metric_type") or "shipment_watt",
            "result_count": int((execution_summary or {}).get("result_count", 0)),
            "status": "SUCCESS",
            "message": "查询计划已落库",
        }
        try:
            repository.write_query_log(db, payload)
            db.commit()
        except SQLAlchemyError as exc:
            logger.warning("query plan store skipped because db write failed: %s", exc)
            try:
                db.rollback()
            except Exception:
                pass

    @staticmethod
    def _safe_json_dumps(payload: dict[str, Any]) -> str:
        try:
            return json.dumps(payload, ensure_ascii=False, default=str)
        except Exception as exc:
            logger.warning("query plan serialization fallback used: %s", exc)
            fallback = {
                "parsed": {
                    "mode": payload.get("parsed", {}).get("mode"),
                    "metric_type": payload.get("parsed", {}).get("metric_type"),
                    "source_scope": payload.get("parsed", {}).get("source_scope"),
                    "sql_template_id": payload.get("parsed", {}).get("sql_template_id"),
                    "template_id": payload.get("parsed", {}).get("template_id"),
                },
                "execution_binding": {
                    "execution_mode": payload.get("execution_binding", {}).get("execution_mode"),
                    "sql_template_id": (payload.get("execution_binding", {}).get("sql_template") or {}).get("sql_template_id"),
                    "sql_whitelist_allowed": (payload.get("execution_binding", {}).get("sql_whitelist") or {}).get("allowed"),
                },
                "execution_summary": payload.get("execution_summary", {}),
                "response_meta": payload.get("response_meta", {}),
                "query_result": {
                    "query_type": (payload.get("query_result", {}) or {}).get("query_type"),
                    "execution_mode": (payload.get("query_result", {}) or {}).get("execution_mode"),
                    "status": (payload.get("query_result", {}) or {}).get("status"),
                    "item_count": (payload.get("query_result", {}) or {}).get("item_count"),
                    "items_truncated": (payload.get("query_result", {}) or {}).get("items_truncated"),
                },
            }
            return json.dumps(fallback, ensure_ascii=False, default=str)

    @staticmethod
    def _build_response_meta_snapshot(response_meta: dict[str, Any] | None) -> dict[str, Any]:
        """构建 response_meta 快照。

        说明：
        1. 查询历史页需要稳定展示状态码、模式和结果数量；
        2. 这里保留前端会直接消费的关键字段；
        3. 其余高频冗余字段不再重复落库，避免日志体积持续膨胀。
        """
        if not isinstance(response_meta, dict):
            return {}
        return {
            "question": response_meta.get("question"),
            "domain": response_meta.get("domain"),
            "mode": response_meta.get("mode"),
            "metric_type": response_meta.get("metric_type"),
            "source_scope": response_meta.get("source_scope"),
            "status": deepcopy(response_meta.get("status")),
            "config_version": response_meta.get("config_version"),
            "trace_ready": response_meta.get("trace_ready"),
            "result_count": response_meta.get("result_count"),
        }

    @staticmethod
    def _build_query_result_snapshot(query_result: dict[str, Any] | None) -> dict[str, Any]:
        """构建 query_result 历史快照。

        说明：
        1. `sys_query_log.request_payload` 当前是 Text 字段，不能直接无上限落整份结果；
        2. 历史详情页主要需要“可解释的核心结果”，不是把整页表格原样存库；
        3. 因此这里只保留关键字段，并对 items 做上限截断，避免日志写入失败。
        """
        if not isinstance(query_result, dict):
            return {}

        items = query_result.get("items")
        safe_items = items if isinstance(items, list) else []
        limited_items = deepcopy(safe_items[:20])

        return {
            "query_type": query_result.get("query_type"),
            "metric_type": query_result.get("metric_type"),
            "source_scope": query_result.get("source_scope"),
            "filters": deepcopy(query_result.get("filters")),
            "execution_mode": query_result.get("execution_mode"),
            "status": deepcopy(query_result.get("status")),
            "summary": deepcopy(query_result.get("summary")),
            "total": query_result.get("total"),
            "page": query_result.get("page"),
            "page_size": query_result.get("page_size"),
            "record_count": query_result.get("record_count"),
            "left_label": query_result.get("left_label"),
            "right_label": query_result.get("right_label"),
            "left_value": query_result.get("left_value"),
            "right_value": query_result.get("right_value"),
            "diff_value": query_result.get("diff_value"),
            "diff_rate": query_result.get("diff_rate"),
            "compatibility_notice": deepcopy(query_result.get("compatibility_notice")),
            "result_explanation": deepcopy(query_result.get("result_explanation")),
            "no_result_analysis": deepcopy(query_result.get("no_result_analysis")),
            "business_no_probe": deepcopy(query_result.get("business_no_probe")),
            "items": limited_items,
            "item_count": len(safe_items),
            "items_truncated": len(safe_items) > len(limited_items),
        }
