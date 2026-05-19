# t_c4b6cc09 final acceptance

## 当前仓库原有 Query Planning V2 能力判断
- 已存在统一 Query Planning V2 schema、service、strategy_router、logistics_adapter 基础能力。
- 原 LogisticsQueryPlanningAdapter 主要把旧 LogisticsDataQaPlanner 结果包装成 query_plan_v2 shadow 诊断快照，不是真正 LLM 主导 QueryPlan。
- 本轮在物流域新增 Query Planner V2 MVP，默认仍为 shadow，不替换正式物流 QA 主链路。

## 本轮新增/修改文件
- 修改：backend/app/core/config.py
- 修改：backend/app/domains/query_planning/schemas/query_plan_v2.py
- 修改：backend/app/domains/query_planning/services/logistics_adapter.py
- 修改：tests/unit/query_planning/test_query_plan_v2_schema.py
- 新增：backend/app/domains/logistics/services/query_planner_v2/__init__.py
- 新增：backend/app/domains/logistics/services/query_planner_v2/capability_registry.py
- 新增：backend/app/domains/logistics/services/query_planner_v2/fallback.py
- 新增：backend/app/domains/logistics/services/query_planner_v2/legacy_adapter.py
- 新增：backend/app/domains/logistics/services/query_planner_v2/llm_parser.py
- 新增：backend/app/domains/logistics/services/query_planner_v2/normalizer.py
- 新增：backend/app/domains/logistics/services/query_planner_v2/planner.py
- 新增：backend/app/domains/logistics/services/query_planner_v2/prompt_builder.py
- 新增：backend/app/domains/logistics/services/query_planner_v2/validator.py
- 新增：tests/unit/logistics/query_planner_v2/test_logistics_query_planner_v2.py
- 验收材料：ai/outbox/t_c4b6cc09/diff.patch
- 验收材料：ai/outbox/t_c4b6cc09/test.log
- 验收材料：ai/outbox/t_c4b6cc09/review_bundle.md
- 验收材料：ai/outbox/t_c4b6cc09/review-result.json
- 验收材料：ai/outbox/t_c4b6cc09/final-acceptance.md

## 新增模块职责
- planner.py：编排 LLM candidate -> normalize -> validate -> shadow plan；失败走 fallback。
- prompt_builder.py：构造受控 QueryPlan prompt，禁止 SQL/查库/最终计算。
- llm_parser.py：调用 OpenAI 兼容 LLM 并解析严格 JSON；危险字段、未知顶层字段、非标准 JSON 均 fail closed。
- normalizer.py：归一年份、始发地、目的城市、省份、车型、指标、聚合、趋势/对比模式。
- validator.py：按 capability registry 做 query_key/filter/metric/dimension/group_by/aggregation/compare_mode/time_scope/confidence/B-C 边界/多段路线校验。
- capability_registry.py：维护首批白名单 query_key 能力表。
- legacy_adapter.py：把已校验 QueryPlan 转为 LogisticsDataQaPlan / QueryPlanningV2Plan shadow 快照。
- fallback.py：LLM 关闭、不可用、低置信或校验失败时回退旧 planner。

## QueryPlan schema 变更
- QueryPlanningV2Slots 新增 time_range、aggregations、compare_mode。
- QueryPlanningV2Plan 新增 confidence。
- 既有默认值保持兼容，旧规则 planner 包装路径仍可正常构造。

## capability registry 覆盖 query_key
- hist_route_pricing_analysis
- hist_total_fee_city_rank
- hist_avg_fee_by_month
- hist_carrier_kpi_by_year

## Validator 规则
- query_key 必须在白名单。
- filter、metric、dimension、group_by、aggregation、compare_mode 必须在 capability 声明范围。
- required_filters / required_any_filters 必须满足。
- 原问题显式年份必须与候选年份一致，历史 2023-2025 与 2026 系统数据不能混用。
- time_range 只允许 years/months/source_scope/time_scope，source_scope 与 time_scope 任一出现均必须匹配 capability.time_scope。
- origin_place、city、vehicle_type 必须归一到受控值；未知实体 fail closed。
- 多段路线必须澄清。
- 低置信、非法 confidence、B/C 边界问题 fail closed。
- Parser 对 sql/where/where_clause/database/table_name/answer/computed_value/python_code/tool_call 递归 fail closed。

## shadow 接入点
- LogisticsQueryPlanningAdapter 在配置开启且 mode 为 shadow/assist 时调用 LogisticsQueryPlannerV2.build_shadow_plan。
- 默认配置 enabled=false、mode=shadow，因此不影响正式物流 QA。
- 未修改 POST /api/v1/logistics/data-qa/query 正式执行链路。

## fallback 机制
- LLM 未启用/未配置/调用异常/解析异常/Validator 拒绝/配置非法，均转为旧 LogisticsDataQaPlanner 的 shadow fallback 快照。
- fallback 只构造诊断 plan，不查库、不生成最终答案。

## 新增测试覆盖
- capability registry 首批 query_key 合同。
- prompt 安全边界与 query_key 子集。
- parser 严格 JSON、where/sql/answer/未知字段/NaN fail closed。
- normalizer + validator 路线语义变体：合肥发/至/到/从合肥运到/合肥往马鞍山发、17米五、均费等。
- validator 负向：非法 query_key/filter、低置信、2026/历史混用、source_scope/time_scope 绕过、未知始发地、多段路线、B/C 边界、非法维度/聚合/compare_mode。
- planner shadow 不替换 legacy fallback。
- fallback 旧 planner 回退。
- QueryPlanningV2Slots schema 新字段稳定序列化。

## 实际执行测试
- `backend/.venv/bin/python -m pytest tests/unit/logistics/query_planner_v2/test_logistics_query_planner_v2.py::test_llm_parser_accepts_strict_json_and_fail_closes_forbidden_payload tests/unit/logistics/query_planner_v2/test_logistics_query_planner_v2.py::test_validator_rejects_invalid_query_key_filter_low_confidence_2026_and_bc_boundary -q --tb=short`：2 passed
- `backend/.venv/bin/python -m pytest tests/unit/logistics/query_planner_v2/ tests/unit/query_planning/ tests/business_acceptance/test_logistics_*.py -q --tb=short`：131 passed
- `backend/.venv/bin/python -m compileall -q backend/app/domains/logistics/services/query_planner_v2 backend/app/domains/query_planning backend/app/core/config.py`：passed

## 静态检查与 review
- task-scoped diff 新增行静态扫描：未发现 hardcoded secrets、shell=True、os.system、eval/exec、pickle.loads、SQL string formatting。
- 独立 review 第一次发现 where/NaN/source_scope 问题：已修复。
- 独立 review 第二次发现 source_scope/time_scope 双字段绕过：已修复。
- 独立 review 第三次通过：review-result.json 中 passed=true。

## 未执行测试及原因
- 未运行全仓库所有测试：当前任务要求小步推进、避免重复加载/执行过大上下文；本轮已覆盖新增单测、现有 query_planning 单测、物流业务验收 test_logistics_*.py 和 compileall。
- 未做浏览器验证：本轮无前端页面改动，且默认 shadow 不改变用户可见正式 QA 答案。

## 影响评估
- 现有物流 QA 正式主链路：默认不受影响；新增逻辑只在 Query Planning V2 诊断/显式配置开启时进入。
- BOM QA：未修改。
- 功率预测：未修改。
- 前端页面：未修改。

## 风险与下一步
- 风险：当前 LLM QueryPlan MVP 只覆盖首批能力，assist 仍应保持小范围灰度。
- 建议：进入下一阶段前，可仅对 hist_route_pricing_analysis 做小范围 assist 灰度，并继续以 validator fail-closed 和旧 planner fallback 兜底。
