from __future__ import annotations

import logging
from typing import Any

from backend.app.core.config import settings
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaResult
from backend.app.domains.logistics.schemas.llm_understanding import LogisticsLlmGuardrailDecision
from backend.app.domains.plan_bom.schemas.qa import PlanBomQaResponse
from backend.app.domains.query_planning.services.shadow_snapshot_builder import QueryPlanningV2ShadowSnapshotBuilder

logger = logging.getLogger(__name__)


class QueryPlanningV2ResponseMetaExposureService:
    """构建可选暴露到正式响应中的 Query Planning V2 轻量 meta。

    说明：
        1. 本服务只在请求显式开启、feature flag 开启且非生产环境时返回 meta；
        2. 生产环境在正式用户权限模块接入前一律 fail-closed；
        3. meta 只包含 strategy / query_key / comparison / risk_tags 等审计摘要；
        4. 不暴露原始问题、完整 trace、request_payload、query_result、raw_result 或完整 query_plan_v2_shadow。
    """

    SAFE_COMPARISON_KEYS = (
        "schema_version",
        "domain",
        "formal_status",
        "formal_intent",
        "formal_query_key",
        "formal_result_count",
        "shadow_strategy",
        "shadow_query_key",
        "query_key_matched",
        "matched",
        "risk_tags",
        "guardrail_status",
        "shadow_only",
        "llm_can_execute",
        "sql_generation_allowed",
    )

    def __init__(self, builder: QueryPlanningV2ShadowSnapshotBuilder | None = None) -> None:
        """初始化响应 meta 暴露服务。

        参数：
            builder: shadow 快照构建器，测试可注入。
        返回：无返回值。
        """

        self.builder = builder or QueryPlanningV2ShadowSnapshotBuilder()

    def should_expose(self, *, requested: bool) -> bool:
        """判断当前请求是否允许暴露 Query Planning V2 meta。

        参数：
            requested: 请求体中是否显式要求返回 meta。
        返回：
            True 表示允许返回轻量 meta；False 表示必须隐藏。
        业务逻辑：生产环境未接入正式权限模块前 fail-closed，避免用临时 header/token 绕过。
        """

        if not requested:
            return False
        if not bool(getattr(settings, "query_planning_v2_response_meta_enabled", False)):
            return False
        app_env = str(getattr(settings, "app_env", "local") or "local").strip().lower()
        return app_env not in {"prod", "production"}

    def build_logistics_meta(
        self,
        *,
        requested: bool,
        question: str,
        result: LogisticsDataQaResult,
        trace_id: str | None = None,
        guardrail_decision: LogisticsLlmGuardrailDecision | None = None,
    ) -> dict[str, Any] | None:
        """为物流正式响应构建可选 Query Planning V2 meta。

        参数：
            requested: 请求体是否显式开启 meta。
            question: 用户原始问题，仅用于构建 shadow 快照，最终不会暴露。
            result: 已完成的物流正式响应。
            trace_id: 请求追踪号。
            guardrail_decision: 可选 Guardrail 决策，通常正式 API 响应阶段为空。
        返回：
            允许暴露时返回安全 meta；否则返回 None。
        """

        if not self.should_expose(requested=requested):
            return None
        try:
            snapshot = self.builder.build_logistics_snapshot(
                question=question,
                result=result,
                trace_id=trace_id,
                guardrail_decision=guardrail_decision,
            )
            return self.build_from_shadow_snapshot(
                snapshot=snapshot,
                trace_id=trace_id,
                history_log_id=result.history_log_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("build logistics query_plan_v2 response meta failed: %s", exc)
            return None

    def build_plan_bom_meta(
        self,
        *,
        requested: bool,
        question: str,
        response: PlanBomQaResponse,
        trace_id: str | None = None,
    ) -> dict[str, Any] | None:
        """为计划 BOM 正式响应构建可选 Query Planning V2 meta。

        参数：
            requested: 请求体是否显式开启 meta。
            question: 用户原始问题，仅用于构建 shadow 快照，最终不会暴露。
            response: 已完成的 BOM 正式响应。
            trace_id: 请求追踪号。
        返回：
            允许暴露时返回安全 meta；否则返回 None。
        """

        if not self.should_expose(requested=requested):
            return None
        try:
            snapshot = self.builder.build_plan_bom_snapshot(
                question=question,
                response=response,
                trace_id=trace_id,
            )
            return self.build_from_shadow_snapshot(snapshot=snapshot, trace_id=trace_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("build plan bom query_plan_v2 response meta failed: %s", exc)
            return None

    @classmethod
    def build_from_shadow_snapshot(
        cls,
        *,
        snapshot: dict[str, Any],
        trace_id: str | None = None,
        history_log_id: int | None = None,
    ) -> dict[str, Any]:
        """从完整 shadow 快照中提取可暴露的轻量 meta。

        参数：
            snapshot: 完整 query_plan_v2_shadow 快照。
            trace_id: 请求追踪号。
            history_log_id: 可选查询历史 ID。
        返回：
            可放入正式响应 `query_plan_v2_meta` 的安全摘要。
        """

        comparison = snapshot.get("comparison") if isinstance(snapshot.get("comparison"), dict) else {}
        safe_comparison = {key: comparison.get(key) for key in cls.SAFE_COMPARISON_KEYS if key in comparison}
        risk_tags = cls._safe_list(snapshot.get("risk_tags") or safe_comparison.get("risk_tags"))
        policy = snapshot.get("execution_policy") if isinstance(snapshot.get("execution_policy"), dict) else {}
        return {
            "schema_version": "query_plan_v2.response_meta.v1",
            "enabled": True,
            "domain": snapshot.get("domain") or safe_comparison.get("domain"),
            "trace_id": trace_id,
            "history_log_id": history_log_id,
            "strategy": snapshot.get("strategy") or safe_comparison.get("shadow_strategy"),
            "query_key": snapshot.get("query_key") or safe_comparison.get("shadow_query_key"),
            "intent": snapshot.get("intent"),
            "matched": safe_comparison.get("matched"),
            "risk_tags": risk_tags,
            "comparison": safe_comparison,
            "shadow_only": policy.get("shadow_only", safe_comparison.get("shadow_only", True)),
            "llm_can_execute": policy.get("llm_can_execute", safe_comparison.get("llm_can_execute", False)),
            "sql_generation_allowed": policy.get(
                "sql_generation_allowed",
                safe_comparison.get("sql_generation_allowed", False),
            ),
        }

    @staticmethod
    def _safe_list(value: Any) -> list[str]:
        """把风险标签转换为字符串列表。"""

        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item)]


__all__ = ["QueryPlanningV2ResponseMetaExposureService"]
