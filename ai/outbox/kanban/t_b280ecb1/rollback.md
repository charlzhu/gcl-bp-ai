# NQE-SQL-MAIN-15 回滚方案

```bash
git checkout HEAD -- backend/app/domains/business_qa_graph/nqe_sql_agent_graph.py
rm tests/unit/business_qa_graph/test_nqe_sql_agent_logistics.py
git checkout HEAD -- docs/NQE_SQL_MAIN_CURRENT_STATUS.md docs/NQE_SQL_MAIN_NEXT_TASK.md docs/NQE_SQL_MAIN_HANDOFF.md
```

回滚影响：
1. 失去 9 个物流域测试覆盖
2. logistics auto-context 场景下 generate_sql_direct 回退到 "SELECT 1"
