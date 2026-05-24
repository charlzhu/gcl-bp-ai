# NQE_SQL_MAIN_NEXT_TASK.md

## 下一步任务：先 checkpoint，再补建 NQE-SQL-MAIN-14

更新时间：2026-05-24 15:30 CST

---

## 一、建议执行顺序

```text
1. 用户确认 checkpoint 计划
2. 执行本地 checkpoint commit（NQE-SQL-MAIN-0~13 产物）
3. 补建 NQE-SQL-MAIN-14 看板卡
4. 执行 NQE-SQL-MAIN-14：物流元数据同步
5. 回归 2 个 auto-context 测试
6. NQE-14 验收后 → NQE-SQL-MAIN-15
```

---

## 二、Checkpoint 详情

### 纳入范围

24 个文件：NQE inbox(2) + NQE docs(11) + NQE 事实源(3) + NQE 实现(4) + NQE 测试(4) + NQE outbox(2 目录)

### 排除范围

- `ai/outbox/kanban/nqe_s3/shadow_compare.jsonl`（旧 NQE 遗留）
- `tests/.../test_nqe_sql_safety_precheck.py`（旧架构遗留）
- `docs/CURRENT_STATUS.md` / `NEXT_TASK.md` / `HANDOFF.md`（物管状态文件）

### Commit message

```
feat(nqe): NQE-SQL-MAIN-0~13 checkpoint — 设计文档、实现骨架与安全预检
```

---

## 三、NQE-SQL-MAIN-14 前置

1. 补建看板卡
2. 实现 `backend/app/services/nqe_metadata_sync.py`
3. 完成后回归 2 个 auto-context 测试

---

## 四、不做事项

1. 不执行 NQE-SQL-MAIN-15
2. 不修改物管状态文件
3. 不修改非 NQE 业务代码
4. 不 push
