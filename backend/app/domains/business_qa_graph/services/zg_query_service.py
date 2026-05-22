"""
掌柜问数对齐 - SSE 流式查询服务。

使用 graph.astream_events(version="v2") 捕获节点生命周期事件，
单次执行即完成全部流式输出，不与 invoke 双重执行。

节点内部通过 zg_utils._emit_progress 记录日志，
服务层通过 astream_events 捕获 on_chain_start/end 发射 SSE。
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

from backend.app.domains.business_qa_graph.builder_v2 import build_unified_graph
from backend.app.domains.business_qa_graph.schemas.request import BusinessQaGraphRequest
from backend.app.domains.business_qa_graph.schemas.state import build_business_qa_initial_state

logger = logging.getLogger(__name__)

# 节点名 → 进度步骤中文名映射
_NODE_STEP_MAP = {
    "extract_keywords": "抽取关键字",
    "recall_column": "召回字段",
    "recall_value": "召回字段取值",
    "recall_metric": "召回指标",
    "merge_retrieved_info": "合并召回信息",
    "filter_table": "过滤表格",
    "filter_metric": "过滤指标",
    "add_extra_context": "添加额外上下文信息",
    "generate_sql": "生成SQL",
    "validate_sql": "验证SQL",
    "correct_sql": "校正SQL",
    "execute_sql": "执行SQL",
}


class ZgQueryService:
    """掌柜问数对齐版查询服务。"""

    def __init__(self, *, graph: Any = None, db_session: Any = None):
        self._graph = graph
        self._db_session = db_session

    @property
    def graph(self) -> Any:
        if self._graph is None:
            self._graph = build_unified_graph()
        return self._graph

    async def query(self, question: str) -> AsyncGenerator[str, None]:
        """SSE 流式执行查询。

        单次 graph.astream_events 完成：
        - on_chain_start → SSE progress running
        - on_chain_end → SSE progress success
        - on_chain_end LangGraph → SSE result（最终结果）
        """
        request = BusinessQaGraphRequest(question=question, domain_hint=None, trace_id=None)
        initial_state = build_business_qa_initial_state(request)
        if self._db_session:
            initial_state["_db_session"] = self._db_session

        try:
            final_output = None
            async for event in self.graph.astream_events(initial_state, version="v2"):
                kind = event.get("event", "")
                name = event.get("name", "")

                # 节点开始 → running
                if kind == "on_chain_start" and name in _NODE_STEP_MAP:
                    yield self._sse_progress(_NODE_STEP_MAP[name], "running")

                # 节点结束 → success
                elif kind == "on_chain_end" and name in _NODE_STEP_MAP:
                    yield self._sse_progress(_NODE_STEP_MAP[name], "success")

                # Graph 结束 → 收集最终输出
                elif kind == "on_chain_end" and name == "LangGraph":
                    final_output = event.get("data", {}).get("output", {})

            # 输出最终结果
            if final_output and isinstance(final_output, dict):
                exec_result = final_output.get("execution_result", {})
                if exec_result:
                    yield self._sse_result(exec_result)
                else:
                    yield self._sse_result({
                        "answer_summary": final_output.get("user_visible_message", "查询完成。"),
                        "result_table": {"columns": [], "rows": []},
                        "warnings": [],
                    })
            else:
                yield self._sse_result({
                    "answer_summary": "查询完成。",
                    "result_table": {"columns": [], "rows": []},
                    "warnings": [],
                })

        except Exception as exc:
            logger.error("zg_query_failed error=%s", exc)
            yield self._sse_error(str(exc))

    def _sse_progress(self, step: str, status: str) -> str:
        return self._sse_event({"type": "progress", "step": step, "status": status})

    def _sse_result(self, data: dict[str, Any]) -> str:
        return self._sse_event({"type": "result", "data": data})

    def _sse_error(self, message: str) -> str:
        return self._sse_event({"type": "error", "message": message})

    @staticmethod
    def _sse_event(data: dict[str, Any]) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
