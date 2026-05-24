# Hermes 管理验收：NQE-SQL-MAIN-7 元数据同步脚本

## 1. 看板与执行状态

- 看板卡：`NQE-SQL-MAIN-7` / `t_c8b38b1a`
- 分支：`feature/nqe-sql-main-7-metadata-sync`
- worktree：`.worktrees/nqe-sql-main-6-metadata-migrations`
- Codex 后台进程：`proc_d8175d331750`
- 处理说明：Codex 已生成产物和自测日志，但进程长时间不退出且输出不再刷新；Hermes 按恢复策略 kill 进程后执行独立验收。

## 2. scoped 文件范围核对

本卡新增/更新范围符合 NQE-SQL-MAIN-7 边界：

1. `backend/app/services/nqe_metadata_sync.py`
2. `scripts/sync_nqe_metadata.py`
3. `tests/unit/nqe/test_nqe_metadata_sync.py`
4. `ai/outbox/kanban/t_c8b38b1a/test.log`
5. `ai/outbox/kanban/t_c8b38b1a/dry-run-summary.json`
6. `ai/outbox/kanban/t_c8b38b1a/final-acceptance.md`
7. `ai/outbox/kanban/t_c8b38b1a/manager-verification.md`

说明：`backend/app/models/__init__.py`、`backend/app/models/nqe_metadata.py`、迁移文件和 `tests/unit/nqe/test_nqe_metadata_models.py` 属于 NQE-SQL-MAIN-6 前置产物，本卡复用但不作为 7 号卡新增业务逻辑。

## 3. Hermes 修正项

Hermes 在独立安全核对中发现 `tests/unit/nqe/test_nqe_metadata_sync.py` 曾包含本机用户名字面量，用于断言 `source_ref` 中不得出现该用户名。该字面量虽不是凭证，但不应写入代码，因此已移除，保留更通用的 `Path.home()` 断言。

## 4. 独立验收命令

Hermes 已重新执行并刷新 `ai/outbox/kanban/t_c8b38b1a/test.log`：

```text
/opt/anaconda3/bin/python3 -m pytest tests/unit/nqe/test_nqe_metadata_models.py tests/unit/nqe/test_nqe_metadata_sync.py -q
/opt/anaconda3/bin/python3 -m py_compile backend/app/services/nqe_metadata_sync.py scripts/sync_nqe_metadata.py
/opt/anaconda3/bin/python3 scripts/sync_nqe_metadata.py --output-json tmp/hermes/nqe7_manager_verify/dry-run-summary-after-patch.json
git diff --check
```

结果：

- focused tests：`9 passed`
- py_compile：通过
- dry-run：通过
- git diff --check：通过

Dry-run 摘要：

```json
{
  "domains": ["logistics", "business_analysis", "plan_bom"],
  "metadata_version": "nqe_catalog_v1",
  "quality_gate_status": "passed",
  "warnings": [],
  "counts": {
    "domains": 3,
    "data_sources": 3,
    "tables": 19,
    "columns": 226,
    "metrics": 65,
    "dimensions": 51,
    "business_rules": 21,
    "retrieval_chunks": 382,
    "metadata_versions": 1,
    "quality_gates": 1
  }
}
```

## 5. 安全与边界核对

已完成 scoped 扫描：

- 禁用外部参考项目命名清单：0 命中
- 本机绝对路径/用户名：0 命中
- 密码、Token、API Key、DSN、host、user 等风险赋值模式：0 命中
- `frontend/`、`docs/CURRENT_STATUS.md`、`docs/NEXT_TASK.md`、`docs/HANDOFF.md`：0 tracked diff

边界确认：

- 未连接生产库
- 未读取 `.env` 中真实连接信息
- 未调用外部服务
- 未替换正式问答链路
- 未修改前端
- 未 commit / push / deploy

## 6. 验收结论

NQE-SQL-MAIN-7 的最小目标已完成：从受控 catalog 构建 NQE 元数据 bundle、生成 dry-run 摘要、支持 SQLite 幂等 upsert、生成五类 retrieval chunk，并通过 focused tests。

建议将看板卡 `t_c8b38b1a` 标记为完成，后续进入 NQE-SQL-MAIN-8：向量索引与召回适配。
