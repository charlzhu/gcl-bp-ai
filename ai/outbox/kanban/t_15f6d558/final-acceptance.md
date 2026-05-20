# M10-C final acceptance

## 任务

物流 NL2SQL M10-C：live-provider shadow 接入正式 QA 旁路。

## 当前仓库完成能力判断

已完成：

1. M10-A candidate SQL 安全门禁能力已在当前 `agent/bp-main` 基线中存在。
2. M10-B shadow pipeline 能力已在当前 `agent/bp-main` 基线中存在。
3. 本轮新增 M10-C：正式物流 QA 历史写入旁路可选运行 NL2SQL live-provider shadow。
4. 默认关闭：未开启时不会实例化 recall / generator / pipeline provider 依赖。
5. 显式开启后仅旁路运行：query rewrite -> domain route -> catalog recall -> SQLPlan generator -> M10-B shadow pipeline。
6. raw candidate SQL 只进入 M10-B candidate SQL gate 审计，不执行、不写入用户可见回答。
7. 正式 `LogisticsDataQaResult` 不被修改；只把脱敏 `nl2sql_live_shadow` 摘要写入服务端查询历史 `response_meta`。
8. Adapter/provider/pipeline 异常 fail-closed，不中断正式 QA 和历史写入。
9. live-shadow error metadata 已按独立 review 要求修补：error code 固定白名单化，error message 泛化，不暴露表/字段/provider/debug 细节。

未完成 / 不在本轮范围：

1. 未把 NL2SQL 接管为正式用户回答来源。
2. 未开启默认 live shadow 环境变量。
3. 未做真实 provider / MySQL smoke；如需进入 M10-D 或灰度，需要另起任务并确认环境。
4. 未改前端展示。
5. 未改物管、计划 BOM、经营分析、M5 产销存等其它业务线。

## 允许修改范围执行情况

已修改：

1. `backend/app/domains/logistics/services/nl2sql/live_shadow_adapter.py`
2. `backend/app/domains/logistics/services/data_qa_service.py`
3. `tests/unit/logistics/nl2sql/test_m10c_live_shadow_adapter.py`
4. `ai/outbox/kanban/t_15f6d558/` 验收材料

未修改：

1. frontend
2. material_management / SAP MID / Oracle
3. plan_bom / plan_power
4. business_analysis / M5 产销存
5. `.env` / 密钥配置
6. 数据库迁移

## 测试方法与结果

详见：`ai/outbox/kanban/t_15f6d558/test.log`

1. `python -m pytest tests/unit/logistics/nl2sql/test_m10c_live_shadow_adapter.py -q`
   - 6 passed
2. `python -m pytest tests/unit/logistics/nl2sql/test_candidate_sql_gate.py tests/unit/logistics/nl2sql/test_shadow_pipeline.py tests/unit/logistics/nl2sql/test_m9_sqlplan_generation.py tests/unit/logistics/nl2sql/test_m10c_live_shadow_adapter.py -q`
   - 72 passed
3. `python -m pytest tests/unit/logistics/nl2sql -q`
   - 226 passed, 9 dependency warnings
4. `python -m pytest tests/unit/query_planning/test_query_planning_phase5_shadow_compare.py tests/unit/query_planning/test_query_planning_phase5_gray_log_report.py tests/business_acceptance/test_logistics_field_scope_clarification.py -q`
   - 15 passed
5. `python -m compileall backend/app/domains/logistics/services/nl2sql -q`
   - passed
6. `git diff --check`
   - passed

## Review

详见：`ai/outbox/kanban/t_15f6d558/review.json`

结论：passed=true。

reviewer 可选建议：未来可把注入 adapter 的返回值再次通过 `LogisticsNl2SqlLiveShadowSummary` validate 后写入历史，以进一步增强依赖注入边界。本轮实现已经在异常 fallback 中 fail-closed，reviewer 未判定为阻断。

## 风险点

1. M10-C 当前仍是旁路 shadow，不是正式接管；开启环境变量后会调用 live-provider 相关依赖，应单独做 provider smoke 和灰度审计。
2. 查询历史 metadata 可能被前端读取，因此本轮已强制把 error metadata 业务安全化；后续若新增字段必须继续遵守同等脱敏规则。
3. 旧 M8 shadow eval artifact 会被部分测试写脏；本轮已两次精确恢复该无关文件，最终未纳入 M10-C diff。

## 当前仍未解决的问题

1. 未执行真实只读库 live smoke。
2. 未定义 M10-D / 灰度开启策略。
3. 未提交、未合入 `agent/bp-main`，等待人工确认 diff 后再执行。

## 是否影响既有能力

1. 物流问答：默认关闭，不改变用户回答；相关回归通过。
2. 计划 BOM：未修改。
3. 功率预测：未修改。
4. 物管 / 经营分析：未修改。
5. 前端：未修改。

## 阶段边界

已遵守：本轮只做物流 NL2SQL M10-C 旁路 shadow 接入；未进入 live takeover、未自动开启 provider、未扩展其它业务域。

## 提交/发布状态

1. 未 commit。
2. 未 push。
3. 未 deploy。
4. 未 merge。
