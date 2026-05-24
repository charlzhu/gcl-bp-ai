# NQE-SQL-MAIN-14 rollback

## 回滚范围
如需回滚本卡，移除或恢复以下 scoped 文件中的 NQE-SQL-MAIN-14 变更：
- `backend/app/services/nqe_metadata_sync.py`
- `backend/app/domains/business_qa_graph/nqe_sql_agent_graph.py`
- `scripts/sync_nqe_metadata.py`
- `tests/unit/nqe/test_nqe_metadata_sync.py`
- `tests/unit/business_qa_graph/test_nqe_sql_agent_graph_skeleton.py`
- `ai/outbox/kanban/t_9c5f1f49/*`

## 回滚方式
1. 若正式合入时使用单独提交：直接 revert 对应提交。
2. 若仍处于当前 untracked/worktree 状态：按 `ai/outbox/kanban/t_9c5f1f49/diff.patch` 反向审阅并手动删除以下新增能力：
   - `NqeMetadataSyncBuilder.__init__` 的 `include_domains/domain_codes` 参数与 `_normalize_domain_filters` 过滤逻辑。
   - `build_nqe_context_package_from_bundle` helper 与 `__all__` 导出。
   - `retrieve_context_multiway` 中物流域自动构建元数据上下文逻辑。
   - `scripts/sync_nqe_metadata.py` 的 `--domain/--include-domain` 参数。
   - 对应新增测试用例。
3. 回滚后重新运行：
   - `/opt/anaconda3/bin/python3 -m pytest tests/unit/nqe/test_nqe_metadata_sync.py tests/unit/business_qa_graph/test_nqe_sql_agent_graph_skeleton.py -q`
   - `/opt/anaconda3/bin/python3 -m py_compile backend/app/services/nqe_metadata_sync.py backend/app/domains/business_qa_graph/nqe_sql_agent_graph.py scripts/sync_nqe_metadata.py tests/unit/nqe/test_nqe_metadata_sync.py tests/unit/business_qa_graph/test_nqe_sql_agent_graph_skeleton.py`

## 数据安全
本卡未写正式数据库、未读取 `.env`、未连接 SAP/Oracle/live DB；回滚不涉及数据迁移或线上数据清理。
