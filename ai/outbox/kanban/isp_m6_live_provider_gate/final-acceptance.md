# 产销存 M6 live provider shadow gate 最终验收说明

## 1. 当前结论

本轮 `isp-m6-review-handoff` 返工与复验已完成，`isp-m6-verify` 门禁全部通过：

- 产销存 M6：provider smoke、catalog reindex dry-run、真实 live provider SQLPlan shadow gate 均通过。
- 真实 live provider 已被调用，SQLPlan validator 通过 1/1，只读中间库 shadow 已执行，预期状态不匹配为 0。
- 产销存、物流、计划 BOM / 功率 focused 回归均通过。
- scoped compile 与 static scan 均通过，static scan finding_count 为 0。
- M6 仍保持 shadow-only 阶段边界，不接管正式 QA，不写正式业务库，不修改 `.env`。

## 2. 修改文件清单

### 代码与测试

1. `backend/app/domains/business_analysis/services/inventory_sales_production/m6_live_provider_gate.py`
2. `scripts/dev/run_inventory_sales_production_m6_live_provider_gate.py`
3. `tests/unit/business_analysis/test_inventory_sales_production_m6_live_provider_gate.py`
4. `backend/app/domains/logistics/services/business_entity_resolver.py`
5. `backend/app/domains/logistics/services/data_qa_planner.py`
6. `tests/business_acceptance/test_logistics_carrier_filter_scope.py`

### 验收材料

1. `ai/outbox/kanban/isp_m6_live_provider_gate/test.log`
2. `ai/outbox/kanban/isp_m6_live_provider_gate/static-scan.log`
3. `ai/outbox/kanban/isp_m6_live_provider_gate/m6-live-provider-shadow-report.json`
4. `ai/outbox/kanban/isp_m6_live_provider_gate/m6-live-provider-shadow-records.jsonl`
5. `ai/outbox/kanban/isp_m6_live_provider_gate/diff.patch`
6. `ai/outbox/kanban/isp_m6_live_provider_gate/review_bundle.md`
7. `ai/outbox/kanban/isp_m6_live_provider_gate/review-result.json`
8. `ai/outbox/kanban/isp_m6_live_provider_gate/final-acceptance.md`

## 3. 关键改动说明

- 新增产销存 M6 live provider gate 服务：覆盖 catalog recall 文档构建、召回、真实 provider SQLPlan candidate 生成、SQLPlan validator、只读中间库 shadow 执行与脱敏摘要输出。
- 新增 M6 CLI：把 provider smoke、catalog reindex dry-run、live provider shadow gate 拆成显式门禁，避免把 M5 离线 shadow 或 provider smoke 误判为 M6 完成。
- 新增 M6 单测：覆盖 catalog 文档、依赖扩展、fail-closed、脱敏、CLI 行为、JSON object provider smoke 兼容、严格 SQLPlan candidate prompt 合同。
- 修复 provider/shadow 公开 reason fail-open 风险：未知外部异常默认映射为 `shadow_error_redacted`，只允许稳定公开枚举透出。
- 修复验收中暴露的物流回归：显式承运商短语支持“每年/按年/各年/年度/分别”等右边界；对年份范围后直接接承运商的短语做受控清洗；显式承运商 + 跨年逐年发运量题优先进入 `hist_mw_by_year`。

## 4. 测试与验证证据

证据文件：`ai/outbox/kanban/isp_m6_live_provider_gate/test.log`。

- 产销存相关单测/验收/前端域入口：`122 passed in 3.72s`
- 物流 focused 回归：`116 passed in 2.86s`
- 计划 BOM / 功率业务验收：`113 passed, 2 warnings in 13.49s`
- M6 provider smoke + catalog reindex dry-run + live provider shadow gate：`EXIT_CODE=0`
- scoped `py_compile`：`EXIT_CODE=0`

证据文件：`ai/outbox/kanban/isp_m6_live_provider_gate/static-scan.log`。

- finding_count: `0`
- status: `PASS`
- scope 覆盖本轮 6 个代码/测试文件

证据文件：`ai/outbox/kanban/isp_m6_live_provider_gate/m6-live-provider-shadow-report.json`。

- total: `1`
- provider_live_called: `true`
- sqlplan_validation_pass_count: `1`
- readonly_middle_db_shadow_executed: `true`
- expected_status_mismatch_count: `0`
- formal_qa_executed: `false`

## 5. 风险点

- 当前 live shadow gate 只跑 1 条安全样本，满足 M6 最小门禁；后续扩大样本前仍需保持 shadow-only，不应直接接管正式 QA。
- 真实 provider 输出仍可能受模型波动影响；本轮已用严格 prompt + validator fail-closed 控制风险，后续若扩大样本需继续补充失败样本回归。
- 计划 BOM / 功率测试存在 openpyxl warning，但不是本轮新增失败。

## 6. 当前仍未解决的问题

- M6 未把产销存 NL2SQL 接入正式用户问答链路；当前保持 shadow gate 阶段边界。
- M6 未扩大到全量 live 样本，也未启用自动同步/生产写入。
- M6 未修改物管/SAP Oracle/前端主体验入口。

## 7. 影响评估

- 对现有物流能力：已复跑物流 focused 回归 `116 passed`，并修复一个显式承运商跨年逐年问法回归。
- 对现有计划 BOM / 功率能力：已复跑 `113 passed, 2 warnings`，未发现新增失败。
- 对现有产销存能力：产销存相关测试 `122 passed`，M6 live gate 通过。
- 对用户可见回答：M6 仍为 shadow-only，不改变正式用户回答路径，不暴露内部技术细节。

## 8. 独立 review 结论

证据文件：`ai/outbox/kanban/isp_m6_live_provider_gate/review-result.json`。

- passed: `true`
- security_concerns: `[]`
- logic_errors: `[]`
- 非阻断建议：后续可进一步强化 provider smoke dict 状态默认 fail-closed、live shadow 异常状态审计、测试路径可移植性。

## 9. 阶段边界与提交状态

- 已遵守 M6 阶段边界：只做 live provider gate + 真实只读库 shadow 验证，不接管正式 QA。
- 未 push，未 deploy。
- 本文件写入时尚未本地 commit；待按 scoped 文件完成本地提交。
