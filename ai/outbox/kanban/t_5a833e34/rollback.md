# NQE-SQL-MAIN-16 回滚方案

```bash
git checkout HEAD -- backend/app/core/config.py
git checkout HEAD -- backend/app/api/v1/business_qa.py
rm backend/app/domains/business_qa_graph/nqe_logistics_gray.py
rm tests/unit/business_qa_graph/test_nqe_logistics_gray.py
git checkout HEAD -- docs/NQE_SQL_MAIN_CURRENT_STATUS.md docs/NQE_SQL_MAIN_NEXT_TASK.md docs/NQE_SQL_MAIN_HANDOFF.md
```

回滚影响：
1. 失去 nqe_logistics_mode 配置项
2. 失去 API 层面的 NQE shadow compare 集成
3. 失去 8 个灰度模块测试
4. 旧物流正式链路行为不受影响（API 层始终走旧链路）
