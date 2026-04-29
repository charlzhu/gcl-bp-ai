from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any


class QaTraceRecorder:
    """问答主链路明细节点记录器。

    说明：
        1. 每个问答请求创建一个 recorder，用于记录“输入、理解、查询、表达、落库”等关键节点；
        2. 事件会同时进入接口响应的 trace_events 字段和后端结构化日志；
        3. 为避免日志过大或泄露敏感信息，payload 会做长度截断和字段裁剪。
    """

    def __init__(
        self,
        *,
        domain: str,
        trace_id: str | None,
        question: str,
        logger_name: str = "backend.app.qa_trace",
    ) -> None:
        """初始化记录器。

        参数：
            domain: 业务域，例如 logistics 或 plan_bom；
            trace_id: 当前请求追踪号；
            question: 用户原始问题；
            logger_name: 写入后端日志的 logger 名称。

        返回：
            无返回值。
        """

        self.domain = domain
        self.trace_id = trace_id or "local-dev"
        self.question = question
        self._logger = logging.getLogger(logger_name)
        self._events: list[dict[str, Any]] = []

    @property
    def events(self) -> list[dict[str, Any]]:
        """返回当前已收集的节点快照。

        返回：
            事件列表副本，避免外部直接修改内部状态。
        """

        return list(self._events)

    def add(self, stage: str, message: str, payload: dict[str, Any] | None = None) -> None:
        """追加一个问答链路节点。

        参数：
            stage: 节点编码，便于按阶段检索；
            message: 面向排查人员的中文节点说明；
            payload: 当前节点的关键业务上下文。

        返回：
            无返回值。
        """

        event = {
            "seq": len(self._events) + 1,
            "time": datetime.now().isoformat(timespec="milliseconds"),
            "domain": self.domain,
            "trace_id": self.trace_id,
            "stage": stage,
            "message": message,
            "payload": self._sanitize(payload or {}),
        }
        self._events.append(event)
        self._logger.info("qa_trace_event=%s", json.dumps(event, ensure_ascii=False, default=str))

    def _sanitize(self, value: Any, *, depth: int = 0) -> Any:
        """裁剪日志 payload，避免明细节点过大。

        参数：
            value: 待写入日志的任意值；
            depth: 当前递归深度，超过限制后只保留摘要。

        返回：
            可安全序列化、规模受控的值。
        """

        if depth >= 4:
            return self._short_text(value)
        if isinstance(value, dict):
            return {str(key): self._sanitize(item, depth=depth + 1) for key, item in list(value.items())[:40]}
        if isinstance(value, (list, tuple, set)):
            items = list(value)
            sanitized = [self._sanitize(item, depth=depth + 1) for item in items[:30]]
            if len(items) > 30:
                sanitized.append(f"...已截断 {len(items) - 30} 项")
            return sanitized
        if isinstance(value, str):
            return value if len(value) <= 500 else f"{value[:500]}...已截断"
        if value is None or isinstance(value, (int, float, bool)):
            return value
        return self._short_text(value)

    @staticmethod
    def _short_text(value: Any) -> str:
        """把复杂对象转换成短文本。

        参数：
            value: 任意对象。

        返回：
            长度受控的文本。
        """

        text = str(value)
        return text if len(text) <= 300 else f"{text[:300]}...已截断"


__all__ = ["QaTraceRecorder"]
