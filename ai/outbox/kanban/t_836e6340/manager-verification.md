# NQE-SQL-MAIN-6 Hermes 管理验收说明

## 看板为什么回到 ready

本卡由 Hermes 在主聊天中手动 `claim` 后，通过独立 Codex 后台进程执行。该 Codex 进程不是 Kanban worker 本身，因此不会向看板 run 发送 heartbeat，也不会自动调用 `kanban_complete`。

看板记录显示：

- `claimed` run_id=98
- claim lock 到期
- `reclaimed`，error 为 `stale_lock=192.168.1.3:92602`
- 任务状态恢复为 `ready`

因此，“就绪状态”代表看板锁被回收，不代表 Codex 失败，也不代表产物缺失。

## Hermes 独立复核结果

1. Codex 后台进程 `proc_a84e542a2839` 已以 exit code 0 结束。
2. scoped 文件已产生：
   - `backend/alembic/versions/20260523_0006_create_nqe_metadata_tables.py`
   - `backend/app/models/nqe_metadata.py`
   - `backend/app/models/__init__.py`
   - `tests/unit/nqe/test_nqe_metadata_models.py`
   - `ai/outbox/kanban/t_836e6340/*`
3. 未修改 `frontend/`。
4. 未修改 `docs/CURRENT_STATUS.md`、`docs/NEXT_TASK.md`、`docs/HANDOFF.md`。
5. 未连接真实数据库，未执行真实迁移，未 commit/push/deploy。
6. scoped 新增/修改文件未发现外部参考项目名称或外部项目前缀命名。
7. scoped 新增/修改文件未发现真实密钥、连接串、账号或密码字面量。

## Hermes 独立测试

```bash
/opt/anaconda3/bin/python3 -m pytest tests/unit/nqe/test_nqe_metadata_models.py -q
```

结果：`3 passed in 0.21s`。

```bash
/opt/anaconda3/bin/python3 -m py_compile backend/alembic/versions/20260523_0006_create_nqe_metadata_tables.py backend/app/models/nqe_metadata.py backend/app/models/__init__.py tests/unit/nqe/test_nqe_metadata_models.py
```

结果：通过，无输出。

```bash
git diff --check
```

结果：通过，无输出。

## 处理动作

Hermes 将重新 claim 本卡并手动 complete，使看板状态与已完成事实一致。
