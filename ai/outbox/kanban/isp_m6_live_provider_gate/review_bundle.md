# 产销存 M6 live provider shadow gate review bundle

## 任务范围

- 阶段：经营分析域 / 产销存 M6。
- 目标：新增并验证 M6 provider smoke、catalog recall/reindex、真实 LLM SQLPlan candidate 生成、本地 SQLPlan validator、只读中间库 live shadow gate 与公开摘要脱敏能力。
- 补充回归修复：验收复跑中发现物流“显式承运商 + 跨年逐年发运量”相邻问法问题，已做最小通用修复并纳入物流 focused 回归。
- Reviewer 返工：公开 provider/shadow reason 已从“已知敏感词替换后回显”改为默认 fail-closed，只允许稳定公开枚举，未知异常统一为 `shadow_error_redacted`。
- 边界：不接管正式 QA，不写正式业务库，不修改 `.env`，不输出密钥/连接串，不扩展物管/SAP Oracle/前端/计划 BOM 主链路。

## 本次变更文件

### 代码与测试

1. `backend/app/domains/business_analysis/services/inventory_sales_production/m6_live_provider_gate.py`
2. `scripts/dev/run_inventory_sales_production_m6_live_provider_gate.py`
3. `tests/unit/business_analysis/test_inventory_sales_production_m6_live_provider_gate.py`
4. `backend/app/domains/logistics/services/business_entity_resolver.py`
5. `backend/app/domains/logistics/services/data_qa_planner.py`
6. `tests/business_acceptance/test_logistics_carrier_filter_scope.py`

### 验收材料

- `ai/outbox/kanban/isp_m6_live_provider_gate/test.log`
- `ai/outbox/kanban/isp_m6_live_provider_gate/static-scan.log`
- `ai/outbox/kanban/isp_m6_live_provider_gate/m6-live-provider-shadow-report.json`
- `ai/outbox/kanban/isp_m6_live_provider_gate/m6-live-provider-shadow-records.jsonl`
- `ai/outbox/kanban/isp_m6_live_provider_gate/diff.patch`
- `ai/outbox/kanban/isp_m6_live_provider_gate/review_bundle.md`
- `ai/outbox/kanban/isp_m6_live_provider_gate/review-result.json`
- `ai/outbox/kanban/isp_m6_live_provider_gate/final-acceptance.md`

## 最新验证结果

证据文件位于：`ai/outbox/kanban/isp_m6_live_provider_gate/`。

- `test.log`
  - 产销存相关单测/验收/前端域入口：`122 passed in 3.72s`
  - 物流 focused 回归：`116 passed in 2.86s`
  - 计划 BOM / 功率业务验收：`113 passed, 2 warnings in 13.49s`（openpyxl 兼容 warning，非本轮新增失败）
  - M6 provider smoke + catalog reindex dry-run + live shadow gate：`EXIT_CODE=0`
  - scoped `py_compile`：`EXIT_CODE=0`
- `static-scan.log`
  - finding_count: `0`
  - status: `PASS`
  - scope 覆盖本轮 6 个代码/测试文件
  - 规则：硬编码密钥赋值、shell 注入、eval/exec、pickle、SQL 字符串拼接
- `m6-live-provider-shadow-report.json`
  - total: `1`
  - provider_live_called: `true`
  - sqlplan_validation_pass_count: `1`
  - readonly_middle_db_shadow_executed: `true`
  - expected_status_mismatch_count: `0`
  - formal_qa_executed: `false`（M6 shadow gate 边界，不接管正式 QA）
- `diff.patch`
  - 包含本任务 6 个代码/测试文件的 scoped diff，其中 3 个为产销存 M6 新文件，3 个为物流跨域回归最小修复/测试。

## TDD / 返工记录

1. 先确认 M5/M5-6 离线 shadow 基线通过，但不能代表 M6 live gate。
2. 新增 M6 provider/reindex/live shadow gate 能力与单测。
3. 第一次完整复跑暴露 provider smoke 兼容问题：OpenAI 兼容接口要求 JSON object 响应格式下提示词显式包含 JSON 字样；已补测试并修复 CLI smoke prompt。
4. 第二次 live gate 暴露真实 LLM 返回了自定义 candidate 结构；validator 正确 fail-closed。已补严格 SQLPlan candidate 合同 prompt 与测试，不放宽 validator。
5. 独立 review 指出公开异常 reason fail-open：已先补 RED 用例 `test_m6_provider_smoke_redacts_plain_unknown_exception_text_by_default`，确认未知外部异常原样回显；随后修复 `_safe_public_reason` 为默认 fail-closed，并复跑 M6 单测 GREEN。
6. 跨域物流 focused 复跑暴露“23年-25年苏州晶茂物流按年份发运量是多少”落入总量 summary；定位为承运商显式抽取未处理年份范围后直接接承运商，以及逐年分支优先级不足；已补测试和最小通用修复。
7. 最终复跑：产销存、物流、计划 BOM/功率、compile、static scan、live gate 均通过。

## 审查重点

请重点审查：

1. M6 live-provider shadow gate 是否与 provider smoke / catalog reindex 明确分离。
2. 真实 provider 输出是否只能进入 SQLPlan validator；validator 是否 fail-closed，且没有自由 SQL 执行路径。
3. Catalog refs 是否只基于本地 canonical catalog/召回依赖扩展；不允许 LLM 反向发明或扩大引用。
4. 公开摘要/记录是否脱敏：不得泄露密钥、连接串、provider、debug/raw、SQL 片段或内部技术细节；未知 provider/shadow 异常必须默认 `shadow_error_redacted`。
5. CLI 默认是否保持 shadow 验证边界：不接管正式 QA、不写正式库、不修改 `.env`。
6. 物流回归修复是否为最小通用修复，且不破坏既有物流主链路。
7. 测试是否覆盖正向、fail-closed、脱敏、CLI 行为和跨域回归。

## 当前工作区说明

当前分支：`feature/isp-m6-live-provider-shadow-gate`。

review 请只审查上述文件与 scoped `diff.patch`，不要扩大到项目其他历史文件。`tmp/hermes/` 下脚本为本地验收辅助，不纳入提交范围。
