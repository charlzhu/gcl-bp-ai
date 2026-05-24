# NQE-SQL-MAIN-14 回滚方案

```bash
# 删除从恢复工作树回填的文件
rm backend/app/services/nqe_metadata_sync.py
rm backend/app/models/nqe_metadata.py

# 恢复 graph 文件到 checkpoint 状态
git checkout HEAD -- backend/app/domains/business_qa_graph/nqe_sql_agent_graph.py

# 恢复 NQE 文档
git checkout HEAD -- docs/NQE_SQL_MAIN_CURRENT_STATUS.md docs/NQE_SQL_MAIN_NEXT_TASK.md docs/NQE_SQL_MAIN_HANDOFF.md
```

回滚影响：
1. 2 个 auto-context 测试回到 FAILED 状态
2. NQE-15 物流 SQL Agent 接入的前置条件不满足
