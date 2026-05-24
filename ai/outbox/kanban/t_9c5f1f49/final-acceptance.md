# NQE-SQL-MAIN-14 final acceptance

## 任务
NQE-SQL-MAIN-14：物流元数据同步。

## 完成内容
1. `NqeMetadataSyncBuilder` 增加受控单域过滤能力：`include_domains` / `domain_codes` 可只构建物流域；默认不传时继续保持三域全量构建。
2. 新增 `build_nqe_context_package_from_bundle`：从静态 catalog bundle 构造 NQE Graph 安全上下文包，包含 `ready`、`domain_code`、`metadata_version`、`allowed_tables`、`table_columns`、`columns_by_table`、`retrieval_assets`、`source_refs` 等非敏感字段。
3. `retrieve_context_multiway` 在 `domain_hint/selected_domain=logistics` 且未注入上下文时，自动从受控 catalog 构建物流元数据上下文；非本卡接入域保持占位澄清；显式注入上下文仍优先。
4. `scripts/sync_nqe_metadata.py` 增加 `--domain` / `--include-domain` 参数，支持 dry-run 或本地 SQLite 写入时按业务域过滤。
5. 增加 TDD 测试覆盖：物流单域过滤、上下文包安全性、CLI 单域输出、Graph 自动物流上下文、非物流域不自动 ready、注入包优先。

## RED
命令：
`/opt/anaconda3/bin/python3 -m pytest tests/unit/nqe/test_nqe_metadata_sync.py -q`

结果：失败，`build_nqe_context_package_from_bundle` 尚不存在，collection import error。

日志：`ai/outbox/kanban/t_9c5f1f49/red-test.log`

## GREEN / 回归
1. Focused：
`/opt/anaconda3/bin/python3 -m pytest tests/unit/nqe/test_nqe_metadata_sync.py tests/unit/business_qa_graph/test_nqe_sql_agent_graph_skeleton.py -q`
结果：20 passed, 7 warnings。
日志：`ai/outbox/kanban/t_9c5f1f49/test.log`

2. NQE 邻近回归：
`/opt/anaconda3/bin/python3 -m pytest tests/unit/nqe tests/unit/business_qa_graph/test_nqe_sql_agent_graph_skeleton.py tests/unit/business_qa_graph/test_nqe_sql_agent_safety_precheck.py tests/unit/business_qa_graph/test_nqe_sql_agent_explain_correct.py tests/unit/business_qa_graph/test_nqe_sql_agent_trace_replay.py -q`
结果：64 passed, 7 warnings。

3. py_compile：
`/opt/anaconda3/bin/python3 -m py_compile backend/app/services/nqe_metadata_sync.py backend/app/domains/business_qa_graph/nqe_sql_agent_graph.py scripts/sync_nqe_metadata.py tests/unit/nqe/test_nqe_metadata_sync.py tests/unit/business_qa_graph/test_nqe_sql_agent_graph_skeleton.py`
结果：通过，无输出。

4. diff check：
`git diff --check -- backend/app/services/nqe_metadata_sync.py backend/app/domains/business_qa_graph/nqe_sql_agent_graph.py scripts/sync_nqe_metadata.py tests/unit/nqe/test_nqe_metadata_sync.py tests/unit/business_qa_graph/test_nqe_sql_agent_graph_skeleton.py`
结果：通过，无输出。

5. CLI 物流单域 dry-run：
`/opt/anaconda3/bin/python3 scripts/sync_nqe_metadata.py --catalog-root backend/app/domains/logistics/config/nl2sql_catalog --domain logistics --metadata-version nqe_catalog_logistics_verify --output-json tmp/hermes/nqe_watchdog/t_9c5f1f49_logistics_summary.json`
结果：domains=["logistics"], counts: tables=8, columns=93, metrics=26, dimensions=18, business_rules=6, retrieval_chunks=151, quality_gate_status=passed。

6. 禁止项扫描：
- 外部参考项目名扫描：0 matches。
- scoped 文件 credential/path 关键词扫描：未发现真实 host/user/password/dsn/token/api key/secret 连接值；命中均为安全测试词或既有 `user_visible_response` 字段名。

## 修改文件
- `backend/app/services/nqe_metadata_sync.py`
- `backend/app/domains/business_qa_graph/nqe_sql_agent_graph.py`
- `scripts/sync_nqe_metadata.py`
- `tests/unit/nqe/test_nqe_metadata_sync.py`
- `tests/unit/business_qa_graph/test_nqe_sql_agent_graph_skeleton.py`
- `ai/outbox/kanban/t_9c5f1f49/red-test.log`
- `ai/outbox/kanban/t_9c5f1f49/test.log`
- `ai/outbox/kanban/t_9c5f1f49/diff.patch`
- `ai/outbox/kanban/t_9c5f1f49/final-acceptance.md`
- `ai/outbox/kanban/t_9c5f1f49/rollback.md`

## 阶段边界
- 未接真实 DB、未读取 `.env`、未进行 SAP/Oracle/live DB 访问。
- 未执行真实 LLM 调用、未执行真实 SQL。
- 未改 frontend，未改 docs 状态文件，未改物管/SAP MID 状态文件。
- 未删除旧链路；Graph 仍保留 fallback / shadow / safety / validation / trace 边界。
- 未 commit / push / deploy。

## 风险与后续
1. 本卡只完成物流静态元数据同步与 Graph 上下文接入，不代表正式主链路已替换旧物流问答。
2. 后续 NQE-SQL-MAIN 卡仍需接入真实多路召回、SQL 生成、只读执行、shadow compare 和 replay 验收。
3. 当前 worktree 中 NQE 系列文件整体处于 untracked 状态，`diff.patch` 以 `/dev/null` 对 scoped 文件生成，用于卡级审阅；正式合入前需统一整理 NQE 系列分支/暂存范围。
