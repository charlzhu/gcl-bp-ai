# NL2SQL Logistics M8 Shadow Eval Plan

## 背景

M7 已完成只读中间库 smoke：在环境可用时通过受控 SQLPlan、Renderer、Safety、EXPLAIN/trial 执行真实只读库闭环，并输出脱敏 JSONL/Markdown 验收材料。

M8 不接正式物流 QA 主链路，也不读取 `.env` 或真实数据库连接；本阶段目标是把 shadow-only 离线样例集扩展成可持续评估入口，用于后续 M9/M10 灰度前的候选质量观察。

## 范围

1. 新增 M8 默认样例集（12 条）：
   - 年度发运量按年份拆分；
   - 承运商平均每车费用，保留总费用与车次追溯；
   - 月度总费用趋势；
   - 区域 + 运输方式多维拆分；
   - 承运商发运量 TopN 排名；
   - 始发地 + 客户明细 TopN；
   - 吨数/吨位不支持 fail-closed；
   - 未知价格指标 fail-closed；
   - 报价/单价/运价在未接历史明细表范围时 fail-closed，避免误映射为均价；
   - 写 SQL safety 负例必须停在 safety gate；
   - 缺少 candidate / 非 sql_direct strategy 边界。
2. 增强评估报表维度：
   - `by_metric_id`；
   - `by_dimension_id`；
   - `by_table_id`；
   - `by_category`；
   - `by_business_case`；
   - `by_metric_family`；
   - `expected_status_match_count` / `expected_status_match_rate`；
   - `safety_pass_count` / `safety_block_count`；
   - `executor_touched_count` / `executor_not_touched_count`；
   - `catalog_ref_coverage`；
   - `distinct_catalog_ref_count`。
3. 固定脚本入口：`scripts/dev/run_logistics_nl2sql_m8_shadow_eval.py`。
4. 验收材料默认输出目录：`ai/outbox/kanban/t_7895e090/`。

## 非范围

- 不接前端、聊天主链路或正式物流 Data QA 查询链路；
- 不生成任意 SQL 文本给 LLM 执行；
- 不读取 SAP Oracle MID；
- 不泄露参数值、SQL 原文、`.env`、host/user/password/DSN；
- 不改变 M7 readonly live smoke 的真实只读库能力。

## 验收命令

```bash
backend/.venv/bin/python -m pytest tests/unit/logistics/nl2sql/test_m8_shadow_eval.py -q
backend/.venv/bin/python scripts/dev/run_logistics_nl2sql_m8_shadow_eval.py --artifact-dir ai/outbox/kanban/t_7895e090
```

脚本 stdout 只输出脱敏摘要；详细脱敏 JSONL/Markdown 写入 artifact 目录。
