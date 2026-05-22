# NL2SQL-S7: LLM 完整 SQLPlan 规划器 — 验收报告

## 变更概要

| 文件 | 变更 |
|------|------|
| `backend/.../nl2sql_sqlplan_planner.py` | **新增** — `InventorySalesProductionNl2SqlSqlPlanPlanner` 类（560行） |
| `tests/.../test_nl2sql_sqlplan_planner.py` | **新增** — 16 条 focused 测试 |
| `tests/.../test_nl2sql_catalog_recall.py` | **改** — 修复 mock 污染导致 `test_recall_no_api_key_fallback` 在 settings 有 API Key 时失败的问题 |

## 核心设计

### Nl2SqlSqlPlanPlanner 类

1. 实现与 `NlQueryPlanner` 相同的 `build_plan(question)` 接口
2. 内部调用 LLM 生成完整 `InventorySalesProductionSqlPlanCandidate`
3. 经 `InventorySalesProductionSqlPlanValidator` fail-closed 校验
4. 校验通过后转换为 `InventorySalesProductionQueryPlan` 由现有 executor 执行
5. LLM 失败、返回 clarify/unsupported、校验失败时自动 fallback 到规则规划器
6. 支持 `build_plan_with_debug()` — 返回 `mode="llm_sqlplan" | "fallback_rule"` 调试信息

### 架构

```
用户问题 → Nl2SqlSqlPlanPlanner
  → LLM 输出完整 SqlPlanCandidate（含 filters/order_by/business_rules/metrics/dimensions/period）
  → SqlPlanValidator fail-closed 校验（禁止 raw_sql/SQL-like 字符串、白名单验证）
  → 校验通过：_sqlplan_to_query_plan() 转换为 QueryPlan
  → 校验失败 / LLM 异常 / clarify / unsupported → fallback 到 NlQueryPlanner（规则规划器）
  → 最终调用 executor.execute(plan) — 与现有链路一致
```

### LLM Prompt 设计

- 完整的 System Prompt（含 QueryKey 规则、指标列表、维度列表、过滤维度列表）
- 输出 JSON 格式约束（`InventorySalesProductionSqlPlanCandidate` 结构）
- 显式规则：不输出 raw_sql、只使用 catalog 中的 metric_code/dimension_id
- Filters 中 business_year 值必须与 plan.year 一致

## 测试结果

### Focused Tests（16/16 passed）

| 测试 | 验证点 |
|------|--------|
| `test_nl2sql_sqlplan_llm_success` | LLM 返回完整 SQLPlan，build_plan 返回 QueryPlan |
| `test_nl2sql_sqlplan_with_dimensions` | LLM 返回带维度的 SQLPlan |
| `test_nl2sql_sqlplan_with_filters` | LLM 返回带过滤条件的 SQLPlan → filters dict |
| `test_nl2sql_sqlplan_clarify_fallback` | clarification → fallback 规则 |
| `test_nl2sql_sqlplan_unsupported_fallback` | unsupported → 两方均失败时抛出异常 |
| `test_nl2sql_sqlplan_validation_fails_fallback` | 非法 query_key 校验失败 → fallback |
| `test_nl2sql_sqlplan_fallback_to_rules` | LLM 异常 → fallback |
| `test_nl2sql_sqlplan_no_fallback_raises_error` | fallback_on_error=False → 抛出异常 |
| `test_nl2sql_sqlplan_no_api_key_fallback` | 无 API Key → fallback |
| `test_nl2sql_sqlplan_empty_question` | 空问题 → clarification |
| `test_nl2sql_sqlplan_debug_llm_mode` | debug 模式返回 mode=llm_sqlplan |
| `test_nl2sql_sqlplan_debug_fallback_mode` | debug 模式返回 mode=fallback_rule |
| `test_nl2sql_sqlplan_implements_same_interface` | 接口一致性（与 NlQueryPlanner） |
| `test_nl2sql_sqlplan_validator_rejects_raw_sql` | raw_sql 字段被阻断 |
| `test_nl2sql_sqlplan_period_compare` | period_compare 正确转换 |
| `test_module_exports_all` | 模块导出完整性 |

### Regression（223/223 passed）

- `tests/unit/business_analysis/` — 全部通过
- `tests/unit/query_planning/` — 全部通过

## 变更文件

```
 M tests/unit/business_analysis/test_inventory_sales_production_nl2sql_catalog_recall.py
 A backend/app/domains/business_analysis/services/inventory_sales_production/nl2sql_sqlplan_planner.py
 A tests/unit/business_analysis/test_inventory_sales_production_nl2sql_sqlplan_planner.py
```

## 不破坏的基线

- 物流问答 ✅（未修改任何物流文件）
- 计划 BOM 问答 ✅（未修改任何 BOM 文件）
- 功率预测 ✅（未修改功率预测文件）
- 前端体验 ✅（未修改任何前端文件）
- 现有 S1~S6 NL2SQL 能力 ✅（未修改现有 planner）

## 当前已完成状态

| 步骤 | 状态 |
|------|------|
| S1 (Semantic Catalog 增强) | ✅ Done |
| S2 (LLM Catalog Recall 服务) | ✅ Done |
| S3 (LLM Metric Resolution 规划器) | ✅ Done |
| S4 (M6 shadow 样本更新 — NL 变体) | ✅ Done |
| S5 (M7 双轨对比) | ✅ Done |
| S6 (M8 灰度接管) | ✅ Done |
| **S7 (LLM 完整 SQLPlan 规划器)** | **✅ 本轮完成** |
| S8 (规则规划器退役) | ⏳ 待开始 |

## 下一阶段建议

**S8: 规则规划器退役** — 移除 `nl_query_planner.py` 中的规则逻辑，完全切换到 LLM 规划器。
需要对现有 `_ask_with_nl2sql_planner()` 中的 nl2sql_planner 注入点进行扩展，在 `nl2sql` 模式下使用 `Nl2SqlSqlPlanPlanner`。
