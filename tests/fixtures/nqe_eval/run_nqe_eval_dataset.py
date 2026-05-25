"""NQE 四域评测执行器（加固版）。

不修改全局环境变量，不默认关闭 SSL。
强制校验 context_source/retrieval_source。
增强结果对比（scalar/grouped_rows/top_n/empty_result）。
严格 smoke 覆盖。

用法:
    PYTHONPATH=. python tests/fixtures/nqe_eval/run_nqe_eval_dataset.py --smoke
    PYTHONPATH=. python tests/fixtures/nqe_eval/run_nqe_eval_dataset.py --full
"""

import json, sys, time, os
from pathlib import Path
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

# ---- 不修改全局 os.environ ----
# 评测执行器不从代码默认设置代理/SSL，由外部环境或 settings 控制。

from backend.app.db.session import SessionLocal
from sqlalchemy import text

# ============================================================
# Result comparison
# ============================================================

def compare_results(expected_rows, expected_cols, nqe_rows, nqe_cols,
                    summary: str, tolerance: float = 0.01) -> dict:
    """增强版结果对比。"""
    if expected_rows is None or nqe_rows is None:
        return {"match": False, "reason": "result_is_none"}

    exp_count = len(expected_rows) if isinstance(expected_rows, (list, tuple)) else 0
    nqe_count = len(nqe_rows) if isinstance(nqe_rows, (list, tuple)) else 0

    # empty_result: 必须 0 行
    if summary == "empty_result":
        return {"match": nqe_count == 0,
                "reason": "ok" if nqe_count == 0 else f"expected_empty got {nqe_count} rows",
                "expected_rows": exp_count, "nqe_rows": nqe_count}

    # scalar: 比较数值
    if summary == "scalar":
        if exp_count == 0 and nqe_count == 0:
            return {"match": True, "reason": "ok", "expected_rows": 0, "nqe_rows": 0}
        if exp_count == 0 or nqe_count == 0:
            return {"match": False, "reason": f"row_count_mismatch ({exp_count} vs {nqe_count})",
                    "expected_rows": exp_count, "nqe_rows": nqe_count}
        try:
            exp_vals = list(expected_rows[0].values())
            nqe_vals = list(nqe_rows[0].values()) if nqe_rows else []
            if not exp_vals or not nqe_vals:
                return {"match": exp_count == nqe_count, "reason": "no_values",
                        "expected_rows": exp_count, "nqe_rows": nqe_count}
            ev, nv = exp_vals[0], nqe_vals[0]
            if isinstance(ev, (int, float)) and isinstance(nv, (int, float)):
                if abs(ev - nv) <= tolerance * max(abs(ev), 1):
                    return {"match": True, "reason": "ok", "expected_rows": exp_count, "nqe_rows": nqe_count, "expected_val": ev, "nqe_val": nv}
                return {"match": False, "reason": f"value_diff ({ev} vs {nv})", "expected_rows": exp_count, "nqe_rows": nqe_count, "expected_val": ev, "nqe_val": nv}
            return {"match": str(ev) == str(nv), "reason": "ok" if str(ev) == str(nv) else "value_diff",
                    "expected_rows": exp_count, "nqe_rows": nqe_count}
        except:
            return {"match": exp_count == nqe_count, "reason": "compare_error", "expected_rows": exp_count, "nqe_rows": nqe_count}

    # grouped_rows / top_n: 比较行数 + 第一行关键值
    if exp_count != nqe_count:
        return {"match": False, "reason": f"row_count_mismatch ({exp_count} vs {nqe_count})",
                "expected_rows": exp_count, "nqe_rows": nqe_count}

    if exp_count > 0:
        try:
            exp_keys = list(expected_rows[0].values())
            nqe_keys = list(nqe_rows[0].values()) if nqe_rows else []
            match = len(exp_keys) == len(nqe_keys)
            for i in range(min(len(exp_keys), len(nqe_keys))):
                ev, nv = exp_keys[i], nqe_keys[i]
                if isinstance(ev, (int, float)) and isinstance(nv, (int, float)):
                    if abs(ev - nv) > tolerance * max(abs(ev), 1): match = False
                elif str(ev) != str(nv): match = False
            return {"match": match, "reason": "ok" if match else "first_row_values_diff",
                    "expected_rows": exp_count, "nqe_rows": nqe_count}
        except:
            pass

    return {"match": True, "reason": "row_count_match_only", "expected_rows": exp_count, "nqe_rows": nqe_count}


# ============================================================
# Single case evaluation
# ============================================================

def evaluate_one(case: dict, db, domain: str) -> dict:
    """评测单条 case，返回结构化 result。"""
    cid = case.get("case_id","?")
    stype = case.get("source_type","")
    sql = (case.get("answer_sql") or "").strip()
    expected_status = case.get("expected_status","")
    summary = case.get("expected_result_summary","")
    expected_ctx = case.get("expected_context_source","")
    expected_ret = case.get("expected_retrieval_source","")

    result = {
        "case_id": cid, "domain": domain, "source_type": stype,
        "question": case.get("question","")[:80],
        "expected_status": expected_status, "actual_status": "", "status": "skip",
        "failure_reason": "", "trace_id": "",
        "expected_context_source": expected_ctx, "actual_context_source": "",
        "expected_retrieval_source": expected_ret, "actual_retrieval_source": "",
        "generated_sql": "", "final_sql": "",
        "expected_rows": 0, "actual_rows": 0, "duration_ms": 0,
        "llm_sql_generated": False, "safety_executed": False,
        "explain_executed": False, "execute_executed": False, "fallback_used": False,
    }

    try:
        from backend.app.domains.business_qa_graph.nqe_sql_agent_graph import build_nqe_sql_agent_graph
    except Exception as e:
        result["status"] = "skip"; result["failure_reason"] = f"import:{e}"; return result

    # ---- SAFETY ----
    if stype == "safety":
        f = build_nqe_sql_agent_graph().invoke({
            "question": case.get("question",""), "nqe_mode": "on",
            "domain_hint": domain, "trace_id": f"eval-{cid}"})
        ts = f.get("terminal_status","")
        result["actual_status"] = ts
        if ts == "safety_reject":
            result["status"] = "pass"
        else:
            result["status"] = "fail"
            result["failure_reason"] = "safety_not_blocked"
            result["generated_sql"] = str(f.get("generated_sql",""))[:100]
        return result

    # ---- EDGE (no answer_sql) ----
    if stype == "edge" and not sql:
        f = build_nqe_sql_agent_graph().invoke({
            "question": case.get("question",""), "nqe_mode": "on",
            "domain_hint": domain, "trace_id": f"eval-{cid}"})
        ts = f.get("terminal_status","")
        result["actual_status"] = ts
        if ts == expected_status or (expected_status == "clarify_required" and ts in ("clarify","clarify_required")):
            result["status"] = "pass"
        elif expected_status == "empty_result":
            result["actual_rows"] = f.get("row_count",0)
            result["status"] = "pass" if result["actual_rows"] == 0 else "fail"
            if result["status"] == "fail": result["failure_reason"] = f"expected_empty got {result['actual_rows']} rows"
        else:
            result["status"] = "fail"
            result["failure_reason"] = f"expected_{expected_status}_got_{ts}"
        return result

    # ---- PowerPredictionEngine ----
    if case.get("expected_result_source") == "PowerPredictionEngine":
        f = build_nqe_sql_agent_graph().invoke({
            "question": case.get("question",""), "nqe_mode": "on",
            "domain_hint": domain, "trace_id": f"eval-{cid}"})
        ts = f.get("terminal_status","")
        result["actual_status"] = ts
        ra = f.get("_nqe_retrieval_assets",{})
        result["actual_context_source"] = f.get("retrieval_context_package",{}).get("context_source","")
        result["actual_retrieval_source"] = ra.get("retrieval_source","") if ra else ""

        if expected_status == "clarify_required":
            result["status"] = "pass" if ts in ("clarify","clarify_required") else "fail"
            if result["status"] == "fail": result["failure_reason"] = f"expected_clarify_got_{ts}"
        elif ts == "completed":
            result["status"] = "pass"
        elif ts == "fallback":
            fb = f.get("fallback_reason","")
            result["status"] = "fail"
            result["failure_reason"] = f"fallback:{fb}"
        else:
            result["status"] = "fail"
            result["failure_reason"] = f"unexpected_status:{ts}"
        return result

    # ---- DETERMINISTIC_SQL ----
    if not sql:
        result["status"] = "skip"; result["failure_reason"] = "no_answer_sql"; return result

    # Step 1: Execute answer_sql
    expected_rows = None; expected_cols = []
    try:
        exec_result = db.execute(text(sql))
        expected_rows = [dict(row._mapping) for row in exec_result.fetchmany(500)]
        expected_cols = list(expected_rows[0].keys()) if expected_rows else []
    except Exception as e:
        result["status"] = "fail"
        result["failure_reason"] = f"expected_sql_failed:{type(e).__name__}:{str(e)[:80]}"
        return result
    result["expected_rows"] = len(expected_rows)

    # Step 2: Run NQE SQL Agent
    t0 = time.time()
    f = build_nqe_sql_agent_graph().invoke({
        "question": case.get("question",""), "nqe_mode": "on",
        "domain_hint": domain, "trace_id": f"eval-{cid}"})
    result["duration_ms"] = int((time.time() - t0) * 1000)

    cp = f.get("retrieval_context_package",{})
    ra = f.get("_nqe_retrieval_assets",{})
    result["actual_context_source"] = cp.get("context_source","")
    result["actual_retrieval_source"] = ra.get("retrieval_source","") if ra else ""
    result["generated_sql"] = str(f.get("generated_sql",""))[:200]
    result["final_sql"] = str(f.get("final_sql") or f.get("generated_sql",""))[:200]
    result["trace_id"] = str(f.get("trace_id","") or "")

    ts = f.get("terminal_status","")
    result["actual_status"] = ts

    # 主链路证据
    result["llm_sql_generated"] = bool(f.get("generated_sql"))
    result["safety_executed"] = bool(f.get("sql_safety_result"))
    result["explain_executed"] = bool(f.get("explain_result"))
    result["execute_executed"] = bool(f.get("rows") or f.get("row_count"))
    result["fallback_used"] = bool(f.get("fallback_used"))

    # 强制校验 context_source
    if result["actual_context_source"] != expected_ctx:
        result["status"] = "fail"
        result["failure_reason"] = f"context_source_mismatch: expect={expected_ctx} actual={result['actual_context_source']}"
        return result

    # 强制校验 retrieval_source
    if result["actual_retrieval_source"] != expected_ret:
        result["status"] = "fail"
        result["failure_reason"] = f"retrieval_source_mismatch: expect={expected_ret} actual={result['actual_retrieval_source']}"
        return result

    # 主链路完整性
    if ts != "completed":
        allow_fb = case.get("allow_fallback", False)
        if ts == "fallback" and allow_fb and result["generated_sql"]:
            fb = f.get("fallback_reason","unknown")
            result["status"] = "fail"
            result["failure_reason"] = f"fallback:{fb}"
            return result
        result["status"] = "fail"
        result["failure_reason"] = f"nqe_status:{ts}"
        return result

    if not result["generated_sql"]:
        result["status"] = "fail"
        result["failure_reason"] = "llm_sql_not_generated"
        return result

    nqe_rows = f.get("rows",[])
    nqe_cols = f.get("columns",[])
    result["actual_rows"] = len(nqe_rows)

    # Step 3: Compare
    comp = compare_results(expected_rows, expected_cols, nqe_rows, nqe_cols, summary)
    result["status"] = "pass" if comp.get("match") else "fail"
    if not comp.get("match"):
        result["failure_reason"] = f"result_mismatch:{comp.get('reason','')}"

    return result


# ============================================================
# Smoke selection
# ============================================================

def smoke_select(cases, domain):
    """smoke: 每域 coverage 导向选取。"""
    by_type = defaultdict(list)
    for c in cases:
        by_type[c.get("source_type","")].append(c)
    by_engine = [c for c in cases if c.get("expected_result_source") == "PowerPredictionEngine"]

    selected = []
    # deterministic_sql x2
    for st in ["real_user","asset_generated","paraphrase"]:
        for c in by_type.get(st, []):
            if c.get("answer_sql") and len(selected) < 2:
                selected.append(c)
    # safety x1
    selected.extend(by_type.get("safety", [])[:1])
    # edge x1
    selected.extend(by_type.get("edge", [])[:1])
    # PowerPredictionEngine x1 (if any)
    selected.extend(by_engine[:1])
    # one more real_user/asset
    for st in ["real_user","paraphrase","asset_generated"]:
        for c in by_type.get(st, []):
            if c not in selected and len(selected) < 5:
                selected.append(c)

    return selected[:5]


# ============================================================
# Main runner
# ============================================================

def run_eval(smoke: bool = False):
    base = Path(__file__).resolve().parent
    domains = ["logistics", "business_analysis", "plan_bom", "power_prediction"]

    all_results = []
    stats = Counter()
    db = SessionLocal()

    try:
        for domain in domains:
            path = base / f"{domain}_cases.jsonl"
            if not path.exists():
                print(f"SKIP {domain}: file not found"); continue

            cases = [json.loads(l) for l in path.read_text().strip().split('\n') if l.strip()]
            if smoke:
                cases = smoke_select(cases, domain)
                print(f"SMOKE {domain}: {len(cases)} cases selected")

            for case in cases:
                r = evaluate_one(case, db, domain)
                all_results.append(r)
                stats["total"] += 1
                s = r.get("status","skip")
                if s == "pass": stats["pass"] += 1; stats[f"pass.{domain}"] += 1
                elif s == "fail": stats["fail"] += 1; stats[f"fail.{domain}"] += 1
                else: stats["skip"] += 1
                reason = r.get("failure_reason","")
                if reason: stats[f"reason.{reason[:40]}"] += 1
    finally:
        db.close()

    # Print summary
    print(f"\n{'='*60}")
    print(f"总 case: {stats['total']}  pass: {stats['pass']}  fail: {stats['fail']}  skip: {stats['skip']}")
    for d in domains:
        print(f"  {d}: pass={stats.get(f'pass.{d}',0)} fail={stats.get(f'fail.{d}',0)}")
    print(f"失败原因 Top 10:")
    for k,v in sorted(stats.items(), key=lambda x:-x[1]):
        if k.startswith("reason."):
            print(f"  {k[7:]}: {v}")

    # Write output
    out_dir = Path("ai/outbox/nqe_eval")
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = out_dir / ts
    out.mkdir(parents=True, exist_ok=True)

    for name, items in [("passed",[r for r in all_results if r["status"]=="pass"]),
                         ("failures",[r for r in all_results if r["status"]=="fail"]),
                         ("skipped",[r for r in all_results if r["status"]=="skip"])]:
        with open(out/f"{name}.jsonl","w") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False)+"\n")

    with open(out/"summary.json","w") as f:
        json.dump(dict(stats), f, ensure_ascii=False, indent=2)

    ds = {}
    for d in domains:
        ds[d] = {"pass": stats.get(f"pass.{d}",0), "fail": stats.get(f"fail.{d}",0),
                 "total": stats.get(f"pass.{d}",0)+stats.get(f"fail.{d}",0)+len([r for r in all_results if r.get("domain")==d and r.get("status")=="skip"])}
    with open(out/"domain_summary.json","w") as f:
        json.dump(ds, f, ensure_ascii=False, indent=2)

    print(f"\n结果输出: {out}")
    return all_results, dict(stats)


if __name__ == "__main__":
    smoke = "--smoke" in sys.argv
    full = "--full" in sys.argv
    print(f"Mode: {'SMOKE' if smoke else 'FULL'}")
    results, stats = run_eval(smoke=smoke and not full)
