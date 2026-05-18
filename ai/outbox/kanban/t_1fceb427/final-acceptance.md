# NL2SQL M7 物流只读中间库 Shadow Smoke MVP 最终验收

## 1. 任务结论

- 看板任务：`t_1fceb427`
- 阶段：NL2SQL M7：物流只读中间库 Shadow Smoke MVP
- 分支：`feature/nl2sql-m7-readonly-middle-db-smoke`
- 结论：已完成并通过恢复后最终验证。

本次任务最初因 worker 达到 iteration budget 停止，状态为 blocked。恢复后已补齐缺失的最终 review 结果、最终验收文档、最终测试日志与最终 patch，并重新确认分支为 M7 专用分支。

## 2. 修改文件清单

### 后端代码

- `backend/app/domains/logistics/services/nl2sql/readonly_middle_db.py`
- `backend/app/domains/logistics/services/nl2sql/m7_readonly_smoke.py`
- `backend/app/domains/logistics/services/nl2sql/__init__.py`

### 固定 dev 脚本

- `scripts/dev/run_logistics_nl2sql_m7_readonly_smoke.py`

### 测试

- `tests/unit/logistics/nl2sql/test_m7_readonly_middle_db_smoke.py`

### 文档

- `docs/NL2SQL_LOGISTICS_M7_READONLY_MIDDLE_DB_SMOKE_MVP_PLAN.md`

### 验收材料

- `ai/outbox/kanban/t_1fceb427/diff.patch`
- `ai/outbox/kanban/t_1fceb427/test.log`
- `ai/outbox/kanban/t_1fceb427/static-scan.json`
- `ai/outbox/kanban/t_1fceb427/review-bundle.md`
- `ai/outbox/kanban/t_1fceb427/review-result-final.json`
- `ai/outbox/kanban/t_1fceb427/final-acceptance.md`
- `ai/outbox/kanban/t_1fceb427/m7-shadow-smoke-report.md`
- `ai/outbox/kanban/t_1fceb427/m7-shadow-smoke-records.jsonl`

## 3. 关键改动

1. 新增真实 MySQL 中间库只读 executor：
   - 只允许 `EXPLAIN SELECT`。
   - 只允许带 `LIMIT` 的 `SELECT` trial。
   - 拒绝多语句、非 SELECT、无 LIMIT、LIMIT 超上限。
   - 参数使用 driver 绑定，不拼接参数值。
   - DB 异常统一收敛为稳定错误码，避免泄漏 host/user/password/DSN。

2. 新增 M7 shadow smoke runner：
   - 复用 M6 已审计 success 样例。
   - 使用 `LogisticsSqlSafetyChecker` 与 `LogisticsSqlExecutionService`。
   - 缺配置或连接失败时 fail-closed / environment_unavailable，不伪造成功。
   - 输出脱敏 JSONL 与 Markdown 报告。

3. 新增固定 dev 脚本：
   - `scripts/dev/run_logistics_nl2sql_m7_readonly_smoke.py`
   - 用于本地触发 M7 只读 smoke，避免临时 heredoc 命令，符合 `AGENTS.md` 命令安全规则。

4. 根据 review 结果补强真实 DB 边界：
   - driver 前拒绝 SQL 注释、`INTO OUTFILE`、`INTO DUMPFILE`、`UNION`、`LOAD_FILE`、`FOR UPDATE`、`LOCK IN SHARE MODE`、`PROCEDURE ANALYSE`、`SLEEP`、`BENCHMARK`。
   - M7 runner 将外部传入的 `trial_limit` / `max_limit` 钳制到硬上限 20。
   - `__init__.py` 不 re-export direct readonly DB config/executor helpers，只保留 M7 runner/sample API。

5. 恢复阶段额外补齐 reviewer 非阻塞建议：
   - 显式单测覆盖 `FOR UPDATE`、`LOCK IN SHARE MODE`、`PROCEDURE ANALYSE`、`SLEEP`、`BENCHMARK` 等危险 SELECT 变体。

## 4. 最终测试命令和结果

恢复后最终验证记录在：

- `ai/outbox/kanban/t_1fceb427/test.log`

结果如下：

1. Focused M7：
   - 命令：`backend/.venv/bin/python -m pytest tests/unit/logistics/nl2sql/test_*m7*.py -q`
   - 结果：`23 passed in 0.33s`

2. Adjacent NL2SQL：
   - 命令：`backend/.venv/bin/python -m pytest tests/unit/logistics/nl2sql -q`
   - 结果：`156 passed, 9 warnings in 3.56s`

3. Logistics unit：
   - 命令：`backend/.venv/bin/python -m pytest tests/unit/logistics -q`
   - 结果：`170 passed, 9 warnings in 3.59s`

4. Full unit：
   - 命令：`backend/.venv/bin/python -m pytest tests/unit -q`
   - 结果：`214 passed, 9 warnings in 4.28s`

5. py_compile：
   - 命令：`backend/.venv/bin/python -m py_compile backend/app/domains/logistics/services/nl2sql/readonly_middle_db.py backend/app/domains/logistics/services/nl2sql/m7_readonly_smoke.py scripts/dev/run_logistics_nl2sql_m7_readonly_smoke.py`
   - 结果：passed

6. git diff check：
   - 命令：`git diff --check`
   - 结果：passed

7. 项目现有测试 wrapper：
   - 命令：`PYTHONPATH="$PWD" PATH="$PWD/backend/.venv/bin:$PATH" ai/scripts/run_tests.sh basic`
   - 结果：`[Test] All checks passed`，退出码 `0`
   - 说明：恢复过程中曾先直接运行 `ai/scripts/run_tests.sh basic`，该次调用使用了系统 Anaconda pytest 且未带 `PYTHONPATH`，在收集阶段报 `ModuleNotFoundError: No module named 'backend'`。该失败属于 wrapper 调用环境问题，不是 M7 代码逻辑失败；随后已用显式 `PYTHONPATH` 和 venv PATH 重跑通过。

## 5. Live MySQL smoke

已执行 live MySQL smoke：

- 命令：`backend/.venv/bin/python scripts/dev/run_logistics_nl2sql_m7_readonly_smoke.py --artifact-dir ai/outbox/kanban/t_1fceb427`
- `environment_status`: `available`
- `live_smoke_executed`: `true`
- `total`: `2`
- `success`: `2`
- `success_rate`: `1.0`

输出报告：

- `ai/outbox/kanban/t_1fceb427/m7-shadow-smoke-report.md`
- `ai/outbox/kanban/t_1fceb427/m7-shadow-smoke-records.jsonl`

报告与 JSONL 只包含脱敏统计、hash、状态和错误码，不包含 SQL 原文、参数值、host/user/password/full DSN/API key/token。

## 6. 静态扫描和独立 review

### 静态扫描

- 文件：`ai/outbox/kanban/t_1fceb427/static-scan.json`
- 状态：passed
- 阻塞项：无

扫描结论：

- 生产代码未发现新增硬编码 secret、shell injection、eval/exec、pickle、SQL 字符串 format、临时 token 等问题。
- M7 生成的 report / JSONL 未发现 SQL 原文、DSN、host/user/password、token、Bearer、`sk-` 等泄漏模式。
- 单测中的 `unit-password` / `db.internal` / `admin_user` 仅为脱敏 fixture，非真实密钥或连接信息。

### 独立 review

- 文件：`ai/outbox/kanban/t_1fceb427/review-result-final.json`
- 结果：passed
- `security_concerns`: []
- `logic_errors`: []
- `suggestions`: []

独立 review 结论：未发现真实 DB 写入/非 SELECT、M4 safety gate 绕过、无界或超 20 LIMIT trial、参数拼接、敏感信息/SQL 原文泄漏、误接正式物流 QA 主链路、AGENTS.md 命令安全违规或既有物流/BOM 能力回归问题。

## 7. 阶段边界确认

本阶段只实现只读 shadow smoke 与本地评估报告能力。

未做：

- 未接正式物流 QA 主链路。
- 未改前端。
- 未建数据库迁移。
- 未连接 Oracle。
- 未直查 SAP Oracle MID。
- 未执行任何写库 SQL。
- 未恢复临时 token 机制。
- 未向用户可见回答暴露技术 trace。

## 8. 对现有 BOM / 物流能力影响

- 对现有 BOM 能力：无影响。
- 对现有物流正式问答链路：无影响。
- 新增能力处于 NL2SQL shadow smoke 层，仅通过固定脚本和 M7 runner 主动触发。

## 9. 已知风险与后续建议

1. M7 live smoke 当前只覆盖 2 条 M6 success 样例，属于 MVP 级真实库连通与只读执行闭环验证。
2. 后续 M8 建议扩展为更完整的中间库 shadow 样例集与评估维度，包括更多物流指标、时间范围、承运商/路线/报价/均价等业务口径。
3. 若后续要接正式 QA，仍必须经过独立阶段，不应直接把 M7 shadow runner 接入用户问答主链路。
4. 可继续把评估记录从本地 JSONL 演进为受控 shadow evaluation store，但需要单独设计迁移与权限边界。
