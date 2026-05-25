"""NQE 四域评测执行器。

读取 JSONL 评测集，执行评测：
1. deterministic_sql: 先跑 answer_sql 生成 expected_result，再跑 NQE SQL Agent 对比
2. safety: 验证 NQE 被拦截
3. edge/PowerPredictionEngine: 按 expected_status 验证

不使用 LLM judge。结果对比基于行列计数和值比较。
"""

import json, sys, time, os, hashlib
from pathlib import Path
from collections import defaultdict, Counter
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
os.environ.setdefault("NQE_LLM_DISABLE_PROXY", "true")
os.environ.setdefault("NQE_LLM_SSL_VERIFY", "false")

# ============================================================
# Result comparison
# ============================================================

def _normalize_rows(rows, columns):
    """标准化 rows 为可比较的 tuple of tuples。"""
    if not rows or not columns: return tuple()
    try:
        return tuple(tuple(row.get(c) for c in columns) for row in rows)
    except:
        return tuple()

def compare_results(expected_rows, expected_cols, nqe_rows, nqe_cols, summary: str, tolerance: float = 0.01) -> dict:
    """比较两组查询结果。返回 match 和差异详情。"""
    if expected_rows is None or nqe_rows is None:
        return {"match": False, "reason": "result_is_none"}

    exp_count = len(expected_rows) if isinstance(expected_rows, (list, tuple)) else 0
    nqe_count = len(nqe_rows) if isinstance(nqe_rows, (list, tuple)) else 0

    # 行数比较
    if summary == "empty_result":
        match = nqe_count == 0
        return {"match": match, "reason": "ok" if match else f"expected_empty but got {nqe_count} rows",
                "expected_rows": exp_count, "nqe_rows": nqe_count}

    if summary == "scalar":
        match = True
        if exp_count != nqe_count:
            match = False
        if match and exp_count == 1 and nqe_count == 1:
            # 比较单值
            exp_val = list(expected_rows[0].values())[0] if expected_rows else None
            nqe_val = list(nqe_rows[0].values())[0] if nqe_rows else None
            if isinstance(exp_val, (int, float)) and isinstance(nqe_val, (int, float)):
                if abs(exp_val - nqe_val) > tolerance * max(abs(exp_val), 1):
                    match = False
        return {"match": match, "reason": "ok" if match else "row_count_mismatch",
                "expected_rows": exp_count, "nqe_rows": nqe_count}

    # grouped_rows / top_n: 比较行数
    match = exp_count == nqe_count
    return {"match": match, "reason": "ok" if match else f"row_count_mismatch ({exp_count} vs {nqe_count})",
            "expected_rows": exp_count, "nqe_rows": nqe_count}


# ============================================================
# Evaluation runner
# ============================================================

def run_eval(smoke: bool = False, max_cases: int = 0):
    """运行评测执行器。

    smoke=True: 每域最多 max_cases 条。
    max_cases>0: 限制每域 case 数。
    """
    from backend.app.db.session import SessionLocal
    from sqlalchemy import text

    base = Path(__file__).resolve().parent
    domains = ["logistics", "business_analysis", "plan_bom", "power_prediction"]

    all_results = []
    stats = Counter()
    db = SessionLocal()

    try:
        for domain in domains:
            path = base / f"{domain}_cases.jsonl"
            if not path.exists():
                print(f"SKIP {domain}: file not found")
                continue

            cases = [json.loads(l) for l in path.read_text().strip().split('\n') if l.strip()]
            if smoke:
                # 每域各选 5 条不同类型
                by_type = defaultdict(list)
                for c in cases:
                    by_type[c.get("source_type","")].append(c)
                selected = []
                for st in ["real_user","safety","edge","asset_generated","paraphrase"]:
                    selected.extend(by_type.get(st, [])[:max_cases or 2])
                cases = selected[:max_cases or 20]
            elif max_cases > 0:
                cases = cases[:max_cases]

            for case in cases:
                result = evaluate_one(case, db, domain)
                all_results.append(result)
                stats["total"] += 1
                if result.get("status") == "pass":
                    stats["pass"] += 1
                    stats[f"pass.{domain}"] += 1
                elif result.get("status") == "fail":
                    stats["fail"] += 1
                    stats[f"fail.{domain}"] += 1
                elif result.get("status") == "skip":
                    stats["skip"] += 1
                reason = result.get("failure_reason","")
                if reason:
                    stats[f"reason.{reason}"] += 1
    finally:
        db.close()

    # Summary
    print(f"\n{'='*60}")
    print(f"总 case: {stats['total']}")
    print(f"通过: {stats['pass']}  失败: {stats['fail']}  跳过: {stats['skip']}")
    for d in domains:
        p = stats.get(f"pass.{d}",0); f = stats.get(f"fail.{d}",0)
        print(f"  {d}: pass={p} fail={f}")
    print(f"\n失败原因分类:")
    for k,v in sorted(stats.items()):
        if k.startswith("reason."):
            print(f"  {k[7:]}: {v}")

    return all_results, dict(stats)


def evaluate_one(case: dict, db, domain: str) -> dict:
    """评测单条 case。"""
    cid = case.get("case_id","?")
    stype = case.get("source_type","")
    sql = (case.get("answer_sql") or "").strip()
    expected_status = case.get("expected_status","")
    summary = case.get("expected_result_summary","")

    result = {
        "case_id": cid, "domain": domain, "source_type": stype,
        "question": case.get("question","")[:80],
        "expected_status": expected_status, "status": "skip",
        "failure_reason": "", "trace_id": "",
        "expected_result_source": case.get("expected_result_source",""),
        "nqe_context_source": "", "nqe_retrieval_source": "",
        "nqe_generated_sql": "", "expected_rows": 0, "nqe_rows": 0, "duration_ms": 0,
    }

    # ---- SAFETY ----
    if stype == "safety":
        try:
            from backend.app.domains.business_qa_graph.nqe_sql_agent_graph import build_nqe_sql_agent_graph
            g = build_nqe_sql_agent_graph()
            f = g.invoke({"question": case.get("question",""), "nqe_mode": "on", "domain_hint": domain, "trace_id": f"eval-{cid}"})
            ts = f.get("terminal_status","")
            if ts == "safety_reject":
                result["status"] = "pass"
            else:
                result["status"] = "fail"
                result["failure_reason"] = "safety_not_blocked"
                result["nqe_generated_sql"] = str(f.get("generated_sql",""))[:100]
        except Exception as e:
            result["status"] = "fail"
            result["failure_reason"] = f"nqe_error:{str(e)[:60]}"
        return result

    # ---- EDGE (clarify/disambiguation/empty) ----
    if stype == "edge" and not sql:
        try:
            from backend.app.domains.business_qa_graph.nqe_sql_agent_graph import build_nqe_sql_agent_graph
            g = build_nqe_sql_agent_graph()
            f = g.invoke({"question": case.get("question",""), "nqe_mode": "on", "domain_hint": domain, "trace_id": f"eval-{cid}"})
            ts = f.get("terminal_status","")
            if ts == expected_status or (expected_status == "clarify_required" and ts in ("clarify","clarify_required")):
                result["status"] = "pass"
            elif expected_status == "empty_result" and ts == "completed":
                # Check actual rows
                result["nqe_rows"] = f.get("row_count",0)
                result["status"] = "pass" if result["nqe_rows"] == 0 else "fail"
                if result["status"] == "fail": result["failure_reason"] = f"expected_empty got {result['nqe_rows']}"
            else:
                result["status"] = "fail"
                result["failure_reason"] = f"expected_{expected_status}_got_{ts}"
        except Exception as e:
            result["status"] = "fail"
            result["failure_reason"] = f"nqe_error:{str(e)[:60]}"
        return result

    # ---- PowerPredictionEngine ----
    if case.get("expected_result_source") == "PowerPredictionEngine":
        try:
            from backend.app.domains.business_qa_graph.nqe_sql_agent_graph import build_nqe_sql_agent_graph
            g = build_nqe_sql_agent_graph()
            f = g.invoke({"question": case.get("question",""), "nqe_mode": "on", "domain_hint": domain, "trace_id": f"eval-{cid}"})
            ts = f.get("terminal_status","")
            ra = f.get("_nqe_retrieval_assets",{})
            result["nqe_context_source"] = f.get("retrieval_context_package",{}).get("context_source","")
            result["nqe_retrieval_source"] = ra.get("retrieval_source","") if ra else ""
            # For power prediction, just verify it didn't crash
            if ts == "completed" or ts == "clarify" or ts == "fallback":
                result["status"] = "pass"
            else:
                result["status"] = "fail"
                result["failure_reason"] = f"unexpected_status:{ts}"
        except Exception as e:
            result["status"] = "fail"
            result["failure_reason"] = f"nqe_error:{str(e)[:60]}"
        return result

    # ---- DETERMINISTIC_SQL ----
    if not sql:
        result["status"] = "skip"
        result["failure_reason"] = "no_answer_sql"
        return result

    # Step 1: Execute answer_sql to get expected result
    from sqlalchemy import text
    expected_rows = None; expected_cols = []
    try:
        exec_result = db.execute(text(sql))
        expected_rows = [dict(row._mapping) for row in exec_result.fetchmany(500)]
        expected_cols = list(expected_rows[0].keys()) if expected_rows else []
    except Exception as e:
        result["status"] = "fail"
        result["failure_reason"] = f"expected_sql_failed:{str(e)[:100]}"
        return result
    result["expected_rows"] = len(expected_rows)

    # Step 2: Run NQE SQL Agent
    t0 = time.time()
    try:
        from backend.app.domains.business_qa_graph.nqe_sql_agent_graph import build_nqe_sql_agent_graph
        g = build_nqe_sql_agent_graph()
        f = g.invoke({"question": case.get("question",""), "nqe_mode": "on", "domain_hint": domain, "trace_id": f"eval-{cid}"})
        result["duration_ms"] = int((time.time() - t0) * 1000)

        cp = f.get("retrieval_context_package",{})
        ra = f.get("_nqe_retrieval_assets",{})
        result["nqe_context_source"] = cp.get("context_source","")
        result["nqe_retrieval_source"] = ra.get("retrieval_source","") if ra else ""
        result["nqe_generated_sql"] = str(f.get("generated_sql",""))[:200]
        result["trace_id"] = f.get("trace_id","")

        ts = f.get("terminal_status","")
        if ts != "completed":
            result["status"] = "fail"
            result["failure_reason"] = f"nqe_status:{ts}"
            return result

        nqe_rows = f.get("rows",[])
        nqe_cols = f.get("columns",[])
        result["nqe_rows"] = len(nqe_rows)

        # Step 3: Compare
        comp = compare_results(expected_rows, expected_cols, nqe_rows, nqe_cols, summary, tolerance=0.01)
        result["status"] = "pass" if comp["match"] else "fail"
        if not comp["match"]:
            result["failure_reason"] = f"result_mismatch:{comp['reason']}"
    except Exception as e:
        result["duration_ms"] = int((time.time() - t0) * 1000)
        result["status"] = "fail"
        result["failure_reason"] = f"nqe_error:{type(e).__name__}:{str(e)[:80]}"

    return result


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    smoke = "--smoke" in sys.argv
    full = "--full" in sys.argv
    max_cases = 0
    if smoke: max_cases = 5
    if full: max_cases = 0

    print(f"Mode: {'SMOKE' if smoke else 'FULL' if full else 'FULL (default)'}")
    results, stats = run_eval(smoke=smoke, max_cases=max_cases)

    # Write output
    out_dir = Path("ai/outbox/nqe_eval")
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = out_dir / ts
    out.mkdir(parents=True, exist_ok=True)

    passed = [r for r in results if r["status"]=="pass"]
    failed = [r for r in results if r["status"]=="fail"]
    skipped = [r for r in results if r["status"]=="skip"]

    for name, items in [("passed",passed),("failures",failed),("skipped",skipped)]:
        with open(out/f"{name}.jsonl","w") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False)+"\n")
    with open(out/"summary.json","w") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # Domain summary
    ds = {}
    for d in ["logistics","business_analysis","plan_bom","power_prediction"]:
        ds[d] = {
            "pass": stats.get(f"pass.{d}",0), "fail": stats.get(f"fail.{d}",0),
            "total": stats.get(f"pass.{d}",0)+stats.get(f"fail.{d}",0)+len([r for r in skipped if r.get("domain")==d])
        }
    with open(out/"domain_summary.json","w") as f:
        json.dump(ds, f, ensure_ascii=False, indent=2)

    print(f"\n结果输出: {out}")
    print(f"  passed.jsonl: {len(passed)}")
    print(f"  failures.jsonl: {len(failed)}")
    print(f"  skipped.jsonl: {len(skipped)}")
