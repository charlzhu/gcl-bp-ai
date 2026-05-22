# NQE-S1 最终验收报告

## 交付概述

NQE-S1 实现了 LangGraph 统一编排 NL2SQL SQLPlan shadow 流程的基础设施。

**变更范围**：在 `business_qa_graph` 中新增 NL2SQL shadow adapter，在 `question_understanding_node` 增加 NL2SQL 分支，shadow 结果写入 `state.query_plan_v2`。

## 修改文件清单

### 修改（已有文件）

| 文件 | 变更说明 |
|------|----------|
| `backend/app/domains/business_qa_graph/schemas/domain.py` | 新增 `logistics_nl2sql_shadow` capability ID |
| `backend/app/domains/business_qa_graph/schemas/state.py` | 新增 `query_plan_v2` 字段 + 初始状态初始化 |
| `backend/app/domains/business_qa_graph/nodes/question_understanding_node.py` | 新增 NL2SQL shadow 分支 + `_resolve_nl2sql_adapter` 函数 |
| `backend/app/domains/business_qa_graph/builder.py` | 新增 `nl2sql_adapter` 参数注入 question_understanding_node |

### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/app/domains/business_qa_graph/nl2sql_adapter.py` | NL2SQL Graph Adapter（调用 LogisticsNl2SqlDomainRouter + shadow pipeline） |
| `tests/unit/business_qa_graph/test_nqe_s1_nl2sql_shadow.py` | NQE-S1 focused tests（12 tests） |

## 测试结果

```
tests/unit/business_qa_graph/test_nqe_s1_nl2sql_shadow.py - 12 passed
tests/unit/business_qa_graph/ (全部) - 107 passed, 8 failed (预存 settings/endpoint 问题)
tests/unit/semantic_catalog/ - 108 passed, 7 failed (预存 YAML 数据缺失)
```

### 12 focused tests

1. `test_capability_includes_logistics_nl2sql_shadow` - capability ID 已注册 ✓
2. `test_state_accepts_query_plan_v2_field` - state 可承载 query_plan_v2 ✓
3. `test_initial_state_includes_query_plan_v2` - 初始状态包含空 query_plan_v2 ✓
4. `test_nl2sql_adapter_route_skips_non_logistics_question` - 非物流问题 route_skipped ✓
5. `test_nl2sql_adapter_accepts_logistics_question` - 物流问题 shadow 生成 ✓
6. `test_nl2sql_adapter_handles_exception_gracefully` - 空问题安全处理 ✓
7. `test_nl2sql_adapter_writes_query_plan_v2_fields` - shadow 结果字段完整 ✓
8. `test_question_understanding_node_routes_nl2sql_shadow_capability` - NL2SQL shadow 分支触发 ✓
9. `test_question_understanding_node_falls_back_for_logistics_data_qa` - 原有 logistics_data_qa 路径不受影响 ✓
10. `test_builder_injects_nl2sql_adapter_to_question_understanding` - builder 注入 adapter ✓
11. `test_graph_with_nl2sql_shadow_injected_state` - 子图 E2E 验证 ✓
12. `test_existing_graph_structure_unchanged` - 无 adapter 时 graph 仍可编译 ✓

## 编译检查

所有 5 个变更/新增文件通过 `py_compile` 检查 ✓

## 关键设计决策

1. **NL2SQL shadow 只记录，不执行**：当 capabilities 包含 `logistics_nl2sql_shadow` 时，question_understanding_node 调用 NL2SQL adapter 生成 shadow 结果写入 `query_plan_v2`，但 understanding_status 设为 UNSUPPORTED 以确保不进入 execute_node。

2. **fail-closed**：adapter 中所有异常都被捕获，返回 error 状态而不中断主链路。

3. **延迟导入**：nl2sql_adapter 和 domain_router 均使用延迟导入避免循环依赖。

4. **当前阶段 shadow 为最小实现**：不调用完整 NL2SQL pipeline（需要 LLM/Milvus），只记录 domain_route 信息。后续 NQE-S2 可扩展。

## 不影响的能力

- 物流 data_qa 主链路不受影响 ✓
- 计划 BOM QA 路径不受影响 ✓
- 功率预测能力不受影响 ✓
- 现有 NL2SQL-A/B/C/D 执行链路不受影响 ✓

## 预存问题（非 NQE-S1 引入）

- `logistics_query_planner_v2_enabled` settings 缺失（7 个已有测试因此失败）
- `/business-qa/stream` endpoint 未注册（1 个已有测试因此失败）
- semantic_catalog YAML 数据文件缺失（7 个已有测试因此失败）
