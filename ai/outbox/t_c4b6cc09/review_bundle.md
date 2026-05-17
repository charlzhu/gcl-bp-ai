# t_c4b6cc09 review bundle

任务：物流 QA Query Planning V2 MVP：LLM 语义解析 + 后端确定性校验。

审查范围（请忽略工作区其它历史/并行任务脏文件）：

Tracked modified:
- backend/app/core/config.py
- backend/app/domains/query_planning/schemas/query_plan_v2.py
- backend/app/domains/query_planning/services/logistics_adapter.py
- tests/unit/query_planning/test_query_plan_v2_schema.py

Untracked new:
- backend/app/domains/logistics/services/query_planner_v2/__init__.py
- backend/app/domains/logistics/services/query_planner_v2/capability_registry.py
- backend/app/domains/logistics/services/query_planner_v2/fallback.py
- backend/app/domains/logistics/services/query_planner_v2/legacy_adapter.py
- backend/app/domains/logistics/services/query_planner_v2/llm_parser.py
- backend/app/domains/logistics/services/query_planner_v2/normalizer.py
- backend/app/domains/logistics/services/query_planner_v2/planner.py
- backend/app/domains/logistics/services/query_planner_v2/prompt_builder.py
- backend/app/domains/logistics/services/query_planner_v2/validator.py
- tests/unit/logistics/query_planner_v2/test_logistics_query_planner_v2.py

Artifacts:
- 完整 task-scoped diff：ai/outbox/t_c4b6cc09/diff.patch
- 测试日志：ai/outbox/t_c4b6cc09/test.log

静态安全扫描：对 task-scoped diff 新增行扫描 hardcoded secrets、shell=True、os.system、eval/exec、pickle.loads、SQL string formatting，未发现命中。

已执行测试：
- RED 1：严格 JSON markdown 负向断言首次失败，parser 返回 provider_mode=live；已修复为只接受严格 JSON object。
- RED 2：reviewer-1 指出的 where/NaN/source_scope 负向断言首次失败，NaN 返回 live 且 source_scope mismatch 被 accepted；已补强 Parser/Validator。
- RED 3：reviewer-2 指出的 source_scope/time_scope 双字段绕过负向断言首次失败，source_scope 匹配但 time_scope=system_2026 被 accepted；已改为分别独立校验两个字段。
- GREEN focused：`backend/.venv/bin/python -m pytest tests/unit/logistics/query_planner_v2/test_logistics_query_planner_v2.py::test_llm_parser_accepts_strict_json_and_fail_closes_forbidden_payload tests/unit/logistics/query_planner_v2/test_logistics_query_planner_v2.py::test_validator_rejects_invalid_query_key_filter_low_confidence_2026_and_bc_boundary -q --tb=short`，2 passed。
- focused/regression：`backend/.venv/bin/python -m pytest tests/unit/logistics/query_planner_v2/ tests/unit/query_planning/ tests/business_acceptance/test_logistics_*.py -q --tb=short`，131 passed。
- compile：`backend/.venv/bin/python -m compileall -q backend/app/domains/logistics/services/query_planner_v2 backend/app/domains/query_planning backend/app/core/config.py`，passed。

已处理的独立 review 阻塞项：
1. `where` 已加入 prompt/parser 禁止字段，递归扫描顶层和嵌套字段。
2. Parser 已拒绝 markdown/额外前后缀，并通过 `parse_constant` 拒绝 NaN/Infinity。
3. Parser 已拒绝未知顶层字段，避免自由 schema 绕过。
4. Validator 已校验 time_range.source_scope/time_scope 必须分别匹配 capability.time_scope，并拒绝未知 time_range key。

重点复审问题：
1. LLM 是否只生成 QueryPlan 候选，不生成 SQL/查库/计算最终业务值。
2. Parser 是否 fail closed：非严格 JSON、未知顶层字段、危险字段（sql/where/where_clause/database/table_name/answer/computed_value/python_code/tool_call）必须失败。
3. Validator 是否基于 capability registry 白名单校验 query_key/filter/metric/dimension/group_by/aggregation/compare_mode/time_scope/confidence/B-C 边界/多段路线。
4. 默认 shadow，不替换正式物流 QA 主链路；旧 planner 仍 fallback。
5. 是否存在硬编码具体样例答案、直接 SQL 执行、BOM/功率/前端误改。