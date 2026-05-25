# NQE 四域评测集建设方案

## 当前状态

首批 125 条评测题，覆盖 4 个业务域，95 条 answer_sql 全部 EXPLAIN 通过。

## 评测集位置

```
tests/fixtures/nqe_eval/
  logistics_cases.jsonl          (35 cases, 30 answer_sql)
  business_analysis_cases.jsonl  (30 cases, 23 answer_sql)
  plan_bom_cases.jsonl           (30 cases, 22 answer_sql)
  power_prediction_cases.jsonl   (30 cases, 20 answer_sql)
  validate_nqe_eval_dataset.py   (校验脚本)
```

## 分层分布

| source_type | 数量 |
|---|---|
| asset_generated | 58 |
| paraphrase | 31 |
| safety | 16 |
| edge | 11 |
| real_user | 9 |

## 域覆盖

| 域 | 题数 | answer_sql | EXPLAIN OK | needs_review |
|---|---|---|---|---|
| logistics | 35 | 30 | 30 | 5 |
| business_analysis | 30 | 23 | 23 | 7 |
| plan_bom | 30 | 22 | 22 | 8 |
| power_prediction | 30 | 20 | 20 | 13 |

## expected_result_source

| 来源 | 数量 |
|---|---|
| deterministic_sql | 95 |
| manual_verified | 24 |
| PowerPredictionEngine | 4 |
| old_service | 2 |

## real_user 说明

9 条标记为 real_user 的题来自项目既有业务问答场景（物流运输量/产销存产量/BOM明细/功率模型），不声称来自企业正式采集流程。如需要正式标注来源，后续可补充 `collected_from` / `collected_at` 字段。

## 校验结果

| 检查项 | 结果 |
|---|---|
| 总题量 >=120 | ✅ 125 |
| 每域 >=30 | ✅ 35/30/30/30 |
| deterministic_sql 有 answer_sql | ✅ 95/95 |
| EXPLAIN smoke 通过 | ✅ 95/95 |
| safety expected_status=safety_blocked | ✅ 16/16 |
| DB context | ✅ 125/125 |
| Milvus retrieval | ✅ 125/125 |

## 下一步

NQE-QA-DATASET-1：编写评测执行器。
