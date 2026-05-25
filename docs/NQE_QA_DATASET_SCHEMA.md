# NQE 评测集 JSONL Schema

## 必填字段

| 字段 | 类型 | 说明 |
|---|---|---|
| case_id | string | 唯一标识 |
| domain | string | logistics/business_analysis/plan_bom/power_prediction |
| source_type | string | real_user/paraphrase/asset_generated/safety/edge |
| question | string | 用户自然语言问题 |
| expected_intent | string | 意图标签 |
| expected_result_source | string | deterministic_sql/old_service/PowerPredictionEngine/manual_verified/source_excel/existing_report |
| must_use_llm_sql | bool | 是否必须 LLM 生成 SQL |
| must_pass_safety | bool | 是否必须通过安全预检 |
| must_pass_explain | bool | 是否必须通过 EXPLAIN |
| difficulty | string | easy/medium/hard |
| is_active | bool | 是否激活 |

## 可选字段

| 字段 | 类型 | 说明 |
|---|---|---|
| answer_sql | string | 标准答案 SQL |
| expected_result | any | 预期结果 |
| expected_tables | list | 预期使用的表 |
| expected_metrics | list | 预期使用的指标 |
| expected_dimensions | list | 预期使用的维度 |
| expected_filters | dict | 预期过滤条件 |
| tolerance | float | 数值比较容差 |
| allow_fallback | bool | 是否允许 fallback |
| expected_fallback_reason | string | 预期 fallback 原因 |
| requires_power_engine | bool | 是否需要 PowerPredictionEngine |
| requires_disambiguation | bool | 是否需要候选消歧 |
| tags | list | 标签列表 |
