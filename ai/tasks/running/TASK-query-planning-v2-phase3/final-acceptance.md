# Query Planning V2 Phase 3 最小实现验收报告

## 1. 本轮目标

进入 Phase 3：在不替换现有物流 Data QA / 计划 BOM QA 主链路的前提下，新增 Query Planning V2 最小实现：

- 输出统一、稳定的 `query_plan_v2` JSON；
- 支持受控 strategy 枚举；
- 复用现有物流规则 planner 和计划 BOM NLU Center；
- 新增内部诊断接口，先 shadow 运行；
- 写入 JSONL 审计日志；
- 保持 LLM 不直接生成 SQL、不直接查数、不直接生成最终业务答案；
- 补充单元测试和回归验证。

## 2. 当前仓库能力判断

### 已完成能力

1. 已新增 `backend/app/domains/query_planning` 领域包；
2. 已新增 `QueryPlanningV2Plan` / `QueryPlanningV2Slots` / `QueryPlanningV2SubQuery` / `QueryPlanningV2ExecutionPolicy` 等 schema；
3. 已新增 `QueryPlanningV2StrategyRouter`，统一处理：
   - `DIRECT_RETRIEVAL`
   - `HYDE_RETRIEVAL`
   - `QUERY_DECOMPOSITION`
   - `QUERY_REWRITE_SIMPLIFY`
   - `CLARIFY`
   - `NO_ANSWER`
   - `UNSUPPORTED`
4. 已新增物流 adapter：仅调用 `LogisticsDataQaPlanner.build_plan()`，不执行 Data QA 查询；
5. 已新增计划 BOM adapter：仅调用 `PlanBomNluCenterService.understand(..., use_llm=False)`，不调用 `PlanBomQaService.ask()`；
6. 已新增 `QueryPlanV2AuditWriter`：写入 `data/logs/query_planning_v2_audit.jsonl`；
7. 已新增统一服务 `QueryPlanningV2Service`；
8. 已新增内部诊断接口：`POST /query-planning/v2/diagnose`；
9. 已补充 query planning 单元测试；
10. 已生成 `diff.patch` 和 `test.log` 验收材料。

### 明确未做 / 阶段边界

1. 未替换 `/logistics/data-qa/query` 主链路；
2. 未替换 `/plan-bom/qa/ask` 主链路；
3. 未新增数据库迁移；
4. 未让 LLM 生成 SQL；
5. 未让 LLM 执行查询或查数；
6. 未让 LLM 生成最终业务答案；
7. HYDE / rewrite 当前只在 schema 与 strategy 层具备承载能力，未接入真实 LLM 生成；
8. QUERY_DECOMPOSITION 当前仍复用现有 `composite_decomposed` 受控框架，未做自由拆分。

## 3. 修改文件清单

### 新增 Query Planning V2 代码

- `backend/app/domains/query_planning/__init__.py`
- `backend/app/domains/query_planning/api/__init__.py`
- `backend/app/domains/query_planning/api/endpoints/__init__.py`
- `backend/app/domains/query_planning/api/endpoints/query_plan_v2.py`
- `backend/app/domains/query_planning/schemas/__init__.py`
- `backend/app/domains/query_planning/schemas/query_plan_v2.py`
- `backend/app/domains/query_planning/services/__init__.py`
- `backend/app/domains/query_planning/services/logistics_adapter.py`
- `backend/app/domains/query_planning/services/plan_bom_adapter.py`
- `backend/app/domains/query_planning/services/query_plan_v2_audit_writer.py`
- `backend/app/domains/query_planning/services/query_planning_v2_service.py`
- `backend/app/domains/query_planning/services/strategy_router.py`

### 接口注册 / 依赖注册

- `backend/app/api/deps.py`
- `backend/app/api/router.py`

### 新增测试

- `tests/unit/query_planning/test_query_plan_v2_schema.py`
- `tests/unit/query_planning/test_strategy_router.py`
- `tests/unit/query_planning/test_query_planning_adapters.py`
- `tests/unit/query_planning/test_query_planning_endpoint_registration.py`

### 验收材料

- `ai/tasks/running/TASK-query-planning-v2-phase3/diff.patch`
- `ai/tasks/running/TASK-query-planning-v2-phase3/test.log`
- `ai/tasks/running/TASK-query-planning-v2-phase3/final-acceptance.md`

## 4. 关键实现说明

### 4.1 schema 安全边界

`QueryPlanningV2ExecutionPolicy` 强制：

- `shadow_only=True`
- `llm_can_execute=False`
- `sql_generation_allowed=False`

`QueryPlanningV2SubQuery` 使用 `extra="forbid"`，测试覆盖了 `raw_sql` 注入会被拒绝。

### 4.2 strategy router 优先级

策略路由采用安全优先级：

1. `UNSUPPORTED`
2. `NO_ANSWER`
3. `CLARIFY`
4. `QUERY_DECOMPOSITION`
5. `DIRECT_RETRIEVAL`
6. `HYDE_RETRIEVAL`
7. `QUERY_REWRITE_SIMPLIFY`
8. 默认 fail closed 到 `CLARIFY`

其中 `composite_decomposed` / `sub_queries` 优先进入 `QUERY_DECOMPOSITION`，避免被普通 `DIRECT_RETRIEVAL` 吞掉。

### 4.3 物流 adapter

只复用：

```python
LogisticsDataQaPlanner.build_plan(question)
```

不调用：

```python
LogisticsDataQaService.query(...)
```

因此不会查数、不会写正式查询历史、不会生成最终业务答案。

### 4.4 Plan BOM adapter

只复用：

```python
PlanBomNluCenterService.understand(question, use_llm=False)
```

不调用：

```python
PlanBomQaService.ask(...)
```

并且在 reviewer 建议后已移除 adapter 层对 `use_llm=True` 的外部开关，避免未来内部调用误启用 LLM。

### 4.5 审计日志

新增 JSONL 审计写入器：

```text
data/logs/query_planning_v2_audit.jsonl
```

写入失败不会阻断诊断接口，会写入 `audit.audit_message`。

## 5. 测试记录

详见：`ai/tasks/running/TASK-query-planning-v2-phase3/test.log`

最终测试结果：

1. Query Planning focused unit tests：`14 passed`
2. 物流 LLM-led composite regression：`19 passed`
3. 物流字段澄清 regression：`6 passed`
4. Backend compile：`compileall OK`
5. Static safety scan：`PASS no free SQL execution patterns`
6. Full regression：`188 passed, 2 warnings`

两个 warning 均来自 openpyxl 读取 xlsm 扩展/条件格式，不是本轮新增问题。

## 6. 独立 Review 结论

已通过独立 reviewer 审查。

Reviewer 结论：

- 未发现阻塞问题；
- 当前实现满足 Phase 3 最小目标；
- 未发现破坏现有物流/BOM主链路；
- 未发现 LLM 直接执行/SQL生成/查数/最终回答风险；
- 可验收。

Reviewer 非阻塞建议中，本轮已处理：

1. BOM adapter 移除可外部传入的 `use_llm=True` 开关；
2. audit JSONL 中的 `query_plan.audit.audit_logged` 与接口返回保持一致；
3. schema 强制 `shadow_only=True`；
4. `QUERY_DECOMPOSITION` 的 `allowed_query_keys` 补入子查询 query_key；
5. 补充对应单元测试，focused tests 从 13 条增加到 14 条。

剩余非阻塞建议：

- 上线前如需把 `/query-planning/v2/diagnose` 作为严格内部接口，可在应用层补充权限依赖或由网关限制。

## 7. 风险点

1. 当前诊断接口已挂到主 `api_router`，如果部署环境没有网关内网隔离，后续建议增加应用层鉴权；
2. HYDE / rewrite 目前仅有 schema 和策略承载，尚未接 LLM 生成；
3. query_plan_v2 当前写 JSONL，不落库，后续 Phase 4/5 如需回放检索可再接入 `sys_query_log.request_payload` 或独立审计表；
4. 当前 BOM adapter 只做 NLU shadow，不做 BOM 候选消歧执行验证。

## 8. 是否影响现有能力

- 物流 Data QA 主链路：不替换、不影响，回归通过；
- Plan BOM QA 主链路：不替换、不影响，全量测试通过；
- Guardrail：未删除或绕过现有 Guardrail；
- 数据库：无迁移、无结构变更；
- 前端：无修改。

## 9. 验收结论

Phase 3 Query Planning V2 最小实现已完成，可验收。

建议下一步进入 Phase 4 受控接入前，先确认：

1. 是否需要为 `/query-planning/v2/diagnose` 增加应用层内部访问保护；
2. 是否允许将 query_plan_v2 shadow 结果写入现有 `sys_query_log.request_payload`；
3. 是否先挑选 10 类问题做 shadow 对比报表，再接入 DIRECT / CLARIFY / UNSUPPORTED 的只读辅助展示。
