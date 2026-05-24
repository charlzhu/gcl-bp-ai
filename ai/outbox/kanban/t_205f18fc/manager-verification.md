# NQE-SQL-MAIN-9 Hermes 管理验收

## 1. 验收结论

- 结论：通过。
- 卡片：NQE-SQL-MAIN-9 / MySQL value index 字段取值索引。
- 范围：仅完成 NQE value index 元数据模型、迁移、受控构建服务、value recall 服务、dry-run CLI 与 focused tests；未接入正式问答主链路。

## 2. 独立验证命令

```bash
/opt/anaconda3/bin/python3 -m pytest tests/unit/nqe/test_nqe_metadata_models.py tests/unit/nqe/test_nqe_metadata_sync.py tests/unit/nqe/test_nqe_metadata_vector_index.py tests/unit/nqe/test_nqe_value_index.py -q
/opt/anaconda3/bin/python3 -m py_compile backend/app/models/nqe_metadata.py backend/app/services/nqe_value_index.py scripts/rebuild_nqe_value_index.py
/opt/anaconda3/bin/python3 scripts/rebuild_nqe_value_index.py --output-json tmp/hermes/nqe9_manager/dry-run-summary.json
git diff --check
```

结果：通过。

## 3. 验证数据摘要

- focused tests：27 passed。
- dry-run：不连接真实业务库，不读取 `.env`。
- dry-run total_columns：226。
- dry-run indexed_columns：126。
- dry-run skipped_columns：100。
- dry-run total_values：177。
- dry-run domain_counts：business_analysis=57，logistics=58，plan_bom=62。

## 4. 关键边界复核

- 字段白名单：只允许 active、allow_select、value_index_enabled、filterable/groupable、非敏感字段进入 value index 构建。
- 业务表 distinct：通过 `NqeValueIndexBuilder.build_from_mysql(... limit_per_column=100, timeout_ms=3000, dry_run=True)` 暴露受控接口；默认 dry-run 不执行 SQL。
- SQL 安全：表名/字段名只接受字母、数字、下划线；执行 SQL 使用已校验标识符并强制 `LIMIT :limit` 与 `MAX_EXECUTION_TIME`。
- recall 边界：`NqeValueRecallService` 只查 `nqe_value_index`，不查业务明细表；topK 生效；输出 score_breakdown 与 needs_disambiguation。
- 敏感信息：scoped 文件和 outbox 未发现真实 host、user、password、DSN、Token、API Key、连接串。
- 禁用命名：scoped 文件和 outbox 未发现外部参考项目禁用命名。
- 禁止范围：未修改 frontend；未覆盖 `docs/CURRENT_STATUS.md`、`docs/NEXT_TASK.md`、`docs/HANDOFF.md`。

## 5. 风险与后续建议

- 当前 value recall 是 NQE-9 MVP，召回候选来自本地 `nqe_value_index` 表；未接入正式 Graph 主链路。
- 后续 NQE-10/主链路接入时，应把 value recall 结果写入 trace 摘要，并在运行态增加更细的候选扫描上限与延迟观测。
- 当前不做真实 MySQL apply；生产环境启用前必须由配置注入只读 Session，并继续保持字段白名单、LIMIT、timeout 和审计日志。

## 6. 交付状态

- 未 commit。
- 未 push。
- 未 deploy。
- 不影响现有物流 / 计划 BOM / 经营分析 / 物管正式问答主链路。
