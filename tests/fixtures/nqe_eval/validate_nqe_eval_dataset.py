"""NQE 评测集 JSONL 校验脚本。

校验：格式、字段完整性、题量、answer_sql、安全 case 等。
"""

import json, sys
from collections import Counter
from pathlib import Path

BASE = Path("tests/fixtures/nqe_eval")
if not BASE.exists():
    print("评测集目录不存在:", BASE)
    sys.exit(1)

VALID_DOMAIN = {"logistics","business_analysis","plan_bom","power_prediction"}
VALID_SOURCE = {"real_user","paraphrase","asset_generated","safety","edge"}
VALID_RESULT_SRC = {"deterministic_sql","old_service","PowerPredictionEngine","manual_verified","source_excel","existing_report"}

errors = []; case_ids = set()
stats = {"total":0,"by_domain":Counter(),"by_source":Counter(),"by_result":Counter(),
         "with_answer":0,"explain_ok":0,"safety_count":0,"safety_correct":0,
         "needs_review":0,"db_ctx":0,"milvus_ret":0,"active":0}

for path in sorted(BASE.glob("*.jsonl")):
    domain = path.stem.replace("_cases","")
    with open(path) as f:
        for lno, line in enumerate(f, 1):
            line = line.strip()
            if not line: continue
            stats["total"] += 1
            try:
                case = json.loads(line)
            except:
                errors.append(f"{path.name}:{lno} invalid JSON")
                continue

            # schema
            for k in ["case_id","domain","source_type","question","expected_intent","difficulty","is_active"]:
                if k not in case: errors.append(f"{path.name}:{lno} missing {k}")

            cid = case.get("case_id","")
            if cid in case_ids: errors.append(f"{path.name}:{lno} duplicate case_id: {cid}")
            case_ids.add(cid)

            d = case.get("domain","")
            if d not in VALID_DOMAIN: errors.append(f"{path.name}:{lno} invalid domain: {d}")

            st = case.get("source_type","")
            if st not in VALID_SOURCE: errors.append(f"{path.name}:{lno} invalid source_type: {st}")

            rs = case.get("expected_result_source","")
            if rs not in VALID_RESULT_SRC: errors.append(f"{path.name}:{lno} invalid result_source: {rs}")

            # deterministic_sql must have answer_sql
            if rs == "deterministic_sql" and not case.get("answer_sql"):
                errors.append(f"{path.name}:{lno} {cid}: deterministic_sql but no answer_sql")

            # Safety case rules
            if st == "safety":
                stats["safety_count"] += 1
                if case.get("expected_status") == "safety_blocked":
                    stats["safety_correct"] += 1
                else:
                    errors.append(f"{path.name}:{lno} {cid}: safety case expected_status != safety_blocked")

            # answer_sql sanity
            sql = case.get("answer_sql","").strip().upper()
            if sql:
                stats["with_answer"] += 1
                if "SELECT 1" in sql: errors.append(f"{path.name}:{lno} {cid}: SELECT 1 not allowed")
                if any(kw in sql for kw in ["DROP ","DELETE ","UPDATE ","INFORMATION_SCHEMA"]):
                    errors.append(f"{path.name}:{lno} {cid}: dangerous SQL in answer")

                if case.get("explain_verified"):
                    stats["explain_ok"] += 1

            # context / retrieval
            if case.get("expected_context_source") == "db_semantic_catalog":
                stats["db_ctx"] += 1
            if case.get("expected_retrieval_source") == "milvus":
                stats["milvus_ret"] += 1

            if case.get("manual_review_required", False):
                stats["needs_review"] += 1
            if case.get("is_active"):
                stats["active"] += 1

            stats["by_domain"][d] += 1
            stats["by_source"][st] += 1
            stats["by_result"][rs] += 1

# Domain minimums
for d in VALID_DOMAIN:
    if stats["by_domain"].get(d,0) < 30:
        errors.append(f"Domain {d}: {stats['by_domain'].get(d,0)} < 30 minimum")

print(f"Total: {stats['total']} cases")
print(f"Active: {stats['active']}")
print(f"Errors: {len(errors)}")
if errors:
    for e in errors[:15]: print(f"  {e}")
print(f"\nFiles: {len(list(BASE.glob('*.jsonl')))}")
print(f"By domain: {dict(stats['by_domain'])}")
print(f"By source: {dict(stats['by_source'])}")
print(f"By result_src: {dict(stats['by_result'])}")
print(f"With answer_sql: {stats['with_answer']}")
print(f"EXPLAIN OK: {stats['explain_ok']}")
print(f"Safety correct: {stats['safety_correct']}/{stats['safety_count']}")
print(f"Needs manual review: {stats['needs_review']}")
print(f"DB context: {stats['db_ctx']}/{stats['total']}")
print(f"Milvus retrieval: {stats['milvus_ret']}/{stats['total']}")

rc = 1 if errors else 0
print(f"\n{'✅ PASSED' if rc==0 else '❌ FAILED'}")
sys.exit(rc)
