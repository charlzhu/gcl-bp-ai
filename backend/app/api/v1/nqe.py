"""NQE 统一 SQL Agent SSE 流式查询接口。

NQE-FE-1: text/event-stream 格式，实时推送查询进度、SQL 生成、EXPLAIN、执行结果。"""

from __future__ import annotations

import json, time, logging
from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from backend.app.domains.business_qa_graph.nqe_sql_agent_graph import build_nqe_sql_agent_graph

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/nqe", tags=["nqe"])

_graph = build_nqe_sql_agent_graph()


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/query/stream")
async def nqe_query_stream(question: str = Query(...), trace_id: str | None = None):
    """NQE SQL Agent SSE 流式查询。"""
    tid = trace_id or f"nqe-{int(time.time()*1000)}"

    async def generate():
        try:
            yield _sse_event("progress", {"step": "domain_routed", "trace_id": tid, "message": "已接收查询"})
            final = _graph.invoke({"question": question, "nqe_mode": "on", "trace_id": tid})

            nodes = [t.get("node","") for t in final.get("trace",[])]
            for i, node in enumerate(nodes):
                yield _sse_event("progress", {"step": node, "trace_id": tid, "index": i, "message": f"已完成 {node}"})

            sql = str(final.get("generated_sql","")).strip()
            if sql:
                yield _sse_event("sql_generated", {"trace_id": tid, "sql": sql[:500]})

            safety = final.get("sql_safety_result", {})
            is_safe = safety.get("status") == "pass"
            yield _sse_event("safety_checked", {"trace_id": tid, "safe": is_safe})

            explain = final.get("explain_result", {})
            yield _sse_event("explain_checked", {"trace_id": tid, "passed": explain.get("status") == "pass"})

            result = final.get("structured_result", {})
            rows_count = final.get("row_count", 0)
            yield _sse_event("sql_executed", {"trace_id": tid, "row_count": rows_count})

            yield _sse_event("result", {"trace_id": tid, "status": final.get("terminal_status"), "answer": result.get("answer",""), "columns": result.get("columns",[]), "rows": result.get("rows",[])[:100], "row_count": rows_count})

        except Exception as e:
            yield _sse_event("error", {"trace_id": tid, "error": str(e)[:500]})
        finally:
            yield _sse_event("done", {"trace_id": tid})

    return StreamingResponse(generate(), media_type="text/event-stream")
