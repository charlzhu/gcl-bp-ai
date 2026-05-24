# t_205f18fc / NQE-SQL-MAIN-9 最终验收

## 1. 修改文件清单

1. `backend/app/models/nqe_metadata.py`
2. `backend/app/models/__init__.py`
3. `backend/alembic/versions/20260523_0007_create_nqe_value_index_tables.py`
4. `backend/app/services/nqe_metadata_sync.py`
5. `backend/app/services/nqe_value_index.py`
6. `scripts/rebuild_nqe_value_index.py`
7. `tests/unit/nqe/test_nqe_metadata_models.py`
8. `tests/unit/nqe/test_nqe_value_index.py`
9. `ai/outbox/kanban/t_205f18fc/test.log`
10. `ai/outbox/kanban/t_205f18fc/dry-run-summary.json`
11. `ai/outbox/kanban/t_205f18fc/final-acceptance.md`

## 2. 关键实现说明

1. 新增 `NqeValueInfo` 与 `NqeValueIndex` ORM 模型，覆盖取值资产、检索文本、别名、频次、质量分、来源快照、生命周期字段。
2. 新增 0007 Alembic 迁移，`down_revision=20260523_0006`，创建 `nqe_value_info` / `nqe_value_index`，并为 `nqe_column_info` 补充 `sample_values_json`、`value_index_enabled`、`synonyms_json`、`unit`。
3. `NqeMetadataSyncBuilder` 从 catalog 的 `field_value_examples` / `sample_values` 和 `aliases` 补齐字段安全样例值与 value index 启用标记。
4. 新增 `NqeValueIndexBuilder`，支持字段白名单构建、catalog 静态候选、MySQL 限量 distinct dry-run/apply、幂等 upsert。
5. 新增 `NqeValueRecallService`，只查询 `nqe_value_index`，支持精确、别名、包含匹配，返回 `score_breakdown`、`matched_by`、`needs_disambiguation`。
6. 新增 `scripts/rebuild_nqe_value_index.py`，默认 dry-run，不读取 `.env`，不连接真实业务库。

## 3. dry-run 统计摘要

```json
{
  "apply_status": "dry_run",
  "domain_counts": {
    "business_analysis": 57,
    "logistics": 58,
    "plan_bom": 62
  },
  "dry_run": true,
  "errors": [],
  "indexed_columns": 126,
  "metadata_version": "nqe_value_index_v1",
  "skipped_columns": 100,
  "top_k": 10,
  "total_columns": 226,
  "total_values": 177,
  "warnings": []
}
```

## 4. 测试命令与结果

1. `/opt/anaconda3/bin/python3 -m pytest tests/unit/nqe/test_nqe_metadata_models.py tests/unit/nqe/test_nqe_metadata_sync.py tests/unit/nqe/test_nqe_metadata_vector_index.py tests/unit/nqe/test_nqe_value_index.py -q`
   - 结果：`27 passed in 3.19s`
2. `/opt/anaconda3/bin/python3 -m py_compile backend/app/models/nqe_metadata.py backend/app/services/nqe_value_index.py scripts/rebuild_nqe_value_index.py`
   - 结果：通过
3. `/opt/anaconda3/bin/python3 scripts/rebuild_nqe_value_index.py --output-json tmp/hermes/nqe9_verify/dry-run-summary.json`
   - 结果：通过，已复制到 `ai/outbox/kanban/t_205f18fc/dry-run-summary.json`
4. `git diff --check`
   - 结果：通过

测试日志：`ai/outbox/kanban/t_205f18fc/test.log`

## 5. 风险点与未解决事项

1. 本卡未连接真实 MySQL，apply 查询仅保留注入 Session 接口和 fake/local 测试覆盖。
2. 当前静态候选来自 catalog 安全样例值，不代表生产全量业务实体。
3. MySQL distinct SQL 已带白名单、LIMIT 和执行时间 hint，但真实库执行前仍需由后续任务配置连接、权限和超时策略。
4. NQE 设计文档 `docs/NQE_SQL_MAIN_2_METADATA_KB_DESIGN.md` 与 `docs/NQE_SQL_MAIN_3_RETRIEVAL_DESIGN.md` 当前 worktree 未找到；本轮按用户任务说明、现有 NQE-6/7 代码和受控 catalog 实现。

## 6. 影响范围确认

1. 物流主链路：未修改正式问答入口、Graph、domain service、prompt。
2. 计划 BOM 主链路：未修改正式问答入口、导入、QA、消歧、对比代码。
3. 经营分析主链路：未修改正式入口或查询链路。
4. 物管现有主链路：未进入 M2 正式同步/问答入口开发。
5. frontend：未修改。

## 7. 发布与阶段边界

1. 未读取 `.env`。
2. 未连接生产库。
3. 未覆盖 `docs/CURRENT_STATUS.md`、`docs/NEXT_TASK.md`、`docs/HANDOFF.md`。
4. 未修改 `ai/inbox/attachments/` 原始附件。
5. 未自动 commit。
6. 未 push。
7. 未 deploy。
