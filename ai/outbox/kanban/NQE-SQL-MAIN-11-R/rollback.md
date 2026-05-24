# NQE-SQL-MAIN-11-R 回滚方案

## 回滚方式

如果本卡回填的代码需要回滚，执行以下步骤：

```bash
# 删除从恢复工作树回填的所有文件
rm backend/app/domains/business_qa_graph/nqe_sql_safety.py
rm backend/app/domains/business_qa_graph/nqe_sql_agent_graph.py
rm backend/app/domains/business_qa_graph/nqe_sql_agent_state.py
rm backend/app/domains/business_qa_graph/nqe_sql_agent_trace.py
rm tests/unit/business_qa_graph/test_nqe_sql_agent_safety_precheck.py
rm tests/unit/business_qa_graph/test_nqe_sql_agent_explain_correct.py
rm tests/unit/business_qa_graph/test_nqe_sql_agent_trace_replay.py
rm tests/unit/business_qa_graph/test_nqe_sql_agent_graph_skeleton.py

# 恢复 NQE 文档状态
git checkout -- docs/NQE_SQL_MAIN_CURRENT_STATUS.md docs/NQE_SQL_MAIN_NEXT_TASK.md docs/NQE_SQL_MAIN_HANDOFF.md
```

## 回滚影响

1. 根工作区失去 nqe_sql_safety.py 实现
2. 33 个通过的 NQE focused 测试将无法运行
3. NQE-11 安全预检能力回退到"仅工作树中存在"的状态
4. 不影响旧业务链路
5. 不影响物管/SAP MID 任务
