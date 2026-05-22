# M11 设计审计与执行方案

## 一、M10 边界审计结论

### 1. M10 全部合入 agent/bp-main

- HEAD: `710fb9a9 feat(nl2sql): M10-D2/D3/D4/D5 shadow gate 全链路`
- 无未关闭的边界性问题

### 2. M10 当前目录结构

```
backend/app/domains/logistics/services/nl2sql/
  m10d_shadow_gate.py           — D2 核心 gate（~379行）
  m10d2_explain_smoke.py        — D2-2 EXPLAIN smoke runner（~472行）
  sql_plan_repair.py            — D4 SQLPlan 修复（~217行）
  sql_ast_safety.py             — D3 SQLGlot AST 安全校验（~417行）
  m10_shadow_gate_runner.py     — D5 评估集 runner（~525行）
  shadow_pipeline.py            — 串联 pipeline（embed repair）
  sql_execution.py              — Executor 协议 + FakeExecutor（含 EXECUTE 模式）

tests/unit/logistics/nl2sql/
  test_m10d_shadow_gate.py      — D2 测试（~547行）
  test_m10_shadow_gate_runner.py— D5 测试（~54行）
  test_m10c_live_shadow_adapter.py — D? 测试

scripts/dev/
  run_logistics_nl2sql_m9_provider_smoke.py     — M9 live provider smoke（~224行）
  run_logistics_nl2sql_m10_shadow_gate.py         — M10 CLI 入口
```

### 3. M10 未留边界性问题

| 检查项 | 结论 |
|--------|------|
| EXPLAIN 结果处理 | 只有 `explain_status: "success" | "failed" | "skipped" | "disabled"`，未做 type 分类 |
| Live provider smoke | M9 有成功样例，但样本少（~2条），未正式化 |
| Timeout 处理 | `timeout_ms` 只记录脱敏摘要，不做真实超时中断 |
| 联合评估 | M9 SQLPlan gen + M10 gate 分别独立，未串联为统一评估 |

---

## 二、M11 子阶段执行方案

### 并行策略

```
M11-0（设计审计，已完成）→ 输出本文档
                          ↓
M11-1 (Live Provider Smoke)  ──┐
                                ├→ M11-3 (联合 Runner)
M11-2 (EXPLAIN 分类)         ──┘
                                │
M11-4 (Timeout 中断)         ───┘  (独立并行，不阻塞 M11-3)
```

---

### M11-1：Live Provider Smoke 正式化

**目标**：扩展 M9 的 live provider smoke 到正式评估集（≥5 样本），shadow-only。

| 项目 | 说明 |
|------|------|
| **入口文件** | `scripts/dev/run_logistics_nl2sql_m9_provider_smoke.py`（扩展） |
| **被测文件** | `backend/app/domains/logistics/services/nl2sql/catalog_retrieval.py`（Embedding/Rerank/Milvus） |
| **新建文件** | —（在现有 M9 CLI 入口中扩展） |
| **测试文件** | 无（provider smoke 需真实外部 provider，不做单元测试；写 focused test 在 `test_m9_sqlplan_generation.py` 中加 producer mock test） |
| **样本覆盖** | ≥5 条，覆盖 success / guard / edge / safety 类别 |
| **验收** | CLI smoke 跑通、全量 NL2SQL 292+ passed |

---

### M11-2：EXPLAIN 结果分类正式化

**目标**：新建 `m10d_explain_classifier.py`，对 EXPLAIN 输出按 type 脱敏分类。

| 项目 | 说明 |
|------|------|
| **新建文件** | `backend/app/domains/logistics/services/nl2sql/m10d_explain_classifier.py` |
| **串联改动** | `m10d_shadow_gate.py` — 在 EXPLAIN 阶段后调用 classifier |
| **测试文件** | `tests/unit/logistics/nl2sql/test_m10d_explain_classifier.py` |
| **分类** | SUCCESS / ERROR_SYNTAX / ERROR_TABLE / ERROR_COLUMN / ERROR_TIMEOUT / ERROR_OTHER |
| **验收** | focused test 全分类通过、全量 NL2SQL 292+ passed |

---

### M11-3：M9+M10 联合 Shadow Runner

**目标**：串联 M9 SQLPlan gen + M10 shadow gate 的统一评估 Runner。

| 项目 | 说明 |
|------|------|
| **入口文件** | 新建 `scripts/dev/run_logistics_nl2sql_m11_joint_runner.py` |
| **新建文件** | `backend/app/domains/logistics/services/nl2sql/m11_joint_runner.py` |
| **测试文件** | `tests/unit/logistics/nl2sql/test_m11_joint_runner.py` |
| **依赖** | M11-1（Live Provider Smoke 正式化）+ M11-2（EXPLAIN 分类正式化）|
| **验收** | 联合 runner 跑通、全量 NL2SQL 292+ passed |

---

### M11-4：Timeout 真实中断语义

**目标**：给 gate 执行添加真实超时中断，不依赖 gunicorn 超时。

| 项目 | 说明 |
|------|------|
| **改动文件** | `backend/app/domains/logistics/services/nl2sql/sql_execution.py`（添加超时机制） |
| **串联改动** | `m10d_shadow_gate.py`（传递 timeout 到 executor） |
| **测试文件** | `tests/unit/logistics/nl2sql/test_sql_execution.py`（扩展超时测试） |
| **方案** | `asyncio.wait_for` — 在 executor 层对 EXPLAIN / trial 执行设置超时 |
| **验收** | 超时触发/超时不中断正常流/并行超时测试通过、全量 NL2SQL 292+ passed |

---

## 三、关键执行原则

1. **TDD**：所有代码先 RED 测试，再 GREEN 实现
2. **shadow-only**：不接正式 QA 主链路
3. **不暴露技术内容**：report/日志不输出 SQL 原文、参数值、表名、字段名
4. **不破坏基线**：保持物流/BOM/功率预测能力不受影响
5. **默认关闭**：所有 gate 功能默认关闭，显式 enable 才生效
6. **全量回归**：每个子阶段完成后必须跑全量 NL2SQL 回归（292+ passed）

---

## 四、执行顺序

```text
1. 并行启动 M11-1 + M11-2 + M11-4
   （按子阶段顺序执行各自的 RED→GREEN→回归）

2. M11-1 + M11-2 完成后 → 启动 M11-3

3. M11-3 + M11-4 完成后 → 全部合入 agent/bp-main
```
