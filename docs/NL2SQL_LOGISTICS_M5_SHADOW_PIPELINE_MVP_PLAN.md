# NL2SQL 物流 M5 Shadow Pipeline + 评估日志 MVP 方案

## 1. 阶段目标

本阶段新增物流 NL2SQL 的内部 shadow pipeline 和 evaluation log MVP。该能力用于离线评估、回放和灰度前的质量统计，不接入正式物流 Data QA 主链路，不影响用户可见回答。

## 2. 本轮交付范围

新增内部模块：

- `backend/app/domains/logistics/services/nl2sql/evaluation_log.py`
- `backend/app/domains/logistics/services/nl2sql/shadow_pipeline.py`

新增单测：

- `tests/unit/logistics/nl2sql/test_evaluation_log.py`
- `tests/unit/logistics/nl2sql/test_shadow_pipeline.py`

更新包导出：

- `backend/app/domains/logistics/services/nl2sql/__init__.py`

## 3. Shadow Pipeline 边界

MVP 串联既有 M3/M4 组件：

1. 输入用户问题、可选改写问题、受控 `SQLPlan candidate`。
2. 仅接受 `domain=logistics` 与 `source_system=middle_db`。
3. 缺少 candidate 或非 `sql_direct` strategy 时只记录评估日志，不进入 SQL 阶段。
4. 调用 M3 `LogisticsSqlPlanValidator` 做确定性校验。
5. 调用 M4 `LogisticsSqlRenderer` 渲染参数化 SQL。
6. 调用 M4 `LogisticsSqlSafetyChecker` 做二次只读安全校验。
7. 调用 M4 `LogisticsSqlExecutionService` 做 EXPLAIN 与 trial。
8. 输出 `status/stage/error_codes/sql_hash/sql_param_keys/row_count/explain_ok/trial_ok/evaluation_log_record`。

该链路不返回 SQL 原文、不返回参数值、不读取 `.env`，默认使用 fake executor；如后续需要真实中间库 smoke，必须由调用方显式注入只读 executor。

## 4. Evaluation Log 设计

评估日志记录字段包括：

- `schema_version` / `pipeline_version`
- `trace_id` / `request_id`
- 脱敏后的 `question` / `rewritten_question`
- `domain` / `source_system`
- `status` / `stage` / `error_codes` / `error_message`
- `catalog_ids` / `catalog_versions`
- `sql_hash` / `sql_param_keys`
- `validation_errors` / `safety_errors`
- `explain_ok` / `trial_ok` / `row_count` / `sample_row_count`
- `duration_ms` / `warnings` / `created_at`

日志只保留 SQL hash 与参数 key，禁止持久化 SQL 原文、参数值、DSN、password、token、API key、Bearer token 等敏感内容；`sql_hash` 只接受 64 位十六进制哈希，误传 SQL/密钥文本时丢弃。该约束同时固化在 `LogisticsNl2SqlEvaluationLogRecord` 直接构造入口和 JSONL/内存 sink 写入入口，避免后续复用公共导出类时绕过 `from_pipeline()`。

## 5. Fail-closed 规则

- validation 失败：停止 render/safety/executor，写 `validation_failed` 日志。
- render 失败：停止 safety/executor，写 `render_failed` 日志。
- safety 失败：停止 executor，写 `safety_failed` 日志。
- explain 失败：不继续 trial，写 `explain_failed` 日志。
- trial 失败：写 `trial_failed` 日志。
- 日志 sink 写失败：不改变 shadow 主结果，只在结果中返回脱敏 `log_error`。

## 6. 后续扩展建议

1. 增加只读 DB executor 的受控 smoke 配置，但必须保持默认 fake/offline。
2. 增加 query rewrite / catalog recall / SQLPlan candidate provider 的 shadow wrapper，不接正式用户回答。
3. 基于 JSONL 或数据库离线表生成失败分类、错误码分布、SQLPlan 命中率和安全拦截率报表。
4. 在 M5 验证稳定后，再讨论是否进入灰度日志或正式主链路旁路观测。
