# NL2SQL Logistics M6 Shadow Smoke + Evaluation Report MVP Plan

## 1. M6 目标

M6 在 M5 `LogisticsNl2SqlShadowPipeline` 与 `LogisticsNl2SqlEvaluationLogRecord` 的基础上，补充一个完全离线、可重复执行的物流 NL2SQL shadow smoke runner 和确定性 evaluation report MVP。

目标链路：

```text
offline sample set
→ M5 shadow pipeline
→ offline fake executor
→ sanitized evaluation log records
→ deterministic evaluation report
→ JSON / Markdown report artifacts
```

M6 只服务内部离线验收，不接正式物流 QA 主链路，不改变既有 planner / data_qa_planner，不改前端，不建数据库迁移。

## 2. M5 / M6 / M7 边界

| 阶段 | 边界 | 本阶段行为 |
| --- | --- | --- |
| M5 | 单次 shadow pipeline 与脱敏 evaluation log | 已提供 validator → renderer → safety → explain/trial → log 的单次链路 |
| M6 | 离线样例集、批量 runner、评估报表 | 本阶段新增，默认只使用 fake executor，不读取 `.env`，不连接真实 MySQL/Oracle/SAP/Milvus |
| M7 | 只读中间库 smoke | 后续单独阶段才允许接只读 middle_db smoke；M6 严禁真实库 EXPLAIN/SELECT |

M6 的 fake executor 只记录离线调用并返回预置行或受控异常，用于覆盖成功、验证失败、安全失败、执行失败和脱敏场景。

## 3. 离线样例类型

默认样例由 `build_default_logistics_nl2sql_shadow_smoke_samples()` 生成，样例 ID 固定，便于离线验收复现：

1. `success_valid_plan`：合法 SQLPlan + fake executor explain/trial 成功。
2. `skipped_missing_candidate`：缺少 candidate，跳过 SQL 阶段。
3. `unsupported_non_sql_direct_strategy`：非 `sql_direct` strategy，停在 candidate 边界。
4. `skipped_non_logistics_domain`：非 logistics domain，跳过 SQL 链路。
5. `skipped_non_middle_db_source`：非 middle_db source，跳过 SQL 链路。
6. `validation_failed_unknown_metric`：未知指标由 SQLPlan validator fail-closed。
7. `safety_failed_select_star`：fixture renderer 产生 `SELECT *`，仍交给 M4 safety 拒绝。
8. `explain_failed_fake_executor`：fake executor explain 失败并脱敏。
9. `trial_failed_fake_executor`：fake executor trial 失败并脱敏。
10. `redaction_failure_sanitized`：question / error / warning 中包含 DSN、password、token、SQL-like 文本，最终报表不得泄露。

样例只使用通用物流业务模板，不 hardcode 历史聊天中的真实答案、客户或业务数据。

## 4. Evaluation report 字段

`build_logistics_nl2sql_evaluation_report()` 输出 `LogisticsNl2SqlEvaluationReport`，字段包括：

- `total`
- `by_status`
- `by_stage`
- `by_error_code`
- `success_count`
- `failure_count`
- `skipped_count`
- `unsupported_count`
- `success_rate`
- `fail_closed_count`
- `safety_block_count`
- `execution_failure_count`
- `sql_hash_coverage`
- `top_errors`
- `sample_outcomes`
- `warnings`

报表安全边界：

- 不输出 SQL 原文。
- 不输出 SQL 参数值或参数 key。
- 不输出 DSN、password、token、API key、Bearer token、`sk-*`。
- `sample_outcomes` 只包含样例 ID、业务描述、status、stage、error_codes。
- 支持 `model_dump(mode="json")` / `model_dump_json()` 序列化。
- 支持 `render_logistics_nl2sql_evaluation_report_markdown()` 渲染 Markdown。

## 5. 如何运行单测

M6 focused tests：

```bash
backend/.venv/bin/python -m pytest tests/unit/logistics/nl2sql/test_shadow_smoke.py tests/unit/logistics/nl2sql/test_evaluation_report.py -q
```

NL2SQL adjacent tests：

```bash
backend/.venv/bin/python -m pytest tests/unit/logistics/nl2sql -q
```

物流单元回归：

```bash
backend/.venv/bin/python -m pytest tests/unit/logistics -q
```

全量单元回归：

```bash
backend/.venv/bin/python -m pytest tests/unit -q
```

编译与 diff 检查：

```bash
backend/.venv/bin/python -m py_compile backend/app/domains/logistics/services/nl2sql/shadow_smoke.py backend/app/domains/logistics/services/nl2sql/evaluation_report.py
git diff --check
```

## 6. M7 预留

M7 才允许在明确只读、安全、限时、限行、可审计的前提下接入真实 middle_db smoke。M6 不读取 `.env`，不构造真实 DSN，不执行真实库 `EXPLAIN` / `SELECT`，也不连接 Oracle / SAP / Milvus。
