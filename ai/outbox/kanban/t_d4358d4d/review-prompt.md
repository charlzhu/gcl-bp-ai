You are an independent read-only code reviewer.

Return ONLY JSON matching the provided output schema. Do not write or modify files. Do not run tests unless absolutely necessary; use the artifacts below as evidence.

Repository: /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai
Task: t_d4358d4d, NL2SQL M3 SQLPlan candidate schema + deterministic validator MVP.
Branch: feature/nl2sql-m3-sqlplan-guardrails.

Scope to review:
- /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/ai/outbox/kanban/t_d4358d4d/diff.patch
- /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/ai/outbox/kanban/t_d4358d4d/static-scan.json
- /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/ai/outbox/kanban/t_d4358d4d/test.log

Changed files in patch:
- backend/app/domains/logistics/services/nl2sql/sql_plan.py (new)
- tests/unit/logistics/nl2sql/test_sql_plan.py (new)
- backend/app/domains/logistics/services/nl2sql/__init__.py (exports only)

Task boundaries:
- M3 must not generate, render, EXPLAIN, execute SQL, or query a business database.
- M3 must not alter formal logistics QA services, routers, DB migrations, or frontend.
- LLM/upstream may produce only structured SQLPlan candidates.
- Deterministic backend must validate candidate structure/catalog/rules/fields/types/safety and fail closed.
- Logistics domain only; catalog must represent intelligent-assistant MySQL middle DB only.
- Validator must block raw_sql/sql/where/having/free_sql and SQL-like strings in arbitrary candidate fields.
- SQLPlan references must be backed by catalog_id/catalog_version from M2 recall and canonical catalog lookup.
- Explicit multi-year buckets must be preserved; unsupported tonnage must not be rewritten to MW.

Focus your review on:
1. fail-closed behavior and any bypasses;
2. SQL injection/raw SQL string exposure or future renderer hazards;
3. catalog ID/version回查 and canonical catalog pollution defenses;
4. M3 phase boundary (no SQL generation/execution/DB access/formal QA/frontend change);
5. test coverage for the required cases, including non-integral biz_year guard.

Fail-closed response rule:
- If security_concerns is non-empty, passed must be false.
- If logic_errors is non-empty, passed must be false.
- Only passed=true if both lists are empty.
