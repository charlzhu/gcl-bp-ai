"""NQE 评测集 JSONL 严格校验脚本。

每条 rule 发现问题必须 errors.append，不允许 pass。
"""

import json, sys, re
from collections import Counter
from pathlib import Path

BASE = Path("tests/fixtures/nqe_eval")
if not BASE.exists():
    print("ERROR: 评测集目录不存在"); sys.exit(2)

VALID_DOMAIN = {"logistics","business_analysis","plan_bom","power_prediction"}
VALID_SOURCE = {"real_user","paraphrase","asset_generated","safety","edge"}
VALID_RESULT = {"deterministic_sql","old_service","PowerPredictionEngine","manual_verified","safety_policy","source_excel","existing_report"}

DANGER_KW = ["DROP ","DELETE ","INSERT ","UPDATE ","ALTER ","TRUNCATE ",
             "information_schema","mysql.","performance_schema","CREATE "]

errors = []; case_ids = {}
stats = Counter()

def add_error(cid, msg):
    errors.append(f"{cid}: {msg}")

def from_tables(sql):
    return set(re.findall(r'(?:FROM|JOIN)\s+`?(\w+)`?', sql, re.IGNORECASE))

for path in sorted(BASE.glob("*_cases.jsonl")):
    with open(path) as f:
        for lno, line in enumerate(f, 1):
            line = line.strip()
            if not line: continue
            stats["total"] += 1
            try:
                c = json.loads(line)
            except:
                add_error(f"{path.name}:{lno}", "invalid JSON"); continue

            cid = c.get("case_id",""); dom = c.get("domain",""); stype = c.get("source_type","")
            rs = c.get("expected_result_source",""); sql = (c.get("answer_sql") or "").strip()
            question = c.get("question",""); expect_tbl = c.get("expected_tables",[])
            metrics = c.get("expected_metrics",[]); dims = c.get("expected_dimensions",[])
            filters = c.get("expected_filters",{})

            # ====== RULE 1: Schema basics ======
            for k in ["case_id","domain","source_type","question","expected_intent","expected_result_source",
                       "expected_status","difficulty","is_active","expected_tables","expected_metrics",
                       "expected_dimensions","expected_filters","expected_context_source",
                       "expected_retrieval_source","verification_status","manual_review_required"]:
                if k not in c: add_error(cid, f"missing field: {k}")

            if dom not in VALID_DOMAIN: add_error(cid, f"invalid domain: {dom}")
            if stype not in VALID_SOURCE: add_error(cid, f"invalid source_type: {stype}")
            if rs not in VALID_RESULT: add_error(cid, f"invalid result_source: {rs}")
            if cid in case_ids: add_error(cid, "duplicate case_id")
            case_ids[cid] = 1

            stats[f"domain.{dom}"] += 1; stats[f"source.{stype}"] += 1

            # ====== RULE 2: Context/retrieval ======
            if c.get("expected_context_source") != "db_semantic_catalog":
                add_error(cid, "expected_context_source must be db_semantic_catalog")
            else: stats["db_ctx"] += 1

            if c.get("expected_retrieval_source") != "milvus":
                add_error(cid, "expected_retrieval_source must be milvus")
            else: stats["milvus"] += 1

            # ====== RULE 3: Empty question ======
            if not question:
                stats["empty_question"] += 1
                if stype != "edge" or c.get("expected_intent") != "empty_question":
                    add_error(cid, "empty question only for edge+empty_question intent")
            elif stype == "edge" and c.get("expected_intent") == "empty_question":
                add_error(cid, "empty_question intent must have empty question text")

            # ====== RULE 4: Real user source ======
            if stype == "real_user":
                stats["real_user"] += 1
                src = c.get("real_user_source",""); coll = c.get("collected_from","")
                if not src: add_error(cid, "real_user missing real_user_source")
                if not coll: add_error(cid, "real_user missing collected_from")
                if "team" in src.lower() or "团队" in coll:
                    add_error(cid, "real_user source must not be 'team' — change to paraphrase")
                else: stats["real_with_source"] += 1

            # ====== RULE 5: Safety rules ======
            if stype == "safety":
                stats["safety"] += 1
                if c.get("expected_status") != "safety_blocked":
                    add_error(cid, "safety case expected_status must be safety_blocked")
                if sql: add_error(cid, "safety case must not have answer_sql")
                if c.get("must_pass_safety") != False: add_error(cid, "safety must_pass_safety must be false")
                if c.get("must_pass_explain") != False: add_error(cid, "safety must_pass_explain must be false")
                if c.get("allow_fallback") != False: add_error(cid, "safety allow_fallback must be false")
                if not stats.get("safety_err"): stats["safety_err"] = 0
            # ====== RULE 6: deterministic_sql needs answer_sql ======
            if rs == "deterministic_sql" and not sql:
                add_error(cid, "deterministic_sql must have answer_sql")

            # ====== RULE 7: SQL safety checks ======
            if sql and stype != "safety":
                stats["with_sql"] += 1
                upper = sql.upper()
                dang = [kw for kw in DANGER_KW if kw.upper() in upper]
                if dang: add_error(cid, f"dangerous keywords in answer_sql: {dang}")
                if sql.strip() == "SELECT 1": add_error(cid, "SELECT 1 not allowed")
                if c.get("explain_verified"): stats["explain_ok"] += 1
                if stype != "safety" and not c.get("explain_verified"):
                    add_error(cid, "answer_sql not EXPLAIN verified")

                # ====== RULE 8: expected_tables must cover SQL FROM/JOIN tables ======
                sql_tables = from_tables(sql)
                if not expect_tbl: add_error(cid, "expected_tables must not be empty when answer_sql present")
                else:
                    missing_tbl = sql_tables - set(expect_tbl)
                    if missing_tbl: add_error(cid, f"expected_tables missing FROM/JOIN tables: {missing_tbl}")

                # ====== RULE 9: expected_metrics/dimensions/filters ======
                if not metrics: add_error(cid, "expected_metrics must not be empty")
                if not dims: add_error(cid, "expected_dimensions must not be empty")
                if not filters: add_error(cid, "expected_filters must not be empty")

# ====== RULE 10-12: Domain/total minimums ======
for d in VALID_DOMAIN:
    cnt = stats.get(f"domain.{d}", 0)
    if cnt < 30:
        add_error(f"domain:{d}", f"count {cnt} < 30 minimum")
if stats["total"] < 120:
    add_error("total", f"count {stats['total']} < 120 minimum")

# ====== REPORT ======
print(f"Total: {stats['total']} cases")
print(f"Source: { {k.split('.')[-1]:v for k,v in stats.items() if k.startswith('source.')} }")
print(f"Domain: { {k.split('.')[-1]:v for k,v in stats.items() if k.startswith('domain.')} }")
print(f"With SQL: {stats.get('with_sql',0)}")
print(f"EXPLAIN OK: {stats.get('explain_ok',0)}")
print(f"DB context: {stats.get('db_ctx',0)}/{stats['total']}")
print(f"Milvus: {stats.get('milvus',0)}/{stats['total']}")
print(f"Real user with source: {stats.get('real_with_source',0)}/{stats.get('real_user',0)}")
print(f"Empty questions: {stats.get('empty_question',0)}")
print(f"\nErrors: {len(errors)}")
for e in errors: print(f"  {e}")

rc = 1 if errors else 0
print(f"\n{'✅ PASSED' if rc == 0 else '❌ FAILED — must fix before QA-DATASET-1'}")
sys.exit(rc)
