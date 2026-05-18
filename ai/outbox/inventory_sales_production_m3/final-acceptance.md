# 产销存智能问答 M3 验收说明

完成时间：2026-05-18 13:12:05 CST

## 1. 本轮目标

本轮完成经营分析 / 产销存子域的 QueryPlan / 查询执行器 / 聚合策略 MVP。

边界：

- 不接入前端。
- 不接入最终智能助手路由。
- 不让 LLM 生成 SQL 或计算业务数字。
- 不修改物流、计划 BOM、功率预测链路。
- 不新增管理 token 或临时权限口。

## 2. 已完成能力

1. 新增产销存受控 QueryPlan Schema。
2. 新增 QueryPlan 校验与聚合策略选择器。
3. 新增固定 ORM 查询仓储，不接收自由 SQL。
4. 新增 QueryExecutor，支持以下 MVP query_key：
   - `ba_isp_metric_summary`
   - `ba_isp_metric_breakdown`
   - `ba_isp_metric_trend`
   - `ba_isp_budget_achievement`
   - `ba_isp_inventory_snapshot`
   - `ba_isp_period_compare`
5. 支持流量指标 `flow_sum`：产量、发货/销量、预算按已发布月份求和。
6. 支持时点指标 `period_end`：库存/存货/寄存取最后已发布月份，不累加。
7. 支持预算达成率 `calculated_ratio`：由后端按实际产量 / 预算重算。
8. 支持 2026 未发布月份 fail closed，不把空值/隐藏列/未来月份当 0。
9. 支持 2023 年度按月度事实重算策略提醒。
10. 支持 2024 销量默认切到“组件事业部剔除内部交易”的对外销量口径。
11. 支持指标、维度、过滤条件、开票口径显式触发等白名单校验。
12. 返回业务化摘要，不暴露 SQL、表名、planner、guardrail 等技术实现给用户。

## 3. 修改文件清单

- `backend/app/domains/business_analysis/repositories/__init__.py`
- `backend/app/domains/business_analysis/repositories/inventory_sales_production_query_repository.py`
- `backend/app/domains/business_analysis/schemas/__init__.py`
- `backend/app/domains/business_analysis/schemas/inventory_sales_production_query.py`
- `backend/app/domains/business_analysis/services/inventory_sales_production/aggregation_policy.py`
- `backend/app/domains/business_analysis/services/inventory_sales_production/query_executor.py`
- `tests/unit/business_analysis/test_inventory_sales_production_m3_query_executor.py`

## 4. 测试结果

完整组合测试：`41 passed in 0.72s`

覆盖范围：

- M3 focused：QueryPlan / QueryExecutor / 聚合策略单元测试 8 条。
- M2 相邻回归：产销存 Excel fact import 5 条。
- Query Planning 相邻回归 14 条。
- 物流 Query Planner V2 相邻回归 14 条。

日志文件：

- `ai/outbox/inventory_sales_production_m3/test.log`
- `ai/outbox/inventory_sales_production_m3/static-scan.log`

## 5. 静态检查

- `compileall` 通过。
- 常见凭证、私钥和连接串关键字扫描未发现真实敏感信息。
- 未恢复或新增功率模型临时管理 token。

## 6. 风险与未解决问题

1. M3 仍是后端 QueryPlan 执行 MVP，尚未接入智能助手入口和前端展示。
2. `ba_isp_period_compare` 当前作为受控 query_key 纳入白名单，但复杂同比/环比展示建议在 M4/M5 继续细化。
3. 当前预算达成率 MVP 不支持按维度拆分，后续需要结合预算数据维度完整性再开放。
4. 用户自然语言到 QueryPlan 的生成还未接入统一 NL2SQL，目前 M3 只提供可执行后端合同。

## 7. 对既有能力影响

- 不影响物流能力。
- 不影响计划 BOM 能力。
- 不影响功率预测能力。
- 不影响现有前端构建链路。

## 8. 建议下一步

M4：接入产销存智能问答入口，完成自然语言问题到受控 QueryPlan 的适配，并对用户可见回答做业务化流式展示。