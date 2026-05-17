# gcl-bp-ai: NL2SQL M5 物流 Shadow Pipeline + 评估日志 MVP - Final Acceptance

## 结论

看板任务 `t_121646ca` 原始停止状态为 `blocked/crashed`，停止原因不是业务代码验收失败，而是 worker 在多轮运行中遭遇网络/API 超时与协议违规：

- 第 1 轮：`blocked`。
- 第 2/3/4 轮：`crashed`，原因均为 worker 退出时未调用 `kanban_complete` 或 `kanban_block`，属于 Hermes Kanban 协议违规。
- 日志中出现多次 `APITimeoutError` / `APIConnectionError`，其中最后一轮在 final review / 收尾阶段超时退出。

接手复查后，M5 主体代码已经基本完成，但第一轮独立 review 发现 evaluation log 安全边界存在 blocker。当前已完成补救、复验、第二轮独立 review，通过后可判定 M5 任务完成。

## 当前分支

```text
feature/nl2sql-m5-shadow-pipeline-eval-log
```

## 关键交付

新增/更新：

```text
backend/app/domains/logistics/services/nl2sql/evaluation_log.py
backend/app/domains/logistics/services/nl2sql/shadow_pipeline.py
backend/app/domains/logistics/services/nl2sql/__init__.py
tests/unit/logistics/nl2sql/test_evaluation_log.py
tests/unit/logistics/nl2sql/test_shadow_pipeline.py
docs/NL2SQL_LOGISTICS_M5_SHADOW_PIPELINE_MVP_PLAN.md
```

验收材料：

```text
ai/outbox/kanban/t_121646ca/diff.patch
ai/outbox/kanban/t_121646ca/test.log
ai/outbox/kanban/t_121646ca/static-scan.json
ai/outbox/kanban/t_121646ca/review-result-final.json
ai/outbox/kanban/t_121646ca/review_bundle.md
ai/outbox/kanban/t_121646ca/final-acceptance.md
```

## 功能范围

M5 新增内部 shadow pipeline 与 evaluation log MVP：

1. 接收用户问题、可选改写问题、受控 SQLPlan candidate。
2. 仅支持 `domain=logistics` 与 `source_system=middle_db`。
3. 缺少 candidate 或非 `sql_direct` 策略时只记录 skipped/unsupported，不进入 SQL 阶段。
4. 串联 M3 `LogisticsSqlPlanValidator`。
5. 串联 M4 `LogisticsSqlRenderer`。
6. 串联 M4 `LogisticsSqlSafetyChecker`。
7. 串联 M4 `LogisticsSqlExecutionService` 做 EXPLAIN 与 trial。
8. 输出 shadow result 与脱敏 evaluation log record。
9. 支持 in-memory sink 与受控路径 JSONL sink。

## 阶段边界

已确认未越界：

- 未接正式物流 QA 主链路。
- 未替换现有 planner。
- 未改前端。
- 未建数据库迁移。
- 未读取 `.env`。
- 未接真实业务库。
- 未直查 SAP Oracle MID。
- 未让 LLM 直接生成可执行 SQL。
- 未把技术 trace 暴露给用户可见回答。
- 未把新问法识别主逻辑堆到 `data_qa_planner.py`。

## Review blocker 与修复

第一轮独立 review 结论为未通过，核心 blocker：

1. `LogisticsNl2SqlEvaluationLogRecord.from_pipeline()` 会校验 `sql_hash`，但直接构造 record 可绕过，导致 SQL 原文/密钥可能进入 `sql_hash`。
2. JSONL sink 直接 `record.model_dump()` 持久化，缺少写入前二次安全校验。
3. DSN 脱敏只替换密码段，仍可能保留账号、host、db path。

已修复：

1. 在 `LogisticsNl2SqlEvaluationLogRecord` 字段 validator 中固化文本、列表、`sql_hash`、计数字段的安全约束。
2. `sql_hash` 只接受 64 位十六进制，其他内容一律丢弃。
3. in-memory sink 与 JSONL sink 写入前统一通过 `model_validate(record.model_dump(mode="json"))` 二次校验。
4. DSN 整体替换为 `[DSN_REDACTED]`。
5. SQL-like 文本扩展覆盖 `SELECT 1`、`WITH ... SELECT`、`EXPLAIN SELECT`、DML/DDL。
6. 补充 direct construction 与 JSONL bypass 的 RED/GREEN 单测。

第二轮独立 review 结论：

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": [],
  "missing_tests": []
}
```

## 验证结果

`ai/outbox/kanban/t_121646ca/test.log` 记录的最终复验结果：

```text
focused M5 shadow/evaluation: 19 passed
nl2sql unit regression: 125 passed, 9 warnings
logistics unit regression: 139 passed, 9 warnings
all unit regression: 183 passed, 9 warnings
py_compile: passed
git diff --check: passed
```

`ai/outbox/kanban/t_121646ca/static-scan.json`：

```text
status: passed
true_blocker_count: 0
finding_count: 0
```

warning 说明：

- 9 个 warning 均来自 `pymilvus/pkg_resources/google._upb` 的第三方 deprecation warning。
- 与 M5 改动无关。

## 风险与后续建议

非阻断建议：

1. 后续可给 `LogisticsNl2SqlEvaluationLogRecord` 增加 `validate_assignment` 或 frozen，降低对象创建后被手工改写再直接序列化的误用风险；当前 sink 写入前 revalidate 已覆盖持久化路径。
2. 如 JSONL sink 未来用于多租户或不可信目录，可进一步加固 symlink/TOCTOU 路径逃逸防护；当前受控 root_dir 对内部 shadow/evaluation 场景可接受。
3. 后续可扩展 redaction 覆盖 `client_secret`、`secret_key` 等复合密钥名，并给 `sql_param_keys` 增加参数名形态约束。

## 是否需要用户资源

当前 M5 不需要用户提供额外资料或资源。

如进入下一阶段，可能需要用户确认：是否允许做“只读中间库 shadow smoke”，以及 shadow 日志最终落地方式采用 JSONL、数据库评估表，还是先保留内存/文件离线模式。
