# gcl-bp-ai: NL2SQL M3 SQLPlan 候选与确定性校验 MVP - Final Acceptance

## 结论

任务可判定为完成。当前看板阻塞原因不是代码/测试失败，而是两轮 worker 均超过 7200 秒运行上限，最后卡在独立 review / fallback review 阶段。

## 阻塞原因

看板任务 `t_d4358d4d` 当前为 `blocked`，runs 显示：

- run 15：`timed_out`，`elapsed 7241s > limit 7200s`
- run 16：`timed_out`，`elapsed 8131s > limit 7200s`
- dispatcher 最终 `gave_up`：失败 2 次达到限制

worker 日志显示，主要实现和测试已经完成，阻塞发生在复审阶段：delegate reviewer / fallback codex review 多次发生 provider/API timeout 或 KeyboardInterrupt。

## 已完成能力

- 新增 SQLPlan candidate schema。
- 新增确定性 SQLPlan validator。
- 通过 `catalog_id/catalog_version` 回查 canonical Semantic Catalog。
- 对 table/metric/dimension/filter/group_by/order_by/join/business_rules 执行 fail-closed 校验。
- 阻断 `raw_sql/sql/where/having/free_sql` 等禁止字段和 SQL-like 字符串。
- 阻断未知 catalog ID、catalog version mismatch、非白名单表、未知字段、污染 join grammar。
- 阻断 unsupported tonnage 被 LLM 改写为 MW 后进入 sql_direct。
- 校验默认 2023-2026 时间边界、多年份 bucket、越界年份、非整数年份。
- 未生成 SQL，未执行 SQL，未 EXPLAIN，未查库，未接正式 QA，未改前端。

## 本次人工复核 / 复跑结果

重新复跑：

```bash
backend/.venv/bin/python -m pytest tests/unit/logistics/nl2sql/test_sql_plan.py -q
# 32 passed in 1.33s

backend/.venv/bin/python -m pytest tests/unit/logistics/nl2sql/test_semantic_catalog.py tests/unit/logistics/nl2sql/test_catalog_retrieval.py tests/unit/logistics/query_planner_v2/test_logistics_query_planner_v2.py -q
# 47 passed, 9 warnings in 1.60s

backend/.venv/bin/python -m pytest tests/unit/logistics -q
# 79 passed, 9 warnings in 2.46s

backend/.venv/bin/python -m pytest tests/unit -q
# 123 passed, 9 warnings in 3.49s

backend/.venv/bin/python -m py_compile backend/app/domains/logistics/services/nl2sql/sql_plan.py
# passed

git diff --check -- backend/app/domains/logistics/services/nl2sql/__init__.py backend/app/domains/logistics/services/nl2sql/sql_plan.py tests/unit/logistics/nl2sql/test_sql_plan.py ai/outbox/kanban/t_d4358d4d/test.log ai/outbox/kanban/t_d4358d4d/static-scan.json ai/outbox/kanban/t_d4358d4d/diff.patch
# passed
```

## 独立 review 结论

已补做独立只读 reviewer 复审，结果写入：

- `ai/outbox/kanban/t_d4358d4d/review-result-final.json`

结论：

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": []
}
```

此前 `review-result-round2.json` 中的 blocker 已被后续实现和测试关闭：

- 大范围 `between` 年份不再先展开后校验；
- `>=` / `<=` 年份操作符被禁止；
- `unsupported_tonnage` 规则在 `sql_direct` 中直接阻断；
- 非整数/布尔年份值 fail-closed；
- schema_version mismatch 已覆盖。

## 变更文件

- `backend/app/domains/logistics/services/nl2sql/sql_plan.py`
- `backend/app/domains/logistics/services/nl2sql/__init__.py`
- `tests/unit/logistics/nl2sql/test_sql_plan.py`
- `ai/outbox/kanban/t_d4358d4d/diff.patch`
- `ai/outbox/kanban/t_d4358d4d/test.log`
- `ai/outbox/kanban/t_d4358d4d/static-scan.json`
- `ai/outbox/kanban/t_d4358d4d/review-result-final.json`
- `ai/outbox/kanban/t_d4358d4d/final-acceptance.md`

## 风险与后续建议

非阻塞建议：

1. 后续阶段可以继续补充更细粒度用例：逐一覆盖 `sql/where/having/free_sql` 禁止键。
2. 后续可对错误码里回显的未知 ID / catalog_version / requested_unit 做统一截断或脱敏。
3. 后续 M4 renderer 前应继续保持 fail-closed，不允许未通过 M3 validator 的 plan 进入 SQL 生成。

## 是否影响现有能力

不影响现有 BOM / 物流正式 QA 主链路。本阶段只新增 NL2SQL shadow 架构下的 SQLPlan schema 与 validator，没有接入正式问答链路，没有执行数据库查询，没有修改前端。
