# M5-5 closeout report

## 收口结论

本轮在 `feature/isp-m5-inventory-nl2sql-integration` 上执行 M5-5 收口、归档与提交准备。当前仓库已经具备产销存 M5 shadow-only QueryPlan / SQLPlan 离线对比能力，并有 runner、focused tests、脱敏记录、脱敏报告与两轮返修/复审证据。

## M5 主链与返修卡状态

- `t_d76060c2`：M5-3 初版过程证据，独立 review 曾发现 blocker；仅保留为历史过程证据，不作为最终通过依据。
- `t_87762691`：M5-4 初版过程证据，review-result 曾为 false；仅保留为历史过程证据，不作为最终通过依据。
- `t_3ca95bf9`：M5-3R shadow compare review blocker fix，`review-result.json` 显示 `passed=true`，作为最终通过依据之一。
- `t_45ab3a93`：M5-4R final quality gate after shadow fix，`review-result.json` 显示 `passed=true`，作为最终通过依据之一。

最终通过依据以 `t_3ca95bf9` 与 `t_45ab3a93` 为准；历史过程证据只用于追溯 blocker 与返修过程。

## 当前已完成能力判断

- 已新增产销存 M5 shadow-only 离线对比服务，支持从 M4-6 真实问法样例构造 shadow compare 样例。
- 已用独立 SQLPlan fixture 与既有 QueryPlan 业务签名进行比较，避免从 QueryPlan 反向生成候选后的自我匹配。
- 已覆盖成功、暂不支持、澄清、候选缺失、SQL/凭据噪声、期间语义与期间参数安全指纹等 fail-closed 场景。
- 已提供固定 dev runner，可重复生成脱敏 JSONL 与 Markdown 报告。
- 已有 focused tests、产销存回归、物流回归、计划 BOM / 功率回归、compile、frontend build、static scan 与独立 review 证据。
- `frontend/tsconfig.tsbuildinfo` 已记录 diff，确认属于 TypeScript build cache 文件差异，并按任务建议执行路径级还原，不纳入提交。

## 当前未完成能力判断

- 本阶段仍为 shadow-only；不接入正式用户可见 QA 主链路。
- 本阶段不执行 live DB，不连接生产/真实业务数据库。
- 本阶段不启用 live provider gate，不让 NL2SQL 正式接管产销存问答。
- 本阶段不扩样到下一批产销存 shadow 样例，不新增多 Agent / 多工具正式编排。

## 本次任务与当前仓库状态一致性

本次任务是 M5-5 收口/归档/提交准备卡，不是新功能开发卡。当前仓库中的 M5 shadow compare 源码、测试、runner 与 outbox 证据均处于未提交状态，符合本卡要求的“确认并提交准备”工作。

## 本轮允许修改范围

- `backend/app/domains/business_analysis/services/inventory_sales_production/m5_shadow_compare.py`
- `scripts/dev/run_inventory_sales_production_m5_shadow_compare.py`
- `tests/unit/business_analysis/test_inventory_sales_production_m5_shadow_compare.py`
- `ai/outbox/kanban/t_3ca95bf9/**`
- `ai/outbox/kanban/t_45ab3a93/**`
- 历史过程证据：`ai/outbox/kanban/t_d76060c2/**`、`ai/outbox/kanban/t_87762691/**`
- 本卡证据：`ai/outbox/kanban/t_4131bbbb/**`

## 本轮禁止修改范围

- 不修改 main，不 push，不 merge，不 deploy。
- 不切换到其他业务分支。
- 不执行 live DB，不接入正式 QA 主链路。
- 不改物流、计划 BOM、功率预测主链路代码。
- 不提交 `frontend/tsconfig.tsbuildinfo` 构建缓存差异。
- 不使用 `git add -A` 或 `git add .`。

## 阶段边界确认

本阶段严格保持 M5 shadow-only。产物只用于内部离线对比、脱敏记录、脱敏报告和验收追溯；用户可见回答链路不暴露 SQL、表名、字段名、query_key、planner、schema、raw/debug、LLM、密钥或连接串。
