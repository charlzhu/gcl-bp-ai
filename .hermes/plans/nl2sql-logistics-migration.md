# NL2SQL 物流一期改造执行计划

## 背景

用户已确认：第一阶段只做物流；业务问答只能查询智能助手 MySQL 中间库；禁止实时直查 SAP Oracle MID；允许 SELECT/EXPLAIN；允许引入 Milvus、百炼 Qwen3-Embedding-4B、Qwen3-Reranker、sqlglot；主 LLM 复用项目百炼 DeepSeek 配置；允许 shadow 记录 SQLPlan / SQL hash / EXPLAIN。物流口径新增确认：“件数”默认按 MW 回答；“今年 / 当前 / 最近”按系统当前年份；2023-2025 历史侧和 2026 系统侧所有维度允许跨源对比；空结果不放宽条件，只说明无数据并给改问建议；“报价 / 单价 / 运价”继续走 `unit_price_per_vehicle`，并与“均价 = SUM(total_fee)/SUM(shipment_trip_count)”严格区分。

## 已完成前置审查

- 已审查当前 Query Planning V2、物流 QA、Query Planner V2 现有代码。
- 已只读连接智能助手 MySQL 中间库，确认 MySQL 8.0.45、库 `logistics_ai`、总表 40 张、物流/日志相关表 20 张。
- 已确认核心表：`dws_logistics_detail_union`、`dws_logistics_monthly_metric`、`dwd_logistics_hist_shipment_detail`、`dwd_logistics_ship_task`、`dwd_logistics_ship_product`、`sys_query_log`。
- 已生成设计文档：`docs/NL2SQL_LOGISTICS_ARCHITECTURE_PLAN.md`。

## 当前仓库判断

### 可复用

1. `backend/app/domains/query_planning/` 已有统一 QueryPlan envelope、shadow 审计和报表。
2. `backend/app/domains/logistics/services/query_planner_v2/` 已有 planner/prompt/parser/normalizer/validator/capability/fallback 雏形。
3. 物流旧主链路已能作为 baseline 与 fallback。
4. `sys_query_log` 已有 31069 条，可做 shadow 与样例挖掘。

### 缺口

1. 缺 Semantic Catalog。
2. 缺 Milvus/Embedding/Rerank catalog 检索。
3. 缺 SQLPlan schema/validator。
4. 缺 SQL renderer/safety/explain/repair/execution 闭环。
5. 缺真实数据自动样例生成。

## 分阶段计划

### M1：Semantic Catalog MVP

目标：固化物流第一阶段可查表、字段、指标、维度、Join、规则、样例。

交付：

- `backend/app/domains/logistics/config/nl2sql_catalog/tables.yaml`
- `backend/app/domains/logistics/config/nl2sql_catalog/metrics.yaml`
- `backend/app/domains/logistics/config/nl2sql_catalog/dimensions.yaml`
- `backend/app/domains/logistics/config/nl2sql_catalog/joins.yaml`
- `backend/app/domains/logistics/config/nl2sql_catalog/rules.yaml`
- catalog loader + schema 单测

TDD 顺序：

1. RED：测试 `shipment_mw` 同义词默认映射到 `SUM(shipment_watt)`，单位 MW，并覆盖“件数”默认按 MW 回答。
2. RED：测试 `avg_fee_per_trip` 必须是 `SUM(total_fee)/SUM(shipment_trip_count)`。
3. RED：测试“报价 / 单价 / 运价”走 `unit_price_per_vehicle`，不走均价公式。
4. RED：测试吨数/运输吨位返回 unsupported 规则。
5. RED：测试无时间条件默认 2023-2026。
6. RED：测试“今年 / 当前 / 最近”按系统当前年份解释。
7. RED：测试 2023-2025 与 2026 混查时所有维度允许跨源对比。
8. RED：测试空结果不放宽条件，只返回无数据说明与改问建议。
9. GREEN：实现 catalog schema/loader。
10. REFACTOR：从 DB inspector 生成 `tables.yaml` 初稿。

### M2：Catalog 召回与 Rerank

目标：使用 Milvus + Qwen3 embedding/rerank 召回 catalog。

前置：用户正在搭建本地 Milvus；进入 M2 前需重新执行连接 smoke test，并核对 `.env` 中 Milvus URI / host / port 配置。

交付：

- embedding client
- rerank client
- Milvus collection 管理
- catalog index/reindex 脚本
- 检索/Rerank 单测

### M3：SQLPlan

目标：LLM/后端生成结构化 SQLPlan，暂不生成正式 SQL。

交付：

- `backend/app/domains/query_planning/schemas/nl2sql.py`
- SQLPlan generator
- SQLPlan validator
- shadow logger

### M4：SQL 渲染与安全

目标：从 SQLPlan deterministic render SQL，并用 sqlglot + 自定义规则拦截危险 SQL。

交付：

- sql renderer
- sql safety validator
- 参数绑定
- 安全测试矩阵

### M5：EXPLAIN / 试执行 / 自修复 shadow

目标：完整跑通 shadow 闭环，不改变正式答案。

交付：

- EXPLAIN runner
- trial executor
- repairer（最多 2 轮）
- `sys_query_log.request_payload.nl2sql_shadow`
- 一致性报表

### M6：真实数据样例与标准答案

目标：从中间库自动生成物流问题样例与标准答案。

交付：

- example generator
- 标准答案计算器
- regression fixture
- acceptance tests

### M7：小范围灰度接管

前提：核心 A 类一致率达标、安全违规 0、用户可见技术泄露 0。

## 已确认业务口径与剩余确认点

### 已确认

1. “件数”默认按 MW 回答，不启用 `shipment_count` 作为默认口径。
2. “今年 / 当前 / 最近”按系统当前年份解释。
3. 2023-2025 历史侧与 2026 系统侧混合查询时，所有维度允许跨源对比。
4. 空结果不放宽条件，只说明无数据并给改问建议。
5. “报价 / 单价 / 运价”走 `unit_price_per_vehicle`，并与“均价 = SUM(total_fee)/SUM(shipment_trip_count)”严格区分。

### 剩余确认点

暂无。

## 下一步

进入 M1：按 TDD 创建 Semantic Catalog MVP。严格不改 `data_qa_planner.py` 主逻辑，不接前端，不查 SAP Oracle MID。
