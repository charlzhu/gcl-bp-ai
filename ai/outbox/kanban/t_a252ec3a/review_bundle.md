# M1 文档审查包

请审查本轮 M1 文档是否满足 requirement.md 的 M1 范围、安全和交付要求。

## 交付文件
- docs/MATERIAL_MANAGEMENT_SAP_MID_DATA_ASSET_AUDIT.md
- docs/MATERIAL_MANAGEMENT_MIDDLE_DB_MODEL_PLAN.md
- docs/SAP_MID_SYNC_DESIGN.md
- docs/MATERIAL_MANAGEMENT_AI_QUERY_PLAN.md
- docs/PLAN_BOM_SAP_DATA_SOURCE_MIGRATION_PLAN.md
- docs/FRONTEND_MATERIAL_MANAGEMENT_ADAPTATION_PLAN.md
- docs/SAP_MID_INTEGRATION_ROADMAP.md
- docs/SAP_MID_ORACLE_SMOKE_TEST_REPORT.md
- docs/CURRENT_STATUS.md
- docs/NEXT_TASK.md
- docs/HANDOFF.md

## 自动验证摘要

- PASS deliverables_exist: 11/11 docs present
- PASS requirement_doc_list_covered: all 11 expected docs match requirement.md list
- PASS exact_env_secret_scan: 0 exact sensitive .env value matches across 11 docs
- PASS high_confidence_secret_pattern_scan: 0 high-confidence token/password/DSN patterns
- PASS m1_boundary_statements_present: required no-dev/no-direct-oracle/no-free-sql boundaries present
- PASS oracle_smoke_blocker_recorded: driver blocker recorded without fabricated Oracle results
- PASS focused_patch_docs_only: focused patch contains docs only; files=11
- PASS placeholder_scan: 0 TBD/TODO/FIXME/待补充 placeholders

## 关键约束

- M1 只允许方案文档和只读审计。
- 禁止前端/后端正式开发。
- 禁止大表导出。
- 禁止用户问答直接查 Oracle。
- 禁止 LLM 自由 SQL。
- 禁止泄露 backend/.env 中真实账号密码。

## 聚焦补丁路径

`ai/outbox/kanban/t_a252ec3a/diff.patch`
