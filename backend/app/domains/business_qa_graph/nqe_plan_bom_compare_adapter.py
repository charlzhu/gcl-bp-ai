"""NQE BOM compare / replay fallback 适配器。

NQE-SQL-MAIN-26：非侵入式接入。包装 PlanBomQueryService.compare/compare_replay，
输出统一 NqeBomCompareResult。不修改旧 BOM 生产逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NqeBomCompareResult:
    """NQE BOM compare / replay 统一输出。"""
    domain: str = "plan_bom"
    operation: str = ""  # compare / replay
    requested: bool = False
    executed: bool = False
    fallback_reason: str = ""
    missing_slots: list[str] = field(default_factory=list)
    left_identifier: str = ""
    right_identifier: str = ""
    diff_summary: str = ""
    changed_count: int = 0
    same_count: int = 0
    log_id: int = 0
    error_code: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "operation": self.operation,
            "requested": self.requested,
            "executed": self.executed,
            "fallback_reason": self.fallback_reason,
            "missing_slots": self.missing_slots,
            "diff_summary": self.diff_summary,
            "changed_count": self.changed_count,
            "same_count": self.same_count,
        }


class NqePlanBomCompareAdapter:
    """NQE BOM compare / replay 适配器。

    参数：
        db_session: 可选数据库 session（compare 需要）。
    """

    def __init__(self, db_session: Any = None) -> None:
        self._db = db_session

    def _ensure_session(self) -> Any:
        if self._db is not None:
            return self._db
        from backend.app.db.session import SessionLocal
        return SessionLocal()

    def try_compare(
        self,
        *,
        left_identifier: str = "",
        right_identifier: str = "",
        trace_id: str = "",
    ) -> NqeBomCompareResult:
        """尝试执行 BOM compare。

        参数：
            left_identifier: 左侧订单/评审号等标识。
            right_identifier: 右侧订单/评审号等标识。
            trace_id: 查询追踪号。
        返回：
            统一 NqeBomCompareResult。
        业务逻辑：
            校验必需参数后调用 PlanBomQueryService.compare()。
            参数不足或服务异常时返回明确 fallback_reason。
        """
        result = NqeBomCompareResult(operation="compare", requested=True)
        missing = []
        if not left_identifier:
            missing.append("left_identifier")
        if not right_identifier:
            missing.append("right_identifier")
        if missing:
            result.missing_slots = missing
            result.fallback_reason = f"missing_slots: {', '.join(missing)}"
            return result

        try:
            from backend.app.domains.plan_bom.schemas.query import (
                PlanBomCompareQueryRequest,
                PlanBomCompareSideRequest,
            )

            from backend.app.domains.plan_bom.services.query_service import (
                PlanBomQueryService,
            )
            from backend.app.domains.plan_bom.repositories.query_repository import PlanBomQueryRepository

            service = PlanBomQueryService(repository=PlanBomQueryRepository(db=self._ensure_session()))
            payload = PlanBomCompareQueryRequest(
                left=PlanBomCompareSideRequest(order_no=left_identifier),
                right=PlanBomCompareSideRequest(order_no=right_identifier),
            )
            compare_result = service.compare(payload, trace_id=trace_id)

            result.executed = True
            if compare_result and compare_result.diff_summary:
                result.diff_summary = compare_result.diff_summary
            if compare_result:
                result.changed_count = getattr(compare_result, "changed", 0) or 0
                result.same_count = getattr(compare_result, "same", 0) or 0

        except Exception as exc:
            result.fallback_reason = f"compare_error: {exc}"

        return result

    def try_replay(self, *, log_id: int = 0) -> NqeBomCompareResult:
        """尝试执行 BOM compare replay。

        参数：
            log_id: sys_query_log 中的记录 ID。
        返回：
            统一 NqeBomCompareResult。
        """
        result = NqeBomCompareResult(operation="replay", requested=True)
        if log_id <= 0:
            result.missing_slots = ["log_id"]
            result.fallback_reason = "missing_slots: log_id"
            return result

        try:
            from backend.app.domains.plan_bom.services.query_service import (
                PlanBomQueryService,
            )
            from backend.app.domains.plan_bom.repositories.query_repository import PlanBomQueryRepository

            service = PlanBomQueryService(repository=PlanBomQueryRepository(db=self._ensure_session()))
            replay_result = service.compare_replay(log_id=log_id)

            result.executed = True
            result.log_id = log_id
            if replay_result and replay_result.diff_summary:
                result.diff_summary = replay_result.diff_summary

        except Exception as exc:
            result.fallback_reason = f"replay_error: {exc}"

        return result
