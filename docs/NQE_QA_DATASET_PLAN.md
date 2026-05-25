# NQE 四域评测集建设方案

## 当前状态

首批 101 条评测题，覆盖 4 个业务域。

## 评测集位置

```
tests/fixtures/nqe_eval/
  logistics_cases.jsonl          (33 cases)
  business_analysis_cases.jsonl  (26 cases)
  plan_bom_cases.jsonl           (23 cases)
  power_prediction_cases.jsonl   (19 cases)
```

## 分层分布

| source_type | 数量 | 说明 |
|---|---|---|
| real_user | 14 | 真实业务问题 |
| paraphrase | 25 | 基于核心问题的改写 |
| asset_generated | 41 | 基于真实表/字段/指标生成 |
| safety | 16 | SQL 注入/系统表攻击 |
| edge | 5 | 空结果/参数缺失/无候选 |

## 域覆盖

| 域 | 数量 | 覆盖重点 |
|---|---|---|
| logistics | 33 | 运输量/基地/承运商/客户/月度/安全 |
| business_analysis | 26 | 产量/销量/库存/指标别名/基地 |
| plan_bom | 23 | 订单/SAP/物料类别/BOM compare/消歧 |
| power_prediction | 19 | 模型/供应商/档位/因子/PowerPredictionEngine |

## expected_result_source

| 来源 | 数量 |
|---|---|
| deterministic_sql | 96 |
| old_service | 2 |
| PowerPredictionEngine | 3 |

## 验收状态

| 检查项 | 结果 |
|---|---|
| JSONL 格式 | ✅ 0 errors |
| case_id 唯一 | ✅ |
| domain 合法 | ✅ |
| source_type 合法 | ✅ |
| answer_sql 空缺 | ⚠️ 101/101 (需 LLM 生成) |
| 需人工确认 | 101/101 |

## 下一步

NQE-QA-DATASET-1：编写评测执行器，逐题调用 NQE SQL Agent 生成 SQL 并与预期对比。
