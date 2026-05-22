# NL2SQL-S8: nl2sql_extended 灰度模式 — 验收报告

## 变更概要

| 文件 | 变更 |
|------|------|
| `backend/app/core/config.py` | **改** — `isp_live_qa_gate_mode` Literal 增加 `"nl2sql_extended"` |
| `backend/app/api/deps.py` | **改** — `get_inventory_sales_production_qa_service` 新增 `nl2sql_extended` 分支，注入 S7 `Nl2SqlSqlPlanPlanner` |
| `backend/app/.../qa_service.py` | **改** — `ask_with_live_gate` 新增 `nl2sql_extended` 分支（与 `nl2sql` 共用 `_ask_with_nl2sql_planner`） |
| `tests/.../test_m8_feature_flag.py` | **改** — 新增 4 条 `nl2sql_extended` 测试 + 1 条 config 字面量测试 |

## 核心设计

### 灰度模式矩阵

| 模式 | 规划器 | 说明 |
|------|--------|------|
| `off` (默认) | 规则规划器 | 不意外激活 NL2SQL |
| `shadow` | 规则规划器 | gate 影子记录 |
| `assist` | 规则规划器 | gate 影子记录 |
| `nl2sql` | S3 `Nl2SqlQueryPlanner` | LLM Metric Resolution |
| **`nl2sql_extended`** | **S7 `Nl2SqlSqlPlanPlanner`** | **LLM 完整 SQLPlan** |

### 数据流

```
nl2sql_extended 模式：
  env: ISP_LIVE_QA_GATE_ENABLED=true, ISP_LIVE_QA_GATE_MODE=nl2sql_extended
    → deps.py 注入 Nl2SqlSqlPlanPlanner
    → qa_service.ask_with_live_gate() 检测 nl2sql_extended
    → _ask_with_nl2sql_planner()
    → nl2sql_planner.build_plan()  → LLM 完整 SqlPlanCandidate → Validator 校验
    → executor.execute(plan) → 返回结果
    → LLM 失败时自动 fallback 到规则规划器
```

## 测试结果

### Focused Tests（5/5 new + 18 existing = 22/22 passed）

| 新测试 | 验证点 |
|--------|--------|
| `test_m8_nl2sql_extended_uses_nl2sql_planner` | nl2sql_extended 使用 NL2SQL 规划器，不调用规则规划器 |
| `test_m8_nl2sql_extended_fallback_to_rule` | LLM 失败时 fallback 到规则规划器 |
| `test_m8_nl2sql_extended_both_fail_returns_blocked` | 两方都失败时返回 blocked |
| `test_m8_config_has_nl2sql_extended_literal` | config.py 支持 nl2sql_extended 字面量 |

### Regression（227/227 passed）

- `tests/unit/business_analysis/` — 全部通过
- `tests/unit/query_planning/` — 全部通过

## 不破坏的基线

- 现有 `off/shadow/assist/nl2sql` 模式 ✅（全部不变）
- S3 `Nl2SqlQueryPlanner` ✅（未修改）
- S7 `Nl2SqlSqlPlanPlanner` ✅（未修改）
- 物流/计划 BOM/功率预测 ✅（未修改）

## 激活方式

上线前只需在 `.env` 中配置：
```
ISP_LIVE_QA_GATE_ENABLED=true
ISP_LIVE_QA_GATE_MODE=nl2sql_extended
```
即可激活 S7 LLM 完整 SQLPlan 灰度，零代码变更。
