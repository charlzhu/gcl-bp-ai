"""NQE-S3 shadow_compare_node：NL2SQL 与旧链路结果 shadow 对比节点。

本节点在 execute_node 之后运行，调用 NL2SQL adapter 获取完整 NL2SQL 结果，
与旧链路 execution_result 对比，记录差异到 state 和 JSONL 文件。

不阻断正常返回，只做 shadow 记录。
"""

from __future__ import annotations

import logging
from typing import Any

from backend.app.domains.business_qa_graph.schemas.event import BusinessQaGraphEvent
from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState

logger = logging.getLogger(__name__)


def shadow_compare_node(
    state: BusinessQaGraphState,
    *,
    nl2sql_adapter: Any = None,
    compare_service: Any = None,
) -> BusinessQaGraphState:
    """执行 NL2SQL shadow compare：调用 NL2SQL 链路获取结果并与旧链路对比。

    参数：
        state: 经 execute_node 处理后的 Graph 运行态。
            execution_result 中已有旧链路结果。
        nl2sql_adapter: 可注入的 NL2SQL adapter 实例。
            需要提供 build_full_result(question, trace_id) 方法。
            默认构造 Nl2SqlGraphAdapter。
        compare_service: 可注入的 ShadowCompareService 实例。
            默认构造新实例。
    返回：
        写入 nl2sql_result 和 shadow_comparison 的新 state。
        不改变 status/execution_status 等主链路字段。
    业务逻辑：
        1. 仅物流域执行对比（plan_bom/unknown 域跳过）。
        2. 调用 NL2SQL adapter 获取完整结果。
        3. 使用 ShadowCompareService 对比两套结果。
        4. 将对比结果写入 JSONL 文件。
        5. 任何异常 fail-closed，不中断主链路。
    """

    question = str(state.get("question") or "").strip()
    domain = state.get("domain", "unknown")
    trace_id = state.get("trace_id")
    trace = list(state.get("trace") or [])
    execution_result = state.get("execution_result", {})

    # ---- 门控：仅物流域执行 shadow compare ----
    if domain != "logistics":
        event = BusinessQaGraphEvent(
            node="shadow_compare",
            event_type="shadow_compare_skipped",
            message=f"业务域 {domain} 非物流域，跳过 shadow compare。",
            payload={"domain": domain, "reason": "non_logistics_domain"},
        )
        next_state: BusinessQaGraphState = dict(state)
        next_state["trace"] = [*trace, event.model_dump(mode="json")]
        next_state["nl2sql_result"] = {"status": "skipped", "reason": "non_logistics_domain"}
        next_state["shadow_comparison"] = {
            "overall_match": False,
            "status_match": False,
            "mismatch_reasons": [f"非物流域（domain={domain}），跳过对比"],
        }
        return next_state

    # ---- 解析 NL2SQL adapter ----
    adapter = _resolve_adapter(nl2sql_adapter)
    svc = _resolve_compare_service(compare_service)

    # ---- 第一步：运行 NL2SQL 链路 ----
    nl2sql_result: dict[str, Any]
    try:
        nl2sql_result = adapter.build_full_result(question, trace_id=trace_id)
    except Exception as exc:
        # NL2SQL 链路异常，fail-closed
        logger.warning(
            "shadow_compare_node NL2SQL 链路异常（不影响主链路）：%s",
            type(exc).__name__,
            exc_info=True,
        )
        nl2sql_result = {
            "status": "error",
            "error": "nl2sql_pipeline_failed",
            "row_count": 0,
        }

    # ---- 第二步：对比两套结果 ----
    try:
        comparison = svc.compare(execution_result, nl2sql_result)
    except Exception as exc:
        logger.warning(
            "shadow_compare_node 对比计算异常（不影响主链路）：%s",
            type(exc).__name__,
            exc_info=True,
        )
        comparison = {
            "overall_match": False,
            "status_match": False,
            "mismatch_reasons": [f"对比计算异常：{type(exc).__name__}"],
        }

    # ---- 第三步：写入 JSONL ----
    try:
        old_sig = svc.extract_signature(execution_result)
        nl2sql_sig = svc.extract_signature(nl2sql_result)
        svc.write_to_jsonl(
            question=question,
            old_signature=old_sig,
            nl2sql_signature=nl2sql_sig,
            comparison=comparison,
            trace_id=trace_id,
        )
    except Exception as exc:
        logger.warning(
            "shadow_compare_node JSONL 写入异常（不影响主链路）：%s",
            type(exc).__name__,
            exc_info=True,
        )

    # ---- 第四步：写入 state ----
    event = BusinessQaGraphEvent(
        node="shadow_compare",
        event_type="shadow_compare_complete",
        message=(
            f"Shadow compare 完成：overall_match={comparison.get('overall_match')}，"
            f"status_match={comparison.get('status_match')}，"
            f"row_count_diff={comparison.get('row_count_diff')}"
        ),
        payload={
            "domain": domain,
            "overall_match": comparison.get("overall_match"),
            "status_match": comparison.get("status_match"),
            "row_count_match": comparison.get("row_count_match"),
            "row_count_diff": comparison.get("row_count_diff"),
            "mismatch_reasons": comparison.get("mismatch_reasons", []),
        },
    )

    next_state = dict(state)
    next_state["trace"] = [*trace, event.model_dump(mode="json")]
    # 清洗 nl2sql_result：确保不包含技术细节
    next_state["nl2sql_result"] = {
        "status": nl2sql_result.get("status", ""),
        "row_count": nl2sql_result.get("row_count", 0),
        "answer_summary": str(nl2sql_result.get("answer_summary", ""))[:200],
        "supported": nl2sql_result.get("supported"),
        "needs_clarification": nl2sql_result.get("needs_clarification"),
        "status_code": nl2sql_result.get("status_code", ""),
    }
    next_state["shadow_comparison"] = comparison

    return next_state


# =============================================================================
# 内部辅助函数
# =============================================================================


def _resolve_adapter(nl2sql_adapter: Any = None) -> Any:
    """构造或返回已注入的 NL2SQL adapter。

    参数：
        nl2sql_adapter: 可注入的 adapter 实例（需要有 build_full_result 方法）。
    返回：
        adapter 实例。
    业务逻辑：
        默认使用 Nl2SqlGraphAdapter（已有 build_shadow 方法，NQE-S3 扩展 build_full_result）。
    """
    if nl2sql_adapter is not None:
        return nl2sql_adapter
    try:
        from backend.app.domains.business_qa_graph.nl2sql_adapter import (
            Nl2SqlGraphAdapter,
        )
        return Nl2SqlGraphAdapter()
    except Exception:
        # 如果无法构造，返回空 adapter
        return _NullNl2SqlAdapter()


def _resolve_compare_service(compare_service: Any = None) -> Any:
    """构造或返回已注入的 ShadowCompareService。

    参数：
        compare_service: 可注入的服务实例。
    返回：
        ShadowCompareService 实例。
    """
    if compare_service is not None:
        return compare_service
    try:
        from backend.app.domains.business_qa_graph.services.shadow_compare import (
            ShadowCompareService,
        )
        return ShadowCompareService()
    except Exception:
        return _NullCompareService()


class _NullNl2SqlAdapter:
    """空 NL2SQL adapter，当真实 adapter 不可用时使用。"""

    def build_full_result(self, question: str, trace_id: str | None = None) -> dict[str, Any]:
        """返回安全的空结果。"""
        return {"status": "error", "error": "nl2sql_adapter_unavailable", "row_count": 0}


class _NullCompareService:
    """空对比服务，当真实服务不可用时使用。"""

    def compare(self, old_result: dict[str, Any], nl2sql_result: dict[str, Any]) -> dict[str, Any]:
        """返回安全的空对比结果。"""
        return {"overall_match": False, "status_match": False, "mismatch_reasons": []}

    def extract_signature(self, result: dict[str, Any]) -> dict[str, Any]:
        """返回安全的空签名。"""
        return {}

    def write_to_jsonl(self, **kwargs: Any) -> None:
        """不执行写操作。"""
        pass
