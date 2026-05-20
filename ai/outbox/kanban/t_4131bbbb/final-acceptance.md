# t_4131bbbb final acceptance

## 结论

M5-5 产销存 M5 shadow-only NL2SQL 接入收口、归档与提交准备已完成。最终通过依据明确为 `t_3ca95bf9` 与 `t_45ab3a93`，两者独立 review 均为 `passed=true`；`t_d76060c2` 与 `t_87762691` 仅作为历史过程证据，不作为最终通过依据。

## 修改/归档文件清单

本次计划提交范围：

- `backend/app/domains/business_analysis/services/inventory_sales_production/m5_shadow_compare.py`
- `scripts/dev/run_inventory_sales_production_m5_shadow_compare.py`
- `tests/unit/business_analysis/test_inventory_sales_production_m5_shadow_compare.py`
- `ai/outbox/kanban/t_3ca95bf9/**`
- `ai/outbox/kanban/t_45ab3a93/**`
- `ai/outbox/kanban/t_4131bbbb/**`

本次不提交：

- `frontend/tsconfig.tsbuildinfo`：已将 diff 保存为 `ai/outbox/kanban/t_4131bbbb/frontend-tsbuildinfo.diff`，确认是 TypeScript build cache 文件差异后已路径级还原。
- `ai/outbox/kanban/t_d76060c2/**`、`ai/outbox/kanban/t_87762691/**`：保留为本地历史过程证据，因其包含已修复 blocker 的历史失败材料，不作为最终通过证据纳入本次提交。

## 关键处理说明

- 产销存 M5 shadow compare 保持 shadow-only，只运行离线 QueryPlan / SQLPlan 对比与 validator，不执行正式 QA 主链路，不执行 live DB。
- 默认样例覆盖 M4-6 真实问法的成功、暂不支持、澄清与脱敏负例。
- 独立 SQLPlan fixture 与 QueryPlan 业务签名比较，避免 QueryPlan 自我生成候选后的虚假 matched。
- 期间语义与期间参数使用安全形状/不可逆指纹比较，不在持久化 artifact 中写出具体抽取年月参数。
- 当前收口报告写入 `ai/outbox/kanban/t_4131bbbb/m5-closeout-report.md`。

## 测试方法与结果

验收日志：`ai/outbox/kanban/t_4131bbbb/test.log`。

- M5 focused shadow compare：11 passed，exit 0。
- 产销存 M2/M3/M4/M4-6 regression：85 passed，exit 0。
- 物流 focused regression：22 passed，exit 0。
- 计划 BOM / 功率 focused regression：21 passed，exit 0。
- backend compileall：exit 0。
- M5 shadow compare dev runner：exit 0；total=11，matched=7，fail_closed_count=4，expected_status_mismatch_count=0，shadow_only=true，formal_qa_executed=false，live_db_executed=false。
- static scan：passed=true，findings=none。
- `git diff --check`：exit 0。

## Static scan 结果

静态扫描日志：`ai/outbox/kanban/t_4131bbbb/static-scan.log`。

结果：passed=true，findings=none。扫描范围覆盖 M5 shadow source、runner、focused tests、当前 M5 shadow records/report 与 test.log；测试中用于验证脱敏的 fixture 已按非生产持久化内容记录为 allowed fixture notes。

## 独立 review

独立 review 已完成并写入 `ai/outbox/kanban/t_4131bbbb/review-result.json`：

- passed=true
- security_concerns=[]
- logic_errors=[]
- suggestions 仅提示提交前必须 scoped staging 并运行 `git diff --cached --check`，以及提交后在验收/看板中记录最终 commit id。

## Commit id

本文件生成于提交前，commit id 需在实际提交后由 `git rev-parse HEAD` 读取，并在看板 handoff / 最终回复中记录。

## 当前 git status

提交前状态见 `ai/outbox/kanban/t_4131bbbb/test.log` 的 preflight 与 post-run git status；`frontend/tsconfig.tsbuildinfo` 已还原，不在当前 dirty 列表中。

## 风险点

- 当前仍为 shadow-only；不能把本轮 runner 或 SQLPlan candidate 结果误当作正式用户问答接管依据。
- 历史过程证据 `t_d76060c2` / `t_87762691` 曾包含 review blocker，最终验收口径必须以 `t_3ca95bf9` 与 `t_45ab3a93` 为准。
- 若后续进入产销存 NL2SQL shadow 扩样或 live provider gate，必须另开阶段卡并重新做 TDD、静态扫描与 review。

## 当前仍未解决的问题

- 未接入 live provider gate。
- 未让 NL2SQL 正式接管产销存用户可见 QA。
- 未执行 live DB。
- 未扩展到下一批产销存 shadow 样例。

## 对既有能力影响

- 物流：已跑 focused regression，22 passed；未修改物流主链路。
- 计划 BOM：已跑 focused regression，计划 BOM / 功率合计 21 passed；未修改计划 BOM 主链路。
- 功率预测：已跑 focused regression，未修改功率预测主链路。

## 阶段边界与发布动作

- 已遵守 M5 shadow-only 阶段边界。
- 未执行 live DB。
- 未让 NL2SQL 正式接管用户可见 QA。
- 未 push / merge / deploy。
