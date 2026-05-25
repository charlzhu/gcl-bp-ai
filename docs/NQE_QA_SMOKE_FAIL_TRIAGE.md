# NQE Smoke 剩余 5 Fail 精确归因

时间: 2026-05-25

---

## 1. NQE-logi-41fe3a7a → dataset_issue

question: 华东区域在历史物流台账中的总发运件数是多少?

| 项目 | answer_sql | NQE SQL |
|---|---|---|
| SQL | `SELECT COUNT(*) FROM dws_logistics_detail_union WHERE region_name LIKE '%华东%'` | `SELECT SUM(actual_qty) AS total_shipment_count FROM dwd_logistics_hist_shipment_detail WHERE region_name = '华东'` |
| 表 | dws_logistics_detail_union | dwd_logistics_hist_shipment_detail ❌ 不同表 |
| 字段 | COUNT(*) | SUM(actual_qty) |
| 过滤 | LIKE '%华东%' | = '华东' ❌ 精确匹配 |
| 结果 | 9917 | 13,877,138 |

**归因**: dataset_issue + sql_agent_issue

- answer_sql 使用 `dws_logistics_detail_union`（28K rows），正确
- NQE 使用 `dwd_logistics_hist_shipment_detail` 不正确 — 这是 DWD 层历史明细表，不是统一发运汇总表
- 语义资产中 `dwd_logistics_hist_shipment_detail` 不应作为首选的查询表，应引导 LLM 使用 `dws_logistics_detail_union`
- answer_sql 口径正确（9917 条），NQE 口径不对

**修复建议**: expected_tables 中不应包含 `dwd_logistics_hist_shipment_detail`，优先引导 `dws_logistics_detail_union`。同时 NQE prompt 中需加强"历史"语义 → 所有年份。

---

## 2. NQE-logi-14ff867b → sql_agent_issue + dataset_issue

question: 安徽省历史发运的总费用是多少?

| 项目 | answer_sql | NQE SQL |
|---|---|---|
| SQL | `SELECT SUM(total_fee) FROM dws_logistics_detail_union WHERE origin_place LIKE '%安徽%'` | `SELECT SUM(total_fee) FROM dwd_logistics_hist_shipment_detail WHERE province LIKE '%安徽%'` |
| 表 | dws_logistics_detail_union | dwd_logistics_hist_shipment_detail ❌ 不同表 |
| 字段 | SUM(total_fee) | SUM(total_fee) ✅ |
| 过滤 | origin_place LIKE '%安徽%' | province LIKE '%安徽%' |
| answer 结果 | NULL（total_fee 确实为 NULL） | 未知 |

**归因**: dataset_issue + sql_agent_issue

- answer_sql 本身返回 NULL — `dws_logistics_detail_union` 中 total_fee 字段可能全为 NULL
- 这导致 answer_sql_result 为 `[{'SUM(total_fee)': None}]`，执行器 scalar 对比时 `None vs 数字` → value_diff
- NQE 选错表 `dwd_logistics_hist_shipment_detail`（同 case 1）

**修复建议**: 
1. dataset: 确认 total_fee 在 dws_logistics_detail_union 中是否有值，或改用 total_fee / shipment_trip_count 做均价
2. NQE: 同 case 1，引导使用 dws_logistics_detail_union

---

## 3. NQE-ba-c5720646 → sql_agent_issue

question: 各基地产量对比

| 项目 | answer_sql | NQE SQL |
|---|---|---|
| SQL | `...WHERE business_year=2024...AND is_published_month=1 AND base_name IS NOT NULL ORDER BY SUM DESC` | `...WHERE...business_year = YEAR(CURDATE()) GROUP BY base_name` |
| 年份 | 硬编码 2024 | `YEAR(CURDATE())` → 2025 ❌ |
| is_published_month | 有 `=1` 过滤 | 无 ❌ |
| base_name IS NOT NULL | 有 | 无 |
| ORDER BY | 有 | 无 |
| answer 结果 | [] (0 rows — is_published_month=1 无匹配) | [{'base_name':None,'total':4782.7}] |

**归因**: sql_agent_issue + dataset_issue

- NQE 生成 `YEAR(CURDATE())` 硬编码当前年份 → 2025 年可能有数据，但 `is_published_month=1` 已被 LLM 丢弃
- answer_sql 返回 0 rows — `is_published_month=1 AND base_name IS NOT NULL` 两条过滤组合后无数据
- NQE 返回 1 row — `base_name=NULL` 被汇总为单组

**修复建议**:
1. dataset: answer_sql 去掉 `is_published_month=1` 或改为 `is_published_month<=12`（当前无 published 数据）
2. NQE: YEAR(CURDATE()) → 根据用户问题语义判断（无显式年份应默认全量或上一完整年）

---

## 4. NQE-pw-48e46411 → runner_comparison_issue + dataset_issue

question: 玻璃配置的因子选项

| 项目 | answer_sql | NQE SQL |
|---|---|---|
| SQL | `SELECT option_label,effect_value FROM plan_power_factor_option WHERE factor_key = 'glass'` | `SELECT factor_key, option_label, effect_value FROM plan_power_factor_option WHERE factor_key = 'glass'` |
| 差异 | 无 factor_key 列 | 有 factor_key 列 |
| rows | 131 | 131 ✅ |
| answer 结果 | `[{'option_label':'单镀+镀釉','effect_value':0.0},...]` | `[{'factor_key':'glass','option_label':'单镀+镀釉','effect_value':0.0},...]` |

**归因**: runner_comparison_issue（dimension_key_mismatch）

- expected_dimensions = `['supplier_name','power_bin','factor_key']` — 这三个维度与 glass 因子选项查询无关！
- 实际是 factor_option 查询，维度应是 `factor_key` 或空
- 执行器退化为取前 2 列做 key：answer 取 `('单镀+镀釉','0.000000')`，NQE 取 `('glass','单镀+镀釉')`
- 第一列为 `''` vs `'glass'` → dimension_key_mismatch

**修复建议**: dataset expected_dimensions 改为 `["factor_key"]` 或 `[]`。runner 无 bug，仅是 dataset 字段不匹配。

---

## 5. NQE-pw-16cbd97d → power_engine_issue

question: 功率分布预测

| 项目 | 值 |
|---|---|
| expected_result_source | PowerPredictionEngine |
| NQE generated_sql | (空) |
| actual_status | completed |
| actual_rows | 0 |
| fallback_used | False |

**归因**: power_engine_issue + power_prediction category routing

- 用户在问题"功率分布预测"中没有提供 model_code / configuration / supplier_name
- NQE graph 跳过了 SQL generation，直接返回 `completed`（可能是通过 adapter 或 domain routing）
- 但没有 `engine_called` / `power_prediction_result` 标记

**修复建议**: 
1. 修改 PowerPredictionEngine 调用后写 `power_prediction_result=true` 或 `engine_called=true`
2. 或修改 runner 检测 `_nqe_retrieval_assets` 中的 power 相关字段
3. dataset 考虑将缺少参数的 PowerPredictionEngine case 改为 `expected_status=clarify_required`

---

## 归因统计

| case_id | 归因 | 应修 |
|---|---|---|
| NQE-logi-41fe3a7a | dataset + SQL Agent | dataset(expected_tables) + NQE(prompt 表优先级) |
| NQE-logi-14ff867b | dataset + SQL Agent | dataset(total_fee 确认) + NQE 同 case1 |
| NQE-ba-c5720646 | SQL Agent | NQE(YEAR(CURDATE()) timing) + dataset(is_published_month) |
| NQE-pw-48e46411 | runner comparison | dataset(expected_dimensions) |
| NQE-pw-16cbd97d | power engine | engine_called 标记 |

## 修复优先级

| 优先级 | 任务 | 预计效果 |
|---|---|---|
| P1 | dataset expected_dimensions (pw-48e46411) | +1 pass |
| P2 | dataset is_published_month 调整 (ba-c5720646) | +1 pass |
| P2 | NQE YEAR(CURDATE()) 修正 | +1 pass |
| P3 | NQE 表优先级引导 (logistics 2 failures) | +2 pass |
| P3 | PowerPredictionEngine engine_called 标记 | +1 pass |

## 下一步

当前 smoke 14/20 → 预期修复后 18~19/20。
