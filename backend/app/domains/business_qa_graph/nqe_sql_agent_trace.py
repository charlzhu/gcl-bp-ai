"""NQE 独立 Graph 的 trace、query log 与 replay 辅助函数。

本模块只处理内存态结构化记录，不连接数据库、不写文件，也不把内部候选查询
写入脱敏 query log。需要复现路径时，replay_record 单独保存受控重放输入。
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from backend.app.domains.business_qa_graph.nqe_sql_agent_state import NqeSqlAgentState

QUERY_LOG_SCHEMA_VERSION = "nqe_query_log.v1"
REPLAY_SCHEMA_VERSION = "nqe_replay.v1"

_REPLAY_INPUT_KEYS = (
    "nqe_mode",
    "domain_mode",
    "domain_hint",
    "selected_domain",
    "selected_capability",
    "trace_id",
    "fallback_policy",
    "metadata_version_id",
    "prompt_version_id",
    "context_readiness",
    "force_safety_reject",
    "force_explain_fail",
)
_SENSITIVE_KEY_FRAGMENTS = (
    "token",
    "secret",
    "password",
    "passwd",
    "credential",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "sql",
    "table",
    "column",
    "field",
    "schema",
)
_REPLAY_PLACEHOLDER_QUESTION = "已脱敏重放问题"


def _jsonable(value: Any) -> Any:
    """把任意值转换为稳定 JSON 可序列化结构。

    参数：
        value: 可能来自 Graph state 的任意 Python 值。
    返回：
        可被 json.dumps 稳定编码的值；无法编码时退化为字符串。
    业务逻辑：
        trace/replay 记录必须稳定、可比较，不能因为 set 等对象导致序列化失败。
    """
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))
    except TypeError:
        return str(value)


def _stable_json(value: Any) -> str:
    """生成稳定 JSON 字符串。

    参数：
        value: 需要做摘要或比较的结构化值。
    返回：
        排序后的紧凑 JSON 文本。
    业务逻辑：
        用于生成稳定摘要，避免同一结构因键顺序不同产生不同追踪号。
    """
    return json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest_text(value: str) -> str:
    """计算文本的稳定摘要。

    参数：
        value: 待摘要文本。
    返回：
        sha256 十六进制摘要。
    业务逻辑：
        query log 只保存问题摘要与长度，不保存原始问题文本，降低日志泄露风险。
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _digest_payload(value: Any) -> str:
    """计算结构化载荷的稳定摘要。

    参数：
        value: 需要摘要的结构化对象。
    返回：
        sha256 十六进制摘要。
    业务逻辑：
        log_id 由脱敏摘要构成，既可关联 replay，又不依赖数据库自增主键。
    """
    return _digest_text(_stable_json(value))


def _trace_summary(state: NqeSqlAgentState) -> list[dict[str, str]]:
    """生成脱敏节点轨迹摘要。

    参数：
        state: Graph 最终或中间运行态。
    返回：
        只包含 node/status/summary 的列表。
    业务逻辑：
        trace 摘要不保存内部候选文本、对象白名单或执行结果明细，只用于审计路径。
    """
    summary: list[dict[str, str]] = []
    for step in state.get("trace_steps", []) or []:
        if not isinstance(step, dict):
            continue
        summary.append(
            {
                "node": str(step.get("node") or ""),
                "status": str(step.get("status") or ""),
                "summary": str(step.get("summary") or ""),
            }
        )
    return summary


def _node_names(state: NqeSqlAgentState) -> list[str]:
    """读取节点名称序列。

    参数：
        state: Graph 运行态。
    返回：
        trace_steps 中的节点名序列。
    业务逻辑：
        replay 对比只比较执行形状，不比较内部候选文本。
    """
    return [step["node"] for step in _trace_summary(state) if step.get("node")]


def _safety_summary(state: NqeSqlAgentState) -> dict[str, Any]:
    """提取安全预检脱敏摘要。

    参数：
        state: Graph 运行态。
    返回：
        status、reason_code、violations 等稳定字段，不包含候选文本和对象名。
    业务逻辑：
        安全日志需要可追溯原因码，但不能把被拒绝候选或白名单对象直接写入 query log。
    """
    result = dict(state.get("sql_safety_result") or {})
    violations = sorted(str(item) for item in result.get("violations", []) or [])
    return {
        "status": str(result.get("status") or "not_run"),
        "reason_code": str(result.get("reason_code") or ""),
        "violations": violations,
        "violation_count": len(violations),
        "limit_applied": bool(result.get("limit_applied")),
    }


def _explain_summary(state: NqeSqlAgentState) -> dict[str, Any]:
    """提取解释校验脱敏摘要。

    参数：
        state: Graph 运行态。
    返回：
        status、violations、revision_round。
    业务逻辑：
        解释校验摘要只记录稳定原因码，不记录字段名、表名或候选文本。
    """
    result = dict(state.get("explain_result") or {})
    violations = sorted(str(item) for item in result.get("violations", []) or [])
    return {
        "status": str(result.get("status") or "not_run"),
        "violations": violations,
        "violation_count": len(violations),
        "revision_round": int(result.get("revision_round") or state.get("sql_revision_round", 0) or 0),
    }


def summarize_nqe_run(state: NqeSqlAgentState) -> dict[str, Any]:
    """生成可用于 replay 对比的脱敏运行摘要。

    参数：
        state: Graph 最终态。
    返回：
        终态、执行状态、行数、节点序列和安全/解释摘要。
    业务逻辑：
        replay 只验证路径与关键业务状态是否一致，不比较内部候选文本。
    """
    return {
        "terminal_status": str(state.get("terminal_status") or ""),
        "execution_status": str(state.get("execution_status") or ""),
        "fallback_reason": str(state.get("fallback_reason") or ""),
        "row_count": int(state.get("row_count") or 0),
        "result_truncated": bool(state.get("result_truncated")),
        "sql_revision_round": int(state.get("sql_revision_round") or 0),
        "node_names": _node_names(state),
        "safety_summary": _safety_summary(state),
        "explain_summary": _explain_summary(state),
    }


def build_nqe_query_log_record(state: NqeSqlAgentState) -> dict[str, Any]:
    """构造脱敏 query log 记录。

    参数：
        state: 已进入终态并追加 record 节点后的 Graph state。
    返回：
        可落库/落文件的脱敏 query log 字典。
    业务逻辑：
        query log 记录运行模式、终态、原因码、节点轨迹和摘要；不保存原始候选查询、
        安全候选、召回上下文包、执行明细或用户可见回答，防止内部信息扩散。
    """
    question = str(state.get("question") or "")
    base_record = {
        "schema_version": QUERY_LOG_SCHEMA_VERSION,
        "trace_id": str(state.get("trace_id") or ""),
        "graph_version": str(state.get("graph_version") or ""),
        "nqe_mode": str(state.get("nqe_mode") or ""),
        "domain_mode": str(state.get("domain_mode") or ""),
        "selected_domain": str(state.get("selected_domain") or ""),
        "selected_capability": str(state.get("selected_capability") or ""),
        "terminal_status": str(state.get("terminal_status") or ""),
        "execution_status": str(state.get("execution_status") or ""),
        "fallback_reason": str(state.get("fallback_reason") or ""),
        "row_count": int(state.get("row_count") or 0),
        "result_truncated": bool(state.get("result_truncated")),
        "sql_revision_round": int(state.get("sql_revision_round") or 0),
        "question_digest": _digest_text(question),
        "question_length": len(question),
        "safety_summary": _safety_summary(state),
        "explain_summary": _explain_summary(state),
        "trace_summary": _trace_summary(state),
        "shadow_status": str(dict(state.get("shadow_compare_result") or {}).get("status") or "not_run"),
    }
    base_record["log_id"] = _digest_payload(
        {
            "trace_id": base_record["trace_id"],
            "question_digest": base_record["question_digest"],
            "terminal_status": base_record["terminal_status"],
            "node_names": [step["node"] for step in base_record["trace_summary"]],
        }
    )
    return base_record


def _contains_sensitive_key(value: Any) -> bool:
    """递归判断结构中是否出现敏感或内部元数据键。

    参数：
        value: 任意上下文结构。
    返回：
        任一字典键命中敏感片段时返回 True。
    业务逻辑：
        replay 持久化记录只能保存 allowlist 摘要，不能因嵌套上下文中的密钥、
        内部候选、对象或字段元数据导致信息扩散。
    """
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).lower()
            if any(fragment in key_text for fragment in _SENSITIVE_KEY_FRAGMENTS):
                return True
            if _contains_sensitive_key(child):
                return True
    elif isinstance(value, list | tuple | set):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _replay_context_summary(state: NqeSqlAgentState) -> dict[str, Any]:
    """生成 replay 输入的脱敏上下文摘要。

    参数：
        state: Graph 最终态。
    返回：
        只包含长度、摘要、终态和布尔标记的 allowlist 摘要。
    业务逻辑：
        原始问题、客户端上下文、用户上下文和召回上下文包都可能包含内部候选、
        对象字段元数据或密钥，持久化 replay 只能保存可比对的摘要和风险标记。
    """
    question = str(state.get("question") or "")
    raw_context = {
        "client_context": state.get("client_context"),
        "user_context": state.get("user_context"),
        "retrieval_context_package": state.get("retrieval_context_package"),
    }
    return {
        "question_digest": _digest_text(question),
        "question_length": len(question),
        "terminal_status": str(state.get("terminal_status") or ""),
        "context_readiness": str(state.get("context_readiness") or ""),
        "had_client_context": bool(state.get("client_context")),
        "had_user_context": bool(state.get("user_context")),
        "had_retrieval_context": bool(state.get("retrieval_context_package")),
        "sensitive_key_seen": _contains_sensitive_key(raw_context),
    }


def build_nqe_replay_input(state: NqeSqlAgentState) -> dict[str, Any]:
    """从最终态反推脱敏最小重放输入。

    参数：
        state: Graph 最终态。
    返回：
        可持久化的 replay 输入摘要；不包含原始问题、客户端/用户上下文或召回包。
    业务逻辑：
        replay 输入采用 allowlist：只保留灰度模式、追踪版本等低敏控制字段，
        原始上下文统一替换为摘要。实际重放时再由 replay 函数注入内存态合成上下文。
    """
    replay_input: dict[str, Any] = {"question": _REPLAY_PLACEHOLDER_QUESTION}
    for key in _REPLAY_INPUT_KEYS:
        if key in state:
            replay_input[key] = deepcopy(_jsonable(state[key]))
    replay_input["replay_context_summary"] = _replay_context_summary(state)
    return replay_input


def build_nqe_replay_record(state: NqeSqlAgentState, query_log_record: dict[str, Any]) -> dict[str, Any]:
    """构造 replay 记录。

    参数：
        state: Graph 最终态。
        query_log_record: 同一次运行生成的脱敏 query log。
    返回：
        包含 replay_input 与 expected_summary 的重放记录。
    业务逻辑：
        query log 用于审计，replay record 用于内部可复现；两者通过 log_id 关联。
    """
    replay_input = build_nqe_replay_input(state)
    expected_summary = summarize_nqe_run(state)
    return {
        "schema_version": REPLAY_SCHEMA_VERSION,
        "query_log_id": str(query_log_record.get("log_id") or ""),
        "trace_id": str(query_log_record.get("trace_id") or ""),
        "replay_input": replay_input,
        "replay_input_digest": _digest_payload(replay_input),
        "expected_summary": expected_summary,
    }


def compare_nqe_replay_summary(expected_summary: dict[str, Any], actual_state: NqeSqlAgentState) -> dict[str, Any]:
    """比较 replay 期望摘要与实际重放结果。

    参数：
        expected_summary: replay_record 中保存的期望摘要。
        actual_state: 重放后得到的 Graph 最终态。
    返回：
        matched 与关键字段对比结果。
    业务逻辑：
        replay 只校验终态、行数、修正轮次和节点序列，避免比较内部候选文本。
    """
    actual_summary = summarize_nqe_run(actual_state)
    expected = dict(expected_summary or {})
    comparable_keys = ("terminal_status", "execution_status", "row_count", "sql_revision_round", "node_names")
    mismatches = [key for key in comparable_keys if expected.get(key) != actual_summary.get(key)]
    return {
        "schema_version": "nqe_replay_summary.v1",
        "matched": not mismatches,
        "mismatches": mismatches,
        "expected_terminal_status": str(expected.get("terminal_status") or ""),
        "actual_terminal_status": str(actual_summary.get("terminal_status") or ""),
        "expected_node_count": len(expected.get("node_names") or []),
        "actual_node_count": len(actual_summary.get("node_names") or []),
    }
