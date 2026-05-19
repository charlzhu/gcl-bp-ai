# t_0006adfb 最终验收说明：NL2SQL M1 字段级引用校验收尾

## 结论

已完成物流 NL2SQL M1 Semantic Catalog 字段级引用校验收尾。`join.on` 已 fail-closed 到单条 `table.column = table.column` 等值表达式；表级边界也已补齐，`allowed_read=false` 的非白名单或非 middle_db 表不再能混入 catalog。

本轮未提交、未合并、未部署。

## 根因与修复

1. 原始 reviewer 阻塞点：`join.on` 若只提取 `table.column` token，会让 `... OR 1=1` 这类额外 SQL 片段通过。
2. 当前代码使用 `re.fullmatch` 严格解析 `table.column = table.column`，并在加载期校验：
   - 只能一条谓词；
   - 左右引用表必须来自声明的 join 左右表集合；
   - 两侧字段必须存在于各自 catalog columns；
   - 额外 SQL 片段统一抛 `catalog_join_on_expression_invalid::<join_id>`。
3. 独立 reviewer 追加发现：表级校验此前只校验 `allowed_read=true` 的表，`allowed_read=false` 的 SAP/ODS/sys_query_log 或非 middle_db 表可留在 `catalog.tables` 中。
4. 已按 TDD 追加 RED guard，并移除该绕过：现在所有 `tables` 条目都必须满足表名白名单、`source_system=middle_db`、`domain=logistics`。

## 修改文件

- `backend/app/domains/logistics/services/nl2sql/semantic_catalog.py`
- `tests/unit/logistics/nl2sql/test_semantic_catalog.py`
- `ai/tasks/running/TASK-nl2sql-semantic-catalog-m1/test.log`
- `ai/tasks/running/TASK-nl2sql-semantic-catalog-m1/static-scan.log`
- `ai/tasks/running/TASK-nl2sql-semantic-catalog-m1/review-result.json`
- `ai/tasks/running/TASK-nl2sql-semantic-catalog-m1/diff.patch`
- `ai/tasks/running/TASK-nl2sql-semantic-catalog-m1/final-acceptance.md`

## TDD 证据

### 原任务 RED/GREEN

- `test_semantic_catalog_loader_rejects_join_on_extra_sql_fragment`
- `test_semantic_catalog_loader_rejects_join_on_missing_join_side`

最新结果：`2 passed`。

### reviewer-fix RED/GREEN

新增 guard：

- `test_semantic_catalog_loader_rejects_non_whitelisted_tables_even_when_not_readable`
- `test_semantic_catalog_loader_rejects_non_middle_db_source_even_when_not_readable`

RED：生产修复前两条均失败，现象为 `Failed: DID NOT RAISE ValueError`。

GREEN：生产修复后 `2 passed`。

## 验证结果

记录文件：`ai/tasks/running/TASK-nl2sql-semantic-catalog-m1/test.log`

- reviewer-fix GREEN guard：`2 passed`
- 原任务 join guard：`2 passed`
- semantic catalog 单测：`18 passed`
- focused suite：`38 passed`
- scoped full：`76 passed`
- compileall scoped source：passed
- py_compile semantic_catalog.py：passed
- git diff --check：passed

## 静态扫描

记录文件：`ai/tasks/running/TASK-nl2sql-semantic-catalog-m1/static-scan.log`

扫描范围：`diff.patch` 新增行。

扫描项：hardcoded_secret、shell_injection、dangerous_eval_exec、unsafe_pickle、sql_string_formatting。

结果：PASS，findings=none。

## 独立 review

记录文件：`ai/tasks/running/TASK-nl2sql-semantic-catalog-m1/review-result.json`

结果：

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": [],
  "suggestions": [
    "后续若 join_type 或 metric.sql_expression 会被直接渲染为 SQL，建议补充枚举/表达式白名单校验以进一步收敛 SQL 渲染面。"
  ],
  "summary": "已审查 task-scoped diff 与验证摘要，表级边界和字段级引用校验满足本次 fail-closed 要求，可安全通过。"
}
```

## 风险与后续建议

- 本卡只收尾 M1 catalog/shadow 层，不进入 Milvus/M2，不扩展正式物流 QA 主链路，不影响 BOM 主链路。
- reviewer 非阻塞建议：后续若 `join_type` 或 `metric.sql_expression` 直接参与 SQL 渲染，应在 M2/M3 SQLPlan/renderer 阶段继续补充枚举与表达式白名单校验。
