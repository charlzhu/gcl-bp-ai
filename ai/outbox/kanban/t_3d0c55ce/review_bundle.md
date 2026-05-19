# t_3d0c55ce Review Bundle

## 任务范围

本任务只收敛 gcl-bp-ai 物流 NL2SQL M9 live provider shadow gate 中 `yearly_mw_breakdown` 的 provider 漂移问题，并修复两轮独立 review 指出的 fail-closed 漏洞。

允许范围：

1. `backend/app/domains/logistics/services/nl2sql/m9_sqlplan_generation.py`
   - 在 SQLPlan 生成层增加窄口径预校验归一化。
   - 仅处理显式年份问题误带 `default_time_range` 与无 join 多表噪声。
   - 只在 `tables` 是有效字符串列表、`joins` 明确为空、所有引用字段形态可验证且从 canonical catalog 解析到同一张表时，才允许单表收敛。
   - `joins` 非空/结构化/异常、`tables` 非字符串项、`filters/order_by` malformed/空白/未知/多引用等都保持原样交给 schema/validator fail-closed。
2. `tests/unit/logistics/nl2sql/test_m9_sqlplan_generation.py`
   - 增加 provider drift 复现测试。
   - 增加 review blocker RED/GREEN 测试：结构化非空 joins、tables 非字符串项、malformed/unknown filters、malformed/unknown/multi-ref order_by 不得被归一化清理。
3. `ai/outbox/kanban/t_3d0c55ce/`
   - 保存调查、RED/GREEN、测试、provider/reindex/live gate、静态扫描、review 与验收材料。
4. `ai/outbox/kanban/t_m9_nl2sql_shadow/m9-shadow-sqlplan-generation-records.jsonl`
   - 历史 live gate 记录证据文件已被前序 live gate 刷新。

禁止范围：

- 不修改物流生产 QA 主链路。
- 不进入 M10 或 live takeover。
- 不扩展 BOM、功率预测、物管、经营分析等业务域。
- 不放宽 SQLPlan validator；只在 generator 进入 validator 前做可证明安全的窄归一化。
- 不新增密钥、连接串或真实账号信息。

## 当前验证（第三轮修复后刷新）

| 验证项 | 当前结果 | 证据 |
| --- | --- | --- |
| 第三轮 RED | PASS：修复前 `2 failed`，证明 malformed filters/order_by 用例能捕获问题 | `red-review-round3-tests.log` |
| 第三轮 GREEN | PASS：`2 passed in 0.21s` | `green-review-round3-tests.log` |
| M9 SQLPlan 单测 | PASS：`26 passed in 1.57s` | `test-m9-sqlplan-generation.log` |
| compile | PASS：`compileall -q` 退出码 0，日志为空 | `compile.log` |
| fake shadow gate | PASS：`total=3 success=2 validation_failed=1 expected_status_mismatch=0` | `fake-shadow-gate.log`、`fake-shadow/m9-shadow-sqlplan-generation-report.md` |
| static scan | PASS：`finding_count=0` | `static-scan.log` |
| task patch | 1168 行 | `diff.patch` |
| provider smoke | BLOCKED：embedding/LLM connection error，rerank SSL EOF；Milvus PASS | `provider-smoke.log`、`provider-smoke-retry1.log` |
| catalog reindex | BLOCKED：`index_error::embedding_error::Connection error.` | `catalog-reindex.log` |
| live provider shadow gate | 本轮未刷新：provider/reindex 被外部连接阻塞；前序修复中曾 2/2 成功，但当前验收不能用旧证据宣称 complete | `live-provider-shadow-gate.log`（旧证据，仅作参考） |

## fake shadow 覆盖样例

1. `m9_success_carrier_mw_ranking_default_years`：success，validation ok。
2. `m9_success_yearly_mw_breakdown`：success，validation ok。
3. `m9_guard_tonnage_fail_closed`：validation_failed，rewrite stage，符合预期。

## 独立 review 历史与处理

### 第一轮 review

阻塞项：

1. 结构化非空 `joins` 被 `_string_items` 当作空 join，可能导致 tables 被收敛。
2. `tables` 含非字符串项时，`_dedupe_string_items` 会在归一化前丢弃异常项。

处理：

- 增加 RED/GREEN 测试。
- 单表归一化入口改为严格类型守卫。

### 第二轮 review

阻塞项：

1. `filters/order_by` 使用 `plan.get(...) or []`，会把 `{}`、空串、False 等 falsy malformed 字段当作空列表处理。
2. filter/order_by item 缺失、空白、未知或多引用场景覆盖不足。

处理：

- 增加第三轮 RED/GREEN 测试覆盖 malformed/unknown filters 与 malformed/unknown/multi-ref order_by。
- 将 filters/order_by 解析改为显式区分缺省/None/空 list 与 malformed；引用必须是非空字符串；order_by 必须且只能有一个有效 metric 或 dimension。

## Review 重点

请重点审查：

1. `_should_drop_default_time_rule_for_explicit_years` 是否足够窄：
   - 必须有显式年份。
   - plan filters 中必须存在非默认全集年份。
   - `explicit_year_buckets` 必须可解析且与 filter 年份完全一致。
2. `_normalize_single_table_plan_tables` 是否 fail-closed：
   - 只有无 join、多表、所有 metric/dimension/filter/group/order 引用都能从 canonical catalog 解析到同一张已存在表时，才收敛 `tables`。
   - `joins` 非空或非预期形态必须保持原样。
   - `tables` 含非字符串/空字符串等异常项必须保持原样。
   - `filters/order_by` malformed、空白引用、未知引用、多引用必须保持原样。
3. 是否放宽 SQLPlan validator、是否越权进入 M10/live takeover/其他业务域。
4. 是否存在密钥泄露、SQL 注入、shell 注入、eval/exec、pickle 等安全问题。
5. 任务材料是否只包含当前任务范围。

## 已知说明

- 当前工作区存在 `.worktrees/` 未跟踪目录，非本任务范围，未纳入 `diff.patch`。
- 当前最终状态不能标记 complete：provider smoke/reindex/live provider gate 被外部 provider 连接阻塞，需要 provider 恢复后重跑。
- 本次未 commit、未 push、未 deploy。
