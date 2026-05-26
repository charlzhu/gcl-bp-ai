"""NQE 四域评测执行器（加固版 v2）。

不修改全局环境变量。
强制校验主链路证据、context/retrieval source、fallback。
支持 CLI 参数和 per-case timeout。

用法:
    PYTHONPATH=. python tests/fixtures/nqe_eval/run_nqe_eval_dataset.py --smoke --timeout-seconds 180
    PYTHONPATH=. python tests/fixtures/nqe_eval/run_nqe_eval_dataset.py --domain logistics --max-cases 5
    PYTHONPATH=. python tests/fixtures/nqe_eval/run_nqe_eval_dataset.py --case-id NQE-logi-... --timeout-seconds 120
"""

import json, sys, time, os, signal, argparse, threading
from pathlib import Path
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

# 不修改全局 os.environ — 由外部环境或 settings 控制

from backend.app.db.session import SessionLocal
from sqlalchemy import text


# ============================================================
# Per-case timeout
# ============================================================

class TimeoutError(Exception): pass

def _timeout_handler(signum, frame): raise TimeoutError("case timed out")

def run_with_timeout(fn, timeout_seconds: int):
    """在超时保护下执行 fn。"""
    if timeout_seconds <= 0:
        try: return fn()
        except Exception as e: raise
    old = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout_seconds)
    try:
        return fn()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


# ============================================================
# Result comparison
# ============================================================

def compare_results(expected_rows, expected_cols, nqe_rows, nqe_cols,
                    summary: str, dims=None, metrics=None,
                    tolerance: float = 0.01) -> dict:
    """增强版结果对比。"""
    if expected_rows is None or nqe_rows is None:
        return {"match": False, "reason": "result_is_none"}

    exp_count = len(expected_rows) if isinstance(expected_rows, (list, tuple)) else 0
    nqe_count = len(nqe_rows) if isinstance(nqe_rows, (list, tuple)) else 0

    if summary == "empty_result":
        return {"match": nqe_count == 0,
                "reason": "ok" if nqe_count == 0 else f"expected_empty got {nqe_count} rows",
                "expected_rows": exp_count, "nqe_rows": nqe_count}

    if summary == "scalar":
        if exp_count == 0 and nqe_count == 0:
            return {"match": True, "reason": "ok", "expected_rows": 0, "nqe_rows": 0}
        if exp_count == 0 or nqe_count == 0:
            return {"match": False, "reason": f"row_count_mismatch ({exp_count} vs {nqe_count})",
                    "expected_rows": exp_count, "nqe_rows": nqe_count}
        try:
            ev = list(expected_rows[0].values())[0]
            nv = list(nqe_rows[0].values())[0] if nqe_rows else None
            if isinstance(ev, (int, float)) and isinstance(nv, (int, float)):
                if abs(ev - nv) <= tolerance * max(abs(ev), 1):
                    return {"match": True, "reason": "ok", "expected_rows": exp_count, "nqe_rows": nqe_count}
                return {"match": False, "reason": f"value_diff ({ev} vs {nv})",
                        "expected_rows": exp_count, "nqe_rows": nqe_count}
            return {"match": str(ev) == str(nv), "reason": "ok" if str(ev)==str(nv) else "value_diff",
                    "expected_rows": exp_count, "nqe_rows": nqe_count}
        except:
            return {"match": False, "reason": "compare_error", "expected_rows": exp_count, "nqe_rows": nqe_count}

    # grouped_rows / top_n: 用 expected_dimensions 作为 key 对齐行
    if exp_count != nqe_count:
        return {"match": False, "reason": f"row_count_mismatch ({exp_count} vs {nqe_count})",
                "expected_rows": exp_count, "nqe_rows": nqe_count}
    if exp_count == 0:
        return {"match": True, "reason": "ok", "expected_rows": 0, "nqe_rows": 0}

    key_cols = (dims or []) + (metrics or [])
    if not key_cols:
        key_cols = list(expected_rows[0].keys())

    # 维度对齐：用 dims columns 做 key
    dim_cols = dims or list(expected_rows[0].keys())[:2]
    exp_by_key = {}
    for row in expected_rows:
        k = tuple(str(row.get(c,"")) for c in dim_cols)
        exp_by_key[k] = row
    nqe_by_key = {}
    for row in nqe_rows:
        k = tuple(str(row.get(c,"")) for c in dim_cols)
        nqe_by_key[k] = row

    if set(exp_by_key.keys()) != set(nqe_by_key.keys()):
        exp_only = set(exp_by_key.keys()) - set(nqe_by_key.keys())
        nqe_only = set(nqe_by_key.keys()) - set(exp_by_key.keys())
        return {"match": False, "reason": f"dimension_key_mismatch: exp_only={list(exp_only)[:3]} nqe_only={list(nqe_only)[:3]}",
                "expected_rows": exp_count, "nqe_rows": nqe_count}

    # 指标值比较
    metric_cols = metrics or [c for c in expected_rows[0].keys() if c not in dim_cols]
    match = True; mismatches = []
    for key in exp_by_key:
        for col in metric_cols:
            ev = exp_by_key[key].get(col)
            nv = nqe_by_key[key].get(col)
            if isinstance(ev, (int, float)) and isinstance(nv, (int, float)):
                if abs(ev - nv) > tolerance * max(abs(ev), 1):
                    match = False; mismatches.append(f"{key}.{col}: {ev} vs {nv}")
            elif str(ev) != str(nv):
                match = False; mismatches.append(f"{key}.{col}: {ev} vs {nv}")

    return {"match": match, "reason": "ok" if match else f"metric_mismatch: {'; '.join(mismatches[:3])}",
            "expected_rows": exp_count, "nqe_rows": nqe_count}


# ============================================================
# Single case
# ============================================================

def evaluate_one(case: dict, db, domain: str, timeout_sec: int) -> dict:
    """评测单条 case。异常不会中断整轮。"""
    cid = case.get("case_id","?")
    stype = case.get("source_type","")
    sql = (case.get("answer_sql") or "").strip()
    expected_status = case.get("expected_status","")
    summary = case.get("expected_result_summary","")
    expected_ctx = case.get("expected_context_source","")
    expected_ret = case.get("expected_retrieval_source","")
    dims = case.get("expected_dimensions",[])
    metrics = case.get("expected_metrics",[])

    base = {
        "case_id": cid, "domain": domain, "source_type": stype,
        "question": case.get("question","")[:80],
        "expected_status": expected_status, "actual_status": "", "status": "skip",
        "failure_reason": "", "trace_id": "",
        "expected_context_source": expected_ctx, "actual_context_source": "",
        "expected_retrieval_source": expected_ret, "actual_retrieval_source": "",
        "generated_sql": "", "final_sql": "",
        "expected_rows": 0, "actual_rows": 0, "duration_ms": 0,
        "retrieved_assets_count": 0,
        "llm_sql_generated": False, "safety_executed": False,
        "explain_executed": False, "execute_executed": False, "fallback_used": False,
    }

    try:
        from backend.app.domains.business_qa_graph.nqe_sql_agent_graph import build_nqe_sql_agent_graph
    except Exception as e:
        base["status"] = "skip"; base["failure_reason"] = f"import_error:{e}"; return base

    _invoke = lambda: build_nqe_sql_agent_graph().invoke({
        "question": case.get("question",""), "nqe_mode": "on",
        "domain_hint": domain, "trace_id": f"eval-{cid}"})

    # ---- SAFETY ----
    if stype == "safety":
        try:
            f = run_with_timeout(_invoke, timeout_sec)
            ts = f.get("terminal_status",""); base["actual_status"] = ts
            base["status"] = "pass" if ts == "safety_reject" else "fail"
            if ts != "safety_reject":
                base["failure_reason"] = "safety_not_blocked"
                base["generated_sql"] = str(f.get("generated_sql",""))[:100]
        except TimeoutError:
            base["status"] = "fail"; base["failure_reason"] = "timeout"
        except Exception as e:
            base["status"] = "fail"; base["failure_reason"] = f"graph_error:{type(e).__name__}"
        return base

    # ---- EDGE (no sql) ----
    if stype == "edge" and not sql:
        try:
            f = run_with_timeout(_invoke, timeout_sec)
            ts = f.get("terminal_status",""); base["actual_status"] = ts
            if ts == expected_status or (expected_status == "clarify_required" and ts in ("clarify","clarify_required")):
                base["status"] = "pass"
            elif expected_status == "empty_result":
                if ts in ("error","failed","safety_reject"):
                    base["status"] = "fail"
                    base["failure_reason"] = f"expected_empty but status={ts}"
                else:
                    exec_int = f.get("execution_result_internal") or {}
                    rows = exec_int.get("rows", [])
                    base["actual_rows"] = len(rows) if isinstance(rows, (list, tuple)) else 0
                    base["status"] = "pass" if base["actual_rows"] == 0 else "fail"
                    if base["status"] == "fail": base["failure_reason"] = f"expected_empty got {base['actual_rows']} rows"
            else:
                base["status"] = "fail"; base["failure_reason"] = f"expected_{expected_status}_got_{ts}"
        except TimeoutError:
            base["status"] = "fail"; base["failure_reason"] = "timeout"
        except Exception as e:
            base["status"] = "fail"; base["failure_reason"] = f"graph_error:{type(e).__name__}"
        return base

    # ---- PowerPredictionEngine ----
    if case.get("expected_result_source") == "PowerPredictionEngine":
        try:
            f = run_with_timeout(_invoke, timeout_sec)
            ts = f.get("terminal_status",""); base["actual_status"] = ts
            ra = f.get("_nqe_retrieval_assets",{})
            base["actual_context_source"] = f.get("retrieval_context_package",{}).get("context_source","")
            base["actual_retrieval_source"] = ra.get("retrieval_source","") if ra else ""

            if expected_status == "clarify_required":
                base["status"] = "pass" if ts in ("clarify","clarify_required") else "fail"
                if base["status"] == "fail": base["failure_reason"] = f"expected_clarify_got_{ts}"
            elif ts == "fallback":
                fb = str(f.get("fallback_reason",""))
                base["status"] = "fail"; base["failure_reason"] = f"fallback:{fb}"
            elif ts == "completed":
                engine_called = bool(f.get("engine_called") or f.get("power_prediction_result"))
                if engine_called:
                    base["status"] = "pass"
                else:
                    base["status"] = "fail"; base["failure_reason"] = "engine_not_called"
            else:
                base["status"] = "fail"; base["failure_reason"] = f"unexpected_status:{ts}"
        except TimeoutError:
            base["status"] = "fail"; base["failure_reason"] = "timeout"
        except Exception as e:
            base["status"] = "fail"; base["failure_reason"] = f"graph_error:{type(e).__name__}"
        return base

    # ---- DETERMINISTIC_SQL ----
    if not sql:
        # old_service: 无标准 SQL，预期走旧链路/fallback
        if case.get("expected_result_source") == "old_service":
            base["status"] = "skip"
            base["failure_reason"] = "old_service_not_available"
            return base
        base["status"] = "skip"; base["failure_reason"] = "no_answer_sql"; return base

    # Step 1: execute answer_sql
    try:
        exec_result = db.execute(text(sql))
        expected_rows = [dict(row._mapping) for row in exec_result.fetchmany(500)]
        expected_cols = list(expected_rows[0].keys()) if expected_rows else []
    except Exception as e:
        base["status"] = "fail"
        base["failure_reason"] = f"expected_sql_failed:{type(e).__name__}:{str(e)[:80]}"
        return base
    base["expected_rows"] = len(expected_rows)

    # Step 2: NQE graph
    t0 = time.time()
    try:
        f = run_with_timeout(_invoke, timeout_sec)
    except TimeoutError:
        base["duration_ms"] = int((time.time() - t0) * 1000)
        base["status"] = "fail"; base["failure_reason"] = "timeout"
        return base
    except Exception as e:
        base["duration_ms"] = int((time.time() - t0) * 1000)
        base["status"] = "fail"; base["failure_reason"] = f"graph_error:{type(e).__name__}:{str(e)[:60]}"
        return base
    base["duration_ms"] = int((time.time() - t0) * 1000)

    cp = f.get("retrieval_context_package",{})
    ra = f.get("_nqe_retrieval_assets",{})
    base["actual_context_source"] = cp.get("context_source","")
    base["actual_retrieval_source"] = ra.get("retrieval_source","") if ra else ""
    base["generated_sql"] = str(f.get("generated_sql",""))[:200]
    base["final_sql"] = str(f.get("final_sql") or f.get("generated_sql",""))[:200]
    base["trace_id"] = str(f.get("trace_id","") or "")
    base["llm_sql_generated"] = bool(base["generated_sql"])
    base["safety_executed"] = bool(f.get("sql_safety_result"))
    base["explain_executed"] = bool(f.get("explain_result"))
    # execute: execution_status 必须是 executed/completed 等明确态
    exec_status = str(f.get("execution_status","")).lower()
    exec_int = f.get("execution_result_internal") or {}
    has_exec_rows = exec_int.get("rows") is not None
    has_exec_cols = bool(exec_int.get("columns"))
    base["execute_executed"] = (exec_status in ("executed","completed","done")) or has_exec_rows or has_exec_cols
    base["fallback_used"] = bool(f.get("fallback_used"))
    ts = f.get("terminal_status",""); base["actual_status"] = ts

    # ---- 强制校验 ----
    # context_source
    if base["actual_context_source"] != expected_ctx:
        base["status"] = "fail"
        base["failure_reason"] = f"context_source_mismatch: expect={expected_ctx} actual={base['actual_context_source']}"
        return base
    # retrieval_source + retrieved_assets_count
    base["retrieved_assets_count"] = ra.get("retrieved_count", 0) if ra else 0
    if base["actual_retrieval_source"] != expected_ret:
        base["status"] = "fail"
        base["failure_reason"] = f"retrieval_source_mismatch: expect={expected_ret} actual={base['actual_retrieval_source']}"
        return base
    if expected_ret == "milvus" and base["retrieved_assets_count"] == 0:
        base["status"] = "fail"
        base["failure_reason"] = "milvus_retrieved_zero"
        return base
    # fallback
    allow_fb = case.get("allow_fallback", False)
    if base["fallback_used"] and not allow_fb:
        base["status"] = "fail"
        base["failure_reason"] = f"unexpected_fallback"
        return base
    # terminal_status
    if ts != "completed":
        base["status"] = "fail"
        base["failure_reason"] = f"nqe_status:{ts}"
        return base
    # main chain evidence
    if not base["generated_sql"]:
        base["status"] = "fail"; base["failure_reason"] = "llm_sql_not_generated"; return base
    if not base["safety_executed"]:
        base["status"] = "fail"; base["failure_reason"] = "safety_not_executed"; return base
    if not base["explain_executed"]:
        base["status"] = "fail"; base["failure_reason"] = "explain_not_executed"; return base
    if not base["execute_executed"]:
        base["status"] = "fail"; base["failure_reason"] = "execute_not_executed"; return base

    exec_int = f.get("execution_result_internal") or {}
    nqe_rows = exec_int.get("rows", [])
    nqe_cols = f.get("execution_result_internal", {}).get("columns", [])
    base["actual_rows"] = len(nqe_rows) if isinstance(nqe_rows, (list, tuple)) else 0

    # Step 3: compare
    comp = compare_results(expected_rows, expected_cols, nqe_rows, nqe_cols,
                           summary, dims, metrics)
    base["status"] = "pass" if comp.get("match") else "fail"
    if not comp.get("match"):
        base["failure_reason"] = f"result_mismatch:{comp.get('reason','')}"
    return base


# ============================================================
# Smoke selection
# ============================================================

def smoke_select(cases, domain):
    by_type = defaultdict(list)
    for c in cases: by_type[c.get("source_type","")].append(c)
    by_engine = [c for c in cases if c.get("expected_result_source") == "PowerPredictionEngine"]
    sel = []
    for st in ["real_user","asset_generated","paraphrase"]:
        for c in by_type.get(st,[]):
            if c.get("answer_sql") and len(sel) < 2: sel.append(c)
    for t in ["safety","edge"]:
        for c in by_type.get(t,[]):
            if c not in sel and len(sel) < 4: sel.append(c)
    sel.extend(by_engine[:1])
    for st in ["real_user","paraphrase","asset_generated"]:
        for c in by_type.get(st,[]):
            if c not in sel and len(sel) < 5: sel.append(c)
    return sel[:5]


# ============================================================
# CLI
# ============================================================

def parse_args():
    p = argparse.ArgumentParser(description="NQE 四域评测执行器")
    p.add_argument("--smoke", action="store_true", help="烟幕测试 (每域 5 条)")
    p.add_argument("--full", action="store_true", help="全量测试")
    p.add_argument("--domain", type=str, help="限定业务域")
    p.add_argument("--case-id", type=str, help="指定单个 case_id")
    p.add_argument("--max-cases", type=int, default=0, help="每域最大 case 数")
    p.add_argument("--timeout-seconds", type=int, default=120, help="单 case 超时 (秒)")
    p.add_argument("--skip-validate", action="store_true", help="跳过数据集校验")
    return p.parse_args()


# ============================================================
# Main
# ============================================================

def main():
    args = parse_args()
    base = Path(__file__).resolve().parent
    all_domains = ["logistics","business_analysis","plan_bom","power_prediction"]
    if args.domain:
        all_domains = [args.domain]

    # 预校验数据集
    if not args.skip_validate:
        import subprocess
        vp = str(base / "validate_nqe_eval_dataset.py")
        rc = subprocess.run([sys.executable, vp], capture_output=False)
        if rc.returncode != 0:
            print("❌ 数据集校验未通过，终止评测")
            sys.exit(1)
        print("✅ 数据集校验通过")

    all_results = []
    stats = Counter()
    log_lines = [f"# NQE eval runner started at {time.strftime('%Y-%m-%d %H:%M:%S')}",
                 f"# args: {sys.argv[1:]}"]

    db = SessionLocal()
    try:
        for domain in all_domains:
            path = base / f"{domain}_cases.jsonl"
            if not path.exists():
                print(f"SKIP {domain}: no file"); log_lines.append(f"SKIP {domain}: no file")
                continue

            cases = [json.loads(l) for l in path.read_text().strip().split('\n') if l.strip()]

            if args.case_id:
                cases = [c for c in cases if c.get("case_id") == args.case_id]
                if not cases:
                    print(f"CASE-ID {args.case_id} not found in {domain}"); continue

            if args.smoke:
                cases = smoke_select(cases, domain)
                log_lines.append(f"SMOKE {domain}: {len(cases)} selected")
            elif args.max_cases > 0:
                cases = cases[:args.max_cases]

            for case in cases:
                t0 = time.time()
                r = evaluate_one(case, db, domain, args.timeout_seconds)
                elapsed = time.time() - t0
                log_lines.append(f"[{r['status']}] {r['case_id']} {r.get('failure_reason','')[:60]} ({elapsed:.1f}s)")
                all_results.append(r)
                stats["total"] += 1
                s = r.get("status","skip")
                if s == "pass": stats["pass"] += 1; stats[f"pass.{domain}"] += 1
                elif s == "fail": stats["fail"] += 1; stats[f"fail.{domain}"] += 1
                else: stats["skip"] += 1
                reason = r.get("failure_reason","")
                if reason: stats[f"reason.{reason[:50]}"] += 1
    finally:
        db.close()

    log_lines.append(f"# done: total={stats['total']} pass={stats['pass']} fail={stats['fail']} skip={stats['skip']}")

    # Summary
    print(f"\n{'='*60}")
    print(f"总: {stats['total']}  pass: {stats['pass']}  fail: {stats['fail']}  skip: {stats['skip']}")
    for d in all_domains:
        print(f"  {d}: pass={stats.get(f'pass.{d}',0)} fail={stats.get(f'fail.{d}',0)}")
    print(f"\nTop 失败原因:")
    for k,v in sorted(stats.items(), key=lambda x:-x[1]):
        if k.startswith("reason."): print(f"  {k[7:]}: {v}")

    # Write output
    out_dir = Path("ai/outbox/nqe_eval")
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = out_dir / ts
    out.mkdir(parents=True, exist_ok=True)

    for name in ["passed","failures","skipped"]:
        items = [r for r in all_results if r["status"] == name.replace("failures","fail").replace("passed","pass").replace("skipped","skip")]
        with open(out/f"{name}.jsonl","w") as f:
            for item in items: f.write(json.dumps(item, ensure_ascii=False)+"\n")

    with open(out/"summary.json","w") as f: json.dump(dict(stats), f, ensure_ascii=False, indent=2)
    ds = {}
    for d in all_domains:
        ds[d] = {"pass": stats.get(f"pass.{d}",0), "fail": stats.get(f"fail.{d}",0)}
    with open(out/"domain_summary.json","w") as f: json.dump(ds, f, ensure_ascii=False, indent=2)
    with open(out/"run.log","w") as f: f.write("\n".join(log_lines)+"\n")

    print(f"\n结果: {out}")
    print(f"  passed.jsonl / failures.jsonl / skipped.jsonl / run.log")

    # Exit code
    if stats.get("fail", 0) > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
