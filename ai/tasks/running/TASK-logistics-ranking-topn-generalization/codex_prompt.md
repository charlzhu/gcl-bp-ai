# Codex 任务：物流问答排名 TopN 写死泛化修复

## 背景
用户反馈“各城市总费用排名前五”能回答，“前十”被澄清。已修过城市总费用 TopN，但用户进一步要求检查同类写死，凡是同类“前五/前十/前20/limit 固定”导致同一问题只换 TopN 就不能问的情况，都要改成灵活处理。

## 当前 RED 测试
已新增并确认 RED：
```bash
PYTHONPATH=. python -m pytest \
  tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_hist_city_total_fee_rank_supports_variable_top_n \
  tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_logistics_ranking_branches_parse_variable_top_n \
  tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_logistics_ranking_variable_top_n_does_not_drop_extra_dimensions \
  -q
```
当前失败点包括：
- `2025年江苏省各城市总费用排名前十一？` 未命中 `hist_total_fee_city_rank`。
- `2025年各承运商总运费排名前五？` 被误落到 `hist_carrier_kpi_by_year`，没有进入 `carrier_metric_ranking`。

## 允许修改范围
只允许修改：
1. `backend/app/domains/logistics/services/data_qa_planner.py`
2. `backend/app/domains/logistics/services/data_qa_service.py`（仅当 summary 文案需要动态 TopN）
3. `tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py`

不要修改数据库、前端、Plan BOM、配置、其它测试。不要 commit/push/deploy。

## 目标
1. 增加通用正整数 TopN 解析能力，支持：
   - `前5/前10/前20`
   - `前五/前十/前十一/前二十`
   - 可合理兼容 `Top5/top10/TOP20`（若低风险）
2. 将以下同类排名分支从写死改为从问句解析 TopN：
   - `hist_total_fee_city_rank`
   - `carrier_metric_ranking`
   - `sys_task_count_ranking`（送达城市 / project_name）
   - `sys_task_status_province_ranking`
   - `sys_driver_task_ranking`
   - `hist_top_customers_fee_and_mw_by_province`
   - `hist_customer_mw_ranking`
   - 若发现相同低风险分支也可一起修，但必须有测试或保持最小改动。
3. `carrier_metric_ranking` 需要把“总费用排名”也识别为 `total_fee`，不要只认“总运费”。
4. 保持 fail-closed：不能吞掉额外维度/额外指标/反向排序，例如：
   - `按区域拆分`
   - `按承运商拆分`
   - `最低/倒数/升序`
   - 额外指标如“总发运量和总费用”超出单指标 query_key 时不能误路由。

## 注意
- 代码新增/修改要有中文注释或中文 docstring。
- 不能为了当前测试硬编码具体句子。
- 保留原本无 TopN 问法的业务默认，如“司机派车任务量最高”如果原来默认 top20，不要改成 top1，除非已有明确业务依据。
- 当前工作树很脏，禁止 reset/checkout/clean。

## 验证
完成后至少运行：
```bash
PYTHONPATH=. python -m pytest \
  tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_hist_city_total_fee_rank_supports_variable_top_n \
  tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_logistics_ranking_branches_parse_variable_top_n \
  tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_logistics_ranking_variable_top_n_does_not_drop_extra_dimensions \
  -q
PYTHONPATH=. python -m pytest tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py -q
```

请完成代码修改并在输出里说明修改点和测试结果。