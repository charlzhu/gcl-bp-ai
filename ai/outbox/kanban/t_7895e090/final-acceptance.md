# M8 Shadow Eval 最终验收说明

## 结论

M8 物流 NL2SQL shadow-only 样例评估能力已完成补齐、验证和独立复审。本次改动保持在物流 NL2SQL shadow/evaluation 层，不接正式物流 Data QA 主链路，不读取 `.env`，M8 runner 只使用 fake executor；M7 只读中间库 live smoke 回归仍可用。

## 修改范围

- `backend/app/domains/logistics/services/nl2sql/m8_shadow_eval.py`
  - 新增 M8 shadow-only 默认样例集与 runner。
  - 样例覆盖发运量、均价、总费用趋势、区域/运输方式拆分、承运商排名、始发地+客户明细 TopN。
  - 保留吨数/未知指标/报价单价范围/safety 写 SQL/缺 candidate/非 sql_direct 等 fail-closed 边界。
  - safety 负例使用专用 renderer 构造危险 SQL，但在 safety gate 停止，并记录 executor 调用前后计数证明不会触达 executor。
- `backend/app/domains/logistics/services/nl2sql/evaluation_report.py`
  - 增强报表：catalog 指标/维度/表覆盖、样例 category/business_case/metric_family、expected_status 匹配率、safety/executor 计数。
  - 保持默认关闭 catalog breakdown，M8 显式开启，避免扩大旧 M6/M7 报表暴露面。
- `backend/app/domains/logistics/services/nl2sql/m7_readonly_smoke.py`
  - 修复通用报表标题调整后 M7 Markdown 专属标题替换。
- `backend/app/domains/logistics/services/nl2sql/__init__.py`
  - 导出 M8 runner、样例与常量。
- `scripts/dev/run_logistics_nl2sql_m8_shadow_eval.py`
  - 新增固定脚本入口，stdout 只输出脱敏摘要。
- `tests/unit/logistics/nl2sql/test_m8_shadow_eval.py`
  - 新增 M8 样例覆盖、报表维度、脱敏、shadow-only 与 safety executor 未触达测试。
- `docs/NL2SQL_LOGISTICS_M8_SHADOW_EVAL_PLAN.md`
  - 补充 M8 shadow eval 范围、非范围与验收命令。

## 验证结果

详见 `ai/outbox/kanban/t_7895e090/test.log`：

- M8 focused：`3 passed`
- NL2SQL adjacent：`159 passed, 9 warnings`
- logistics unit：`173 passed, 9 warnings`
- full unit：`217 passed, 9 warnings`
- scoped compileall：通过
- `git diff --check`：通过
- M8 shadow-only runner：`total=12`，`success=6`，`validation_failed=3`，`safety_failed=1`，`skipped=1`，`unsupported=1`，`expected_status_match_rate=1.0`，`shadow_only=true`，`live_smoke_executed=false`
- M7 readonly live smoke：`environment_status=available`，`live_smoke_executed=true`，`total=2`，`success_rate=1.0`
- 项目 wrapper：`ai/scripts/run_tests.sh basic` 通过，前端 build 输出 `[Test] All checks passed`

## Review 结果

详见 `ai/outbox/kanban/t_7895e090/review-result.json`：

- `passed=true`
- `security_concerns=[]`
- `logic_errors=[]`
- 非阻断建议：后续可考虑让 M8 CLI 在 expected_status mismatch 时返回非 0，增强单独运行时的失败暴露。

## 安全与范围核对

- 未提交 `.env`、真实连接串、账号密码、API Key。
- `diff.patch` 静态扫描仅命中测试中的负向脱敏断言，不是真实密钥。
- 已恢复 `docs/HANDOFF.md` 中一行误写入的无关文本，该文件最终无 diff。
- `docs/PLATFORM_OVERALL_ARCHITECTURE_AND_ROADMAP.md` 属于非 M8 未跟踪文件，未纳入本次限定 patch/提交范围。

## 产物

- `ai/outbox/kanban/t_7895e090/diff.patch`
- `ai/outbox/kanban/t_7895e090/test.log`
- `ai/outbox/kanban/t_7895e090/review-result.json`
- `ai/outbox/kanban/t_7895e090/final-acceptance.md`
- `ai/outbox/kanban/t_7895e090/m8-shadow-eval-records.jsonl`
- `ai/outbox/kanban/t_7895e090/m8-shadow-eval-report.md`
- `ai/outbox/kanban/t_7895e090/m7-live-smoke-check/m7-shadow-smoke-records.jsonl`
- `ai/outbox/kanban/t_7895e090/m7-live-smoke-check/m7-shadow-smoke-report.md`

## 影响评估

- 不影响现有正式物流 QA 主链路。
- 不影响计划 BOM/功率能力。
- M7 live smoke 回归可用，M8 仅作为 shadow-only 离线评估入口。
