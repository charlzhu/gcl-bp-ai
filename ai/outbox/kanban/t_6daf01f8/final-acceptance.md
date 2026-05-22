# LQG-7 验收报告

## 任务摘要

将计划 BOM 功率测算三项 capability（功率预测、供应商推荐、功率配置影响值对比）纳入 LangGraph 统一编排 Graph。

## 修改文件

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `backend/app/domains/business_qa_graph/nodes/execute_node.py` | 修改 | LQG-7：execute_node 读取 state.capabilities，传递到各域执行函数，trace 事件和执行结果中记录当前 capability |
| `tests/unit/business_qa_graph/test_lqg7_execute_node_power.py` | 新增 | LQG-7 focused tests：11 个测试覆盖功率预测/供应商推荐/影响值对比全链路 |

## 关键改动

1. **execute_node 增强**：从 state 中读取 `capabilities` 列表，传递给 `_execute_logistics` 和 `_execute_plan_bom` 内部函数
2. **trace 事件增强**：`execution_complete` 事件 payload 中新增 `capabilities` 字段，便于审计追踪当前执行的能力
3. **执行结果增强**：`execution_result` 中新增 `executed_capabilities` 字段，记录实际执行的能力列表
4. **移除未使用变量**：移除 execute_node 顶层未使用的 `question` 变量声明（各域执行函数内部自行从 state 提取）

## 测试结果

```
tests/unit/business_qa_graph/ — 81 passed (70 原有 + 11 新增)
```

### LQG-7 新增测试（11 tests）

| # | 测试 | 验证点 |
|---|---|---|
| 1 | `test_execute_node_power_prediction_capability_calls_service` | 功率预测 capability 经 execute_node 调用 PlanBomQaService.ask |
| 2 | `test_execute_node_power_prediction_result_preserves_business_fields` | 功率预测结果保留功率档、预测比例等业务化字段 |
| 3 | `test_execute_node_supplier_recommendation_capability_calls_service` | 供应商推荐 capability 返回推荐结果 |
| 4 | `test_execute_node_factor_effect_compare_capability_calls_service` | 配置影响值对比 capability 返回差值 |
| 5 | `test_execute_node_power_missing_params_triggers_clarification` | 缺关键参数时业务化追问，不泄露技术细节 |
| 6 | `test_execute_node_power_no_active_model_explains` | 无 active 功率模型时业务化说明 |
| 7 | `test_execute_node_power_result_sanitized_no_tech_leak` | 功率结果不泄露 SQL/表名/query_key/planner/raw/debug |
| 8 | `test_execute_node_power_exception_handles_gracefully` | 功率服务异常时安全降级，不崩溃 |
| 9 | `test_execute_node_regular_bom_capability_still_works_after_power` | 普通 BOM 材料查询不退化 |
| 10 | `test_execute_node_logistics_domain_still_works_after_power` | 物流域执行不退化（LQG-5 回归） |
| 11 | `test_graph_path_routes_power_capabilities_to_execute` | 三种功率 capability 正确路由到 execute 节点 |

### 现有测试回归

- LQG-2 (domain registry): 13 tests — PASS
- LQG-3 (question understanding): 12 tests — PASS
- LQG-4 (plan validate): 20 tests — PASS
- LQG-5 (logistics execute): 10 tests — PASS
- LQG-6 (plan_bom execute): 9 tests — PASS
- LQG-1 (skeleton): 6 tests — PASS

## 全量回归

```
tests/ — 610 passed, 2 pre-existing failures (logistics carrier filter, 非本次变更)
```

## 静态扫描

```
ruff: All checks passed!
py_compile: OK
```

## 架构合规

- [x] 执行仍通过 PlanBomQaService 内部功率分支，不拆散独立 Service
- [x] LLM 不计算功率档位、比例、供应商效率或匹配度
- [x] 未恢复临时 token
- [x] 用户展示仍归属计划 BOM
- [x] capabilities 在 trace 事件和执行结果中可审计
- [x] 不暴露 SQL/表名/字段名/query_key/planner/guardrail/schema/raw/debug/LLM
- [x] 不触及当前共享工作区 data-agent/
- [x] 未 push/deploy/reset/clean/stash/rebase/squash
- [x] 新增/修改代码均有中文注释

## 阶段边界

- [x] 未进入物管/SAP MID M2
- [x] 未引入 ES
- [x] 未替换 NL2SQL
- [x] LangGraph 只做外层编排，NL2SQL/QueryPlanningV2/SQLPlan 是内层受控查询能力
- [x] 禁止 LLM 自由 SQL、查数、算功率或改结构化事实
- [x] 保留旧接口和回退
- [x] 用户可见回答不暴露技术实现细节

## 验收材料

| 文件 | 路径 |
|---|---|
| diff.patch | `ai/outbox/kanban/t_6daf01f8/diff.patch` |
| test.log | `ai/outbox/kanban/t_6daf01f8/test.log` |
| final-acceptance.md | `ai/outbox/kanban/t_6daf01f8/final-acceptance.md` |
