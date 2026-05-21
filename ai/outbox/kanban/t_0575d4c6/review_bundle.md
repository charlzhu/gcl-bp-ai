# t_0575d4c6 / M10-D1 最终 Review Bundle

## 任务范围

物流 NL2SQL M10-D1：增加 fake executor 下的 EXPLAIN / readonly trial shadow gate schema、状态枚举、错误码、默认关闭策略与脱敏 report 字段。

## 本轮允许修改文件

1. `backend/app/domains/logistics/services/nl2sql/__init__.py`
2. `backend/app/domains/logistics/services/nl2sql/m10d_shadow_gate.py`
3. `tests/unit/logistics/nl2sql/test_m10d_shadow_gate.py`

## 禁止/未做事项

- 未连接真实数据库。
- 未执行真实 EXPLAIN / trial。
- 未接入正式 QA 主链路。
- 未接入前端。
- 未接入 SAP Oracle MID。
- 未 push / merge / deploy。
- 未修改历史物流 / BOM / 功率预测正式链路。

## 关键实现点

- 新增 `LogisticsNl2SqlM10DShadowGateConfig`：默认 `enabled=False`、`explain_enabled=False`、`trial_enabled=False`。
- 新增 `LogisticsNl2SqlM10DShadowGateReport`：只输出状态、阶段、错误码、EXPLAIN/trial 状态、行数摘要、timeout/elapsed、SQL hash、脱敏 reason code 和 `shadow_only=True`。
- 新增 `LogisticsNl2SqlM10DShadowGate`：
  - 默认关闭时不构造 executor、不 hash SQL；
  - 只允许 `middle_db` 来源；
  - 进入 executor 前复核 `LogisticsSqlSafetyChecker`；
  - trial 依赖 EXPLAIN；
  - EXPLAIN 失败 fail-closed 并跳过 trial；
  - trial 只返回 row_count/row_cap_applied，不返回行值；
  - report 统一脱敏，禁止输出 SQL 原文、参数值、表名、字段名、连接串、异常原文和 trial 行值。
- `__init__.py` 仅增加 M10-D gate 公开导出。

## 测试证据

详见 `test.log`。

- Focused：`python -m pytest tests/unit/logistics/nl2sql/test_m10d_shadow_gate.py -q` => `8 passed`。
- Adjacent full NL2SQL unit：`python -m pytest tests/unit/logistics/nl2sql -q` => `234 passed, 9 warnings`（第三方 deprecation warnings）。
- Compile / diff-check：`python -m py_compile ... && git diff --check ...` => passed。

## 静态扫描证据

详见 `static-scan.json`。

- `blocking_count=0`
- `needs_review_count=0`
- findings 分类：`redaction_logic=1`、`test_redaction_probe=8`
- 说明：命中项仅为脱敏逻辑与测试负例字符串，未发现真实 hardcoded secret、shell injection、eval/exec、pickle、SQL string formatting 风险。

## 补丁证据

- `diff.patch`：任务级完整补丁，包含 tracked `__init__.py` diff，以及两个 untracked 新文件的 no-index diff。
- `git_status.txt`：最终 worktree 状态，包含一个历史无关 dirty 文件 `ai/outbox/kanban/t_7895e090/m8-shadow-eval-records.jsonl`，不属于本轮任务。

## Reviewer 关注点

请只读审查 `diff.patch` / 本 bundle / `static-scan.json` / `test.log`，忽略无关 dirty 文件。

重点判断：

1. 默认关闭是否不构造 executor、不触库、不 hash SQL。
2. 显式开启是否仍默认 fake executor，并只允许 `middle_db`。
3. trial 是否不能绕过 EXPLAIN；EXPLAIN fail 是否 fail-closed 并跳过 trial。
4. M10-D gate 内是否二次复核 SQL safety；unsafe SQL / SELECT * / 超 LIMIT 是否阻断 executor。
5. Report 是否不泄露 SQL 原文、params value、表名、字段名、连接串、异常原文、trial 行值。
6. `__all__` 导出是否合理。
7. 是否越界修改正式 QA、前端、Oracle/SAP、真实 DB 执行链路。
