"""NQE 统一 SQL Agent SSE 流式查询接口。

NQE-FE-1: text/event-stream 格式。
NQE-FE-5R: disambiguation continue flow。
"""

from __future__ import annotations

import json, time, logging, uuid
from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from backend.app.domains.business_qa_graph.nqe_sql_agent_graph import build_nqe_sql_agent_graph

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/nqe", tags=["nqe"])

_graph = build_nqe_sql_agent_graph()

# FE-5R: in-memory trace store for disambiguation continue
_pending_traces: dict[str, dict] = {}  # trace_id → {question, domain, candidates, ...}


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
            yield _sse_event("safety_checked", {"trace_id": tid, "safe": safety.get("status") == "pass"})

            explain = final.get("explain_result", {})
            yield _sse_event("explain_checked", {"trace_id": tid, "passed": explain.get("status") == "pass"})

            # 候选消歧
            candidates = final.get("disambiguation_candidates")
            if candidates:
                continue_token = str(uuid.uuid4())
                _pending_traces[continue_token] = {"question": question, "trace_id": tid}
                yield _sse_event("disambiguation_required", {
                    "trace_id": tid, "continue_token": continue_token,
                    "candidates": candidates,
                    "scope": final.get("candidate_scope", "unknown"),
                    "message": final.get("disambiguation_message", "请选择目标对象"),
                })

            result = final.get("structured_result", {})
            rows_count = final.get("row_count", 0)
            yield _sse_event("sql_executed", {"trace_id": tid, "row_count": rows_count})

            yield _sse_event("result", {"trace_id": tid, "status": final.get("terminal_status"),
                "answer": result.get("answer",""), "columns": result.get("columns",[]),
                "rows": result.get("rows",[])[:100], "row_count": rows_count,
                "metrics": result.get("metrics",[]), "cards": result.get("cards",[]),
                "duration_ms": result.get("duration_ms",0), "fallback_used": False,
                "fallback_reason": final.get("fallback_reason",""),
            })

        except Exception as e:
            yield _sse_event("error", {"trace_id": tid, "error": str(e)[:500]})
        finally:
            yield _sse_event("done", {"trace_id": tid})
            _pending_traces.pop(tid, None)

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/query/stream/continue")
async def nqe_query_continue(continue_token: str = Query(...), candidate_key: str = Query(...)):
    """NQE-FE-5R: 候选消歧继续查询。"""
    pending = _pending_traces.get(continue_token)
    if not pending:
        async def error_gen():
            yield _sse_event("error", {"trace_id": "", "error": "continue_token expired or invalid"})
            yield _sse_event("done", {})
        return StreamingResponse(error_gen(), media_type="text/event-stream")

    question = str(pending["question"])
    tid = str(pending.get("trace_id", ""))
    del _pending_traces[continue_token]

    async def generate():
        try:
            yield _sse_event("progress", {"step": "disambiguation_selected", "trace_id": tid, "message": f"已选择候选 {candidate_key}"})
            final = _graph.invoke({"question": question, "nqe_mode": "on", "trace_id": tid, "nqe_disambiguation_selected": candidate_key})

            nodes = [t.get("node","") for t in final.get("trace",[])]
            for i, node in enumerate(nodes):
                yield _sse_event("progress", {"step": node, "trace_id": tid, "index": i, "message": f"已完成 {node}"})

            sql = str(final.get("generated_sql","")).strip()
            if sql:
                yield _sse_event("sql_generated", {"trace_id": tid, "sql": sql[:500]})

            safety = final.get("sql_safety_result", {})
            yield _sse_event("safety_checked", {"trace_id": tid, "safe": safety.get("status") == "pass"})
            explain = final.get("explain_result", {})
            yield _sse_event("explain_checked", {"trace_id": tid, "passed": explain.get("status") == "pass"})

            result = final.get("structured_result", {})
            rows_count = final.get("row_count", 0)
            yield _sse_event("sql_executed", {"trace_id": tid, "row_count": rows_count})

            yield _sse_event("result", {"trace_id": tid, "status": final.get("terminal_status"),
                "answer": result.get("answer",""), "columns": result.get("columns",[]),
                "rows": result.get("rows",[])[:100], "row_count": rows_count,
                "metrics": result.get("metrics",[]), "cards": result.get("cards",[]),
                "duration_ms": result.get("duration_ms",0), "fallback_used": False,
                "fallback_reason": final.get("fallback_reason",""),
            })

        except Exception as e:
            yield _sse_event("error", {"trace_id": tid, "error": str(e)[:500]})
        finally:
            yield _sse_event("done", {"trace_id": tid})

    return StreamingResponse(generate(), media_type="text/event-stream")
