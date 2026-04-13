from __future__ import annotations

import json
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.core.exceptions import AppException
from backend.app.domains.logistics.repositories.query_repository import LogisticsQueryRepository
from backend.app.domains.logistics.services.error_code_registry import LogisticsErrorCodeRegistry
from backend.app.schemas.query_log import QueryLogDetailResponse, QueryLogItem, QueryLogListResponse


class QueryLogService:
    """查询历史服务。

    设计目标：
    1. 复用现有 `sys_query_log`，不再额外新建一套历史表；
    2. 把偏日志格式的原始记录整理成前端可直接展示的结构；
    3. 当日志表未就绪时返回空列表和提示，避免前端直接 500。
    """

    def __init__(
        self,
        *,
        db: Session,
        repository: LogisticsQueryRepository | None = None,
    ) -> None:
        self.db = db
        self.repository = repository or LogisticsQueryRepository()

    def list_query_logs(
        self,
        *,
        limit: int | None = None,
        page: int = 1,
        page_size: int = 20,
        query_type: str | None = None,
        status: str | None = None,
        trace_id: str | None = None,
        keyword: str | None = None,
    ) -> QueryLogListResponse:
        """查询历史列表。

        参数：
            limit: 兼容旧接口的最大返回条数；若传入则覆盖 page_size。
            page: 当前页码。
            page_size: 每页条数。
            query_type: 可选的查询类型过滤。
            status: 可选的状态过滤。
            trace_id: 可选的 trace_id 过滤。
            keyword: 可选的关键词检索，当前匹配历史问题、trace_id 和日志消息。

        返回：
            统一的查询历史列表结构。
        """
        effective_page_size = limit or page_size
        normalized_page = max(page, 1)
        offset = (normalized_page - 1) * effective_page_size
        normalized_keyword = keyword.strip() if isinstance(keyword, str) and keyword.strip() else None

        try:
            rows, total = self.repository.list_query_logs(
                self.db,
                limit=effective_page_size,
                offset=offset,
                query_type=query_type,
                status=status,
                trace_id=trace_id,
                keyword=normalized_keyword,
            )
        except SQLAlchemyError:
            return QueryLogListResponse(
                total=0,
                page=normalized_page,
                page_size=effective_page_size,
                items=[],
                load_warning="当前 sys_query_log 尚未就绪，查询历史暂时不可用。",
            )

        items = [self._normalize_row(row) for row in rows]
        return QueryLogListResponse(
            total=total,
            page=normalized_page,
            page_size=effective_page_size,
            items=items,
        )

    def get_query_log_detail(
        self,
        *,
        log_id: int,
    ) -> QueryLogDetailResponse:
        """查询单条历史详情。

        说明：
        1. 前端详情页后续直接依赖这个接口；
        2. 若当前日志不存在，返回明确 404，避免前端把空对象当成功；
        3. 详情会补齐 response_meta 和 query_result 快照，减少前端自行拼装。
        """
        try:
            row = self.repository.get_query_log_detail(
                self.db,
                log_id=log_id,
            )
        except SQLAlchemyError as exc:
            raise AppException(
                "查询历史详情暂时不可用，请检查 sys_query_log 是否正常。",
                code=5006,
                status_code=500,
            ) from exc

        if not row:
            raise AppException("查询历史记录不存在", code=4043, status_code=404)

        return self._normalize_detail_row(row)

    def _normalize_row(self, row: dict[str, Any]) -> QueryLogItem:
        """把数据库日志行归一成前端可直接消费的结构。"""
        payload_json = self._parse_payload(row.get("request_payload"))
        normalized = self._build_normalized_payload(row=row, payload_json=payload_json)
        return QueryLogItem(**normalized)

    def _normalize_detail_row(self, row: dict[str, Any]) -> QueryLogDetailResponse:
        """把数据库日志行归一成详情接口结构。"""
        payload_json = self._parse_payload(row.get("request_payload"))
        normalized = self._build_normalized_payload(row=row, payload_json=payload_json)
        normalized["response_meta"] = self._extract_response_meta(
            payload_json=payload_json,
            row=row,
            question=normalized["question"],
            execution_mode=normalized["execution_mode"],
            metric_type=normalized["metric_type"],
        )
        normalized["query_result"] = self._extract_query_result(
            payload_json=payload_json,
            row=row,
            execution_mode=normalized["execution_mode"],
            status_code=normalized["status_code"],
            status_message=normalized["status_message"],
        )
        return QueryLogDetailResponse(**normalized)

    def _build_normalized_payload(
        self,
        *,
        row: dict[str, Any],
        payload_json: Any,
    ) -> dict[str, Any]:
        """抽取列表和详情共用的标准字段。"""
        parsed = payload_json.get("parsed") if isinstance(payload_json, dict) else None
        execution_binding = payload_json.get("execution_binding") if isinstance(payload_json, dict) else None
        execution_summary = payload_json.get("execution_summary") if isinstance(payload_json, dict) else None
        response_meta = payload_json.get("response_meta") if isinstance(payload_json, dict) else None
        query_result = payload_json.get("query_result") if isinstance(payload_json, dict) else None

        execution_mode = self._resolve_execution_mode(
            execution_summary=execution_summary,
            execution_binding=execution_binding,
            response_meta=response_meta,
            query_result=query_result,
        )
        question = row.get("question_text")
        if not question:
            question = self._build_fallback_question(
                query_type=row.get("query_type"),
                payload_json=payload_json,
            )

        status_payload = self._resolve_status_payload(
            row=row,
            payload_json=payload_json,
            execution_mode=execution_mode,
        )
        template_id = parsed.get("template_id") if isinstance(parsed, dict) else None
        template_hit = bool(parsed.get("template_hit")) if isinstance(parsed, dict) else False

        return {
            "id": int(row.get("id") or 0),
            "trace_id": row.get("trace_id"),
            "query_type": str(row.get("query_type") or "-"),
            "question": question,
            "execution_mode": execution_mode,
            "route_type": row.get("route_type"),
            "metric_type": row.get("metric_type") or (parsed.get("metric_type") if isinstance(parsed, dict) else None),
            "result_count": int(row.get("result_count") or 0),
            "status": str(row.get("status") or "-"),
            "status_code": status_payload.get("code"),
            "status_message": status_payload.get("message"),
            "template_hit": template_hit,
            "template_id": template_id,
            "message": row.get("message"),
            "created_at": row.get("created_at"),
            "parsed": parsed if isinstance(parsed, dict) else None,
            "execution_binding": execution_binding if isinstance(execution_binding, dict) else None,
            "execution_summary": execution_summary if isinstance(execution_summary, dict) else None,
            "request_payload_json": payload_json,
        }

    @staticmethod
    def _parse_payload(raw_payload: Any) -> Any:
        """安全解析 request_payload。

        `sys_query_log.request_payload` 在不同环境里可能是字符串、字典或 JSON 字段，
        因此这里统一做一层容错。
        """
        if raw_payload is None:
            return None
        if isinstance(raw_payload, (dict, list)):
            return raw_payload
        if isinstance(raw_payload, bytes):
            raw_payload = raw_payload.decode("utf-8", errors="ignore")
        if isinstance(raw_payload, str):
            try:
                return json.loads(raw_payload)
            except Exception:
                return {"raw_text": raw_payload}
        return raw_payload

    @staticmethod
    def _build_fallback_question(
        *,
        query_type: str | None,
        payload_json: Any,
    ) -> str:
        """为没有 question_text 的日志构造前端展示标题。"""
        if isinstance(payload_json, dict):
            if payload_json.get("question"):
                return str(payload_json["question"])
            if payload_json.get("contract_no"):
                return f"明细查询：合同编号 {payload_json.get('contract_no')}"
            if payload_json.get("metric_type"):
                return f"{query_type or 'QUERY'}：{payload_json.get('metric_type')}"
        return query_type or "-"

    @staticmethod
    def _resolve_execution_mode(
        *,
        execution_summary: dict[str, Any] | None,
        execution_binding: dict[str, Any] | None,
        response_meta: dict[str, Any] | None,
        query_result: dict[str, Any] | None,
    ) -> str | None:
        """解析统一执行模式。

        说明：
        1. 不同版本日志中执行模式的挂载位置不完全一致；
        2. 这里按“query_result -> response_meta.status -> execution_summary -> execution_binding”顺序兜底；
        3. 返回值供查询历史列表和详情页统一展示。
        """
        if isinstance(query_result, dict) and query_result.get("execution_mode"):
            return str(query_result.get("execution_mode"))
        if isinstance(response_meta, dict):
            status_payload = response_meta.get("status")
            if isinstance(status_payload, dict) and status_payload.get("execution_mode"):
                return str(status_payload.get("execution_mode"))
        if isinstance(execution_summary, dict) and execution_summary.get("execution_mode"):
            return str(execution_summary.get("execution_mode"))
        if isinstance(execution_binding, dict) and execution_binding.get("execution_mode"):
            return str(execution_binding.get("execution_mode"))
        return None

    def _resolve_status_payload(
        self,
        *,
        row: dict[str, Any],
        payload_json: Any,
        execution_mode: str | None,
    ) -> dict[str, Any]:
        """归一化日志详情中的状态结构。

        说明：
        1. 新日志优先直接取 response_meta.status 或 query_result.status；
        2. 老日志若还没有标准状态字段，则根据 result_count 和 execution_mode 兜底推断；
        3. 统一返回 `code/message/success/severity`，便于前端直接消费。
        """
        if isinstance(payload_json, dict):
            response_meta = payload_json.get("response_meta")
            if isinstance(response_meta, dict) and isinstance(response_meta.get("status"), dict):
                return response_meta["status"]

            query_result = payload_json.get("query_result")
            if isinstance(query_result, dict) and isinstance(query_result.get("status"), dict):
                return query_result["status"]

        result_count = int(row.get("result_count") or 0)
        if execution_mode == "error_fallback":
            return LogisticsErrorCodeRegistry.build_status(
                code=LogisticsErrorCodeRegistry.EXECUTION_ERROR,
                message="查询主执行链路发生异常，日志中只保留了兜底结果。",
                success=False,
                severity="error",
                extras={"execution_mode": execution_mode},
            )
        if execution_mode == "fallback":
            return LogisticsErrorCodeRegistry.build_status(
                code=LogisticsErrorCodeRegistry.FALLBACK_MODE,
                message="当前日志记录对应的是 fallback 兼容模式结果。",
                success=True,
                severity="warning",
                extras={"execution_mode": execution_mode},
            )
        if result_count == 0:
            return LogisticsErrorCodeRegistry.build_status(
                code=LogisticsErrorCodeRegistry.EMPTY_RESULT,
                message="该次查询已执行完成，但未返回匹配数据。",
                success=True,
                severity="warning",
                extras={"execution_mode": execution_mode},
            )
        return LogisticsErrorCodeRegistry.build_status(
            code=LogisticsErrorCodeRegistry.OK,
            message="查询执行成功。",
            success=True,
            severity="info",
            extras={"execution_mode": execution_mode},
        )

    def _extract_response_meta(
        self,
        *,
        payload_json: Any,
        row: dict[str, Any],
        question: str,
        execution_mode: str | None,
        metric_type: str | None,
    ) -> dict[str, Any] | None:
        """提取或补造 response_meta。

        说明：
        1. 新版 `NL_QUERY_PLAN` 日志会直接落 `response_meta`；
        2. 老日志或非 NL_QUERY_PLAN 日志没有该字段时，这里构造最小可消费结构；
        3. 这样前端详情页就不需要自己猜哪些历史记录能拿到状态。
        """
        if isinstance(payload_json, dict) and isinstance(payload_json.get("response_meta"), dict):
            return payload_json.get("response_meta")

        parsed = payload_json.get("parsed") if isinstance(payload_json, dict) else None
        status_payload = self._resolve_status_payload(
            row=row,
            payload_json=payload_json,
            execution_mode=execution_mode,
        )
        return {
            "question": question,
            "domain": (parsed.get("selected_domain") if isinstance(parsed, dict) else None) or "logistics",
            "mode": parsed.get("mode") if isinstance(parsed, dict) else None,
            "metric_type": metric_type,
            "source_scope": (parsed.get("source_scope") if isinstance(parsed, dict) else None) or row.get("route_type"),
            "status": status_payload,
            "trace_ready": bool(row.get("trace_id")),
            "result_count": int(row.get("result_count") or 0),
        }

    def _extract_query_result(
        self,
        *,
        payload_json: Any,
        row: dict[str, Any],
        execution_mode: str | None,
        status_code: str | None,
        status_message: str | None,
    ) -> dict[str, Any] | None:
        """提取或补造 query_result 快照。

        说明：
        1. 新版日志会落 `query_result` 快照，供历史详情页直接展示；
        2. 老日志没有该字段时，这里补一个最小快照，至少保留状态、模式和数量；
        3. 这里返回的是日志快照，不是重新执行查询的实时结果。
        """
        if isinstance(payload_json, dict) and isinstance(payload_json.get("query_result"), dict):
            return payload_json.get("query_result")

        execution_summary = payload_json.get("execution_summary") if isinstance(payload_json, dict) else None
        return {
            "query_type": self._normalize_query_type(row.get("query_type")),
            "metric_type": row.get("metric_type"),
            "source_scope": row.get("route_type"),
            "execution_mode": execution_mode,
            "status": {
                "code": status_code,
                "message": status_message,
                "execution_mode": execution_mode,
            },
            "item_count": int(row.get("result_count") or 0),
            "items_truncated": False,
            "items": [],
            "execution_summary": execution_summary if isinstance(execution_summary, dict) else None,
        }

    @staticmethod
    def _normalize_query_type(query_type: Any) -> str:
        """把日志类型收敛成前端熟悉的查询模式名称。"""
        mapping = {
            "NL_QUERY_PLAN": "nl_query",
            "AGGREGATE": "aggregate",
            "DETAIL": "detail",
            "COMPARE": "compare",
        }
        raw = str(query_type or "").upper()
        return mapping.get(raw, str(query_type or "-").lower())
