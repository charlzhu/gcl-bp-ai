# Codex 任务：修复物流城市总费用排名 TopN 问法不一致

## 背景
用户反馈：
- “2024年江苏省各城市总费用排名前五？” 智能助手能回答。
- “2025年江苏省各城市总费用排名前十？” 却进入澄清。

已复现：`LogisticsDataQaPlanner().build_plan()` 对“前五”返回 `hist_total_fee_city_rank`，但对“前十/前10”返回 clarification。
根因初判：`backend/app/domains/logistics/services/data_qa_planner.py` 中城市总费用排名分支写死了字面量 `各城市总费用排名前五` 和 `limit=5`。

## 当前 RED 测试
我已经新增并确认失败：
```bash
PYTHONPATH=. python -m pytest tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_hist_city_total_fee_rank_supports_variable_top_n -q
```
失败点：`2025年江苏省各城市总费用排名前十？` 的 `plan.query_key is None`。

## 允许修改范围
只允许修改：
1. `backend/app/domains/logistics/services/data_qa_planner.py`
2. `tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py`（如必须微调测试，但不要削弱断言）

禁止修改 Plan Power / 前端 / 配置 / 数据库迁移 / `.env` / 密钥 / 其他业务域。
禁止 commit / push / deploy / merge。
当前工作树有其他未提交改动，必须只做本任务最小增量，不能 reset/clean/checkout。

## 需求口径
1. 对“YYYY年<省份>各城市总费用排名前N？”这一类明确问题，应稳定进入：
   - `query_key="hist_total_fee_city_rank"`
   - `metrics=["total_fee"]`
   - `dimensions=["city"]`
   - `filters={"year": YYYY, "province": <省份>}`
   - `group_by=["city"]`
   - `sort=[{"field": "total_fee", "direction": "desc"}]`
   - `limit=N`
2. 必须支持至少：`前五`、`前十`、`前10`。
3. 不要为了这个 case 写死 2025/江苏；应基于已有年份、省份抽取逻辑通用处理。
4. 不要扩大到模糊问题；必须要求 year 和 province 都存在，并且问题包含城市维度、总费用指标、排名/前N意图。
5. 中文注释说明函数功能、参数、返回值和业务边界。
6. 如涉及 LLM guardrail candidate 回构，也要避免仍然固定 `limit=5`。

## 验收命令
请完成后运行：
```bash
PYTHONPATH=. python -m pytest tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_hist_city_total_fee_rank_supports_variable_top_n -q
PYTHONPATH=. python -m pytest tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py -q
python -m compileall -q backend/app/domains/logistics/services/data_qa_planner.py
```

输出你修改了什么、为什么，以及测试结果。