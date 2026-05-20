# M10-0：物流 NL2SQL M9 当前树复核与 M10 启动门禁

## 结论

本任务结论：**BLOCKED，暂不启动 M10 代码开发**。

原因不是 M9 fake/shadow 代码链路失败，而是当前独立 worktree / provider 环境无法通过真实 provider 门禁：

1. 当前 worktree 自带 `python3` 缺少项目依赖（pytest / pydantic / yaml），已切换到主项目 venv：`/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/backend/.venv/bin/python`。
2. 使用主项目 venv 后，NL2SQL 单测通过：`190 passed, 9 warnings in 6.02s`。
3. fake/shadow M9 SQLPlan generation 通过：`total=3, success=2, validation_failed=1, expected_status_mismatch_count=0`。
4. provider smoke 失败：Milvus PASS，但 embedding / rerank / LLM provider 均缺少必要配置。
5. catalog reindex 失败：`embedding_unavailable`，`indexed_count=0`，`rc=2`。
6. live provider shadow gate 失败：`total=1, recall_failed=1, expected_status_mismatch_count=1`。

因此当前不能把 M10 candidate-SQL safety-gate 代码开发作为已满足前置条件的任务启动；应先补齐 provider 配置并重跑 M9 live gate。

## 当前仓库已完成能力判断

- 物流 NL2SQL 服务目录、semantic catalog、SQLPlan、renderer/safety、M7/M8/M9 runner 与单测目录存在。
- M9 fake/shadow SQLPlan generation 当前可运行并符合预期：2 个 success 样例 + 1 个“吨位/吨数” fail-closed 样例。
- focused NL2SQL unit tests 当前通过：`190 passed, 9 warnings`。
- compileall 通过，`git diff --check` 通过。
- 静态扫描未发现高风险项；仅存在需要人工 review 的 raw/sql 关键词命中，属于安全代码/审计文本中的关键字候选，未直接判定高风险。

## 当前未完成能力判断

- 当前环境未通过真实 provider smoke：embedding、rerank、LLM provider 配置缺失。
- 当前真实 catalog reindex 未成功：`embedding_unavailable`。
- 当前 live provider shadow gate 未成功：recall 阶段失败。
- 因 live provider gate 未通过，尚不能进入 M10 代码开发。

## 本次任务是否与当前仓库状态一致

一致。当前仓库具备 M9 fake/shadow 骨架和测试基础，但 live provider / reindex 仍是前置门禁。因此本任务应 block，而不是假装通过或直接进入 M10。

## 本轮允许修改范围

本轮实际只写入了本任务 outbox 验收材料：

- `ai/outbox/kanban/t_236bba5f/**`

未修改业务代码。

## 本轮禁止修改范围执行情况

已遵守：

- 未修改正式物流 QA 主链路。
- 未修改前端。
- 未修改 BOM / 功率预测 / 物管 SAP / business_analysis。
- 未 stage、未 commit、未 push、未 deploy。
- 未写入密钥或真实连接串。

## 关键验证结果

| Gate | 结果 | 证据 |
|---|---:|---|
| NL2SQL unit tests | PASS | `test.log`: `190 passed, 9 warnings in 6.02s` |
| compileall | PASS | `compileall.log`: `RC=0` |
| git diff --check | PASS | `diff-check.log`: `RC=0` |
| static scan | PASS_WITH_REVIEW_NOTES | `compile-static-scan.log` |
| fake/shadow M9 SQLPlan | PASS | `m9-shadow-current/m9-shadow-sqlplan-generation-report.md` |
| provider smoke | BLOCKED | `provider-smoke.log` |
| catalog reindex | BLOCKED | `catalog-reindex.log` |
| live provider shadow gate | BLOCKED | `m9-shadow-live-current/m9-shadow-sqlplan-generation-report.md` |

## 遗留问答 / 风险

1. 需要确认物流 NL2SQL provider 配置是否应该从主项目 `.env`、backend `.env` 或 Hermes provider 配置注入；本报告不输出任何真实密钥或连接串。
2. 需要补齐：`llm_base_url`、`llm_api_key`、`embedding_model`、`rerank_model`、`llm_model` 的运行时配置。
3. 补齐配置后必须重新跑：provider smoke → catalog reindex → live provider shadow gate。
4. live gate 通过前，不应启动 M10 candidate-SQL safety-gate 代码开发任务。
5. M10 后续仍应限制在物流域 shadow-only，不替换正式物流 QA 主链路。

## 验收材料路径

- `ai/outbox/kanban/t_236bba5f/gate-summary.json`
- `ai/outbox/kanban/t_236bba5f/test.log`
- `ai/outbox/kanban/t_236bba5f/provider-smoke.log`
- `ai/outbox/kanban/t_236bba5f/catalog-reindex.log`
- `ai/outbox/kanban/t_236bba5f/m9-shadow-current/m9-shadow-sqlplan-generation-report.md`
- `ai/outbox/kanban/t_236bba5f/m9-shadow-live-current/m9-shadow-sqlplan-generation-report.md`
- `ai/outbox/kanban/t_236bba5f/compile-static-scan.log`

## 后续建议

下一步应先创建/执行一个**配置复核与 live gate 重跑任务**，范围只处理 provider 配置读取与门禁重跑；如果确认只是环境变量未传入，可以不改代码。只有 live gate 通过后，再启动真正的 M10 代码开发看板任务。
