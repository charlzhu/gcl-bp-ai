from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.domains.query_planning.schemas.query_plan_v2 import QueryPlanningV2Plan


class QueryPlanV2AuditWriter:
    """Query Planning V2 JSONL 审计写入器。

    说明：
        1. Phase 3 独立诊断接口先写 JSONL，不改数据库表结构；
        2. 写入失败不影响主接口返回，只在 query_plan.audit 中标记；
        3. 日志只保存规划结果，不保存密钥、不执行 SQL。
    """

    def __init__(self, path: str | Path | None = None) -> None:
        """初始化审计写入器。

        参数：
            path: JSONL 日志路径，默认 data/logs/query_planning_v2_audit.jsonl。
        返回：无返回值。
        """

        self.path = Path(path or "data/logs/query_planning_v2_audit.jsonl")

    def write(self, *, plan: QueryPlanningV2Plan, trace_id: str | None = None) -> QueryPlanningV2Plan:
        """写入单条 query_plan_v2 审计日志。

        参数：
            plan: 已生成的 Query Planning V2 计划。
            trace_id: 请求追踪号。
        返回：
            带 audit 写入状态的新计划。
        业务逻辑：使用 JSONL 方便灰度回放和 diff，不阻塞正式问答链路。
        """

        updated = plan.model_copy(deep=True)
        updated.audit.trace_id = trace_id or updated.audit.trace_id
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            updated.audit.audit_logged = True
            updated.audit.audit_log_path = str(self.path)
            updated.audit.audit_message = None
            payload: dict[str, Any] = {
                "logged_at": datetime.now(timezone.utc).isoformat(),
                "trace_id": updated.audit.trace_id,
                "query_plan": updated.model_dump(mode="json"),
            }
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")
        except Exception as exc:  # noqa: BLE001
            updated.audit.audit_logged = False
            updated.audit.audit_log_path = str(self.path)
            updated.audit.audit_message = f"Query Planning V2 审计日志写入失败：{exc}"
        return updated


__all__ = ["QueryPlanV2AuditWriter"]
