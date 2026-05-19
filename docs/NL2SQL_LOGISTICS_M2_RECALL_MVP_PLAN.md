# 物流 NL2SQL M2 Milvus 语义召回 MVP 计划

> **For Hermes:** 本计划用于当前看板任务 `t_4a5d380f`。实现必须遵守 TDD：先写失败测试，再补最小实现。

**Goal:** 在不接管正式物流 QA 查询链路的前提下，为物流 NL2SQL shadow SQLPlan 链路提供可索引、可召回、可精排、可审计、fail-closed 的 Semantic Catalog M2 能力。

**Architecture:** M2 只把现有 `Semantic Catalog` 转换为受控召回文档，写入本地 Docker Milvus，并在查询时通过 embedding + Milvus + rerank 返回带 `catalog_id/catalog_version` 的上下文片段。M2 不生成 SQL、不执行 SQL、不查询业务库；后续 M3 SQLPlan 只能通过 `catalog_id` 回查受控 catalog。

**Tech Stack:** Python 3.11、Pydantic v2、PyYAML、pymilvus（requirements 锁定 2.3.5，当前 venv 为 2.5.2，代码需避免使用 2.5 专属 API）、OpenAI-compatible embedding 客户端、百炼 Qwen3-Embedding-4B、百炼 Qwen3-Reranker。

---

## 0. 当前真实代码状态

- 已有 M1 catalog loader：`backend/app/domains/logistics/services/nl2sql/semantic_catalog.py`。
- 已有 catalog YAML：`backend/app/domains/logistics/config/nl2sql_catalog/{tables,metrics,dimensions,joins,rules}.yaml`。
- 已有 Query Planner V2 安全边界：`query_planner_v2/prompt_builder.py` 明确禁止 SQL/where/table_name/answer 等字段，`validator.py` 对 query_key/filter/metric/dimension/time/fallback 做 fail-closed。
- `backend/app/core/config.py` 已有 Milvus/LLM 基础字段，但缺少 M2 使用的 `embedding_model`、`rerank_model`、`embedding_dimension` 等配置；已有 `MILVUS_COLLECTION_PREFIX` property 但字段缺失。
- 本地 Milvus 可连接：`http://localhost:19530`，当前 collection 为空。

## 1. MVP 文件边界

### 新增

- `backend/app/domains/logistics/services/nl2sql/catalog_retrieval.py`
  - catalog -> recall document 转换；
  - embedding client 抽象；
  - Milvus vector store 抽象；
  - rerank client 抽象；
  - recall/index service 编排；
  - 黑名单与 fail-closed 校验。
- `tests/unit/logistics/nl2sql/test_catalog_retrieval.py`
  - focused TDD 单测，全部使用 mock embedding/Milvus/rerank，不访问外网或真实 Milvus。
- `scripts/reindex_logistics_nl2sql_catalog.py`
  - 支持 `--dry-run` 仅打印待索引文档数量；真实重建时才连接 embedding/Milvus。
- `docs/NL2SQL_LOGISTICS_M2_RECALL_MVP_PLAN.md`
  - 本文档。

### 修改

- `backend/app/core/config.py`
  - 新增 M2 配置项：`embedding_model`、`embedding_dimension`、`rerank_model`、`rerank_endpoint_path`、`milvus_collection_prefix`、`nl2sql_recall_top_k`、`nl2sql_rerank_top_k`、`nl2sql_rerank_min_score`。
- `backend/.env.example`
  - 增加 M2 示例配置，不写真实密钥。
- `backend/app/domains/logistics/services/nl2sql/__init__.py`
  - 导出 M2 入口类。

## 2. 召回文档 schema

每个 Milvus payload 必须包含：

- `catalog_id`：稳定 ID，例如 `metric:shipment_mw`、`dimension:city`、`table:dws_logistics_detail_union`、`column:dws_logistics_detail_union.city`。
- `catalog_version`：来自 YAML 顶层，例如 `logistics_nl2sql_catalog.v1`。
- `doc_type`：`table | column | metric | dimension | rule | join`。
- `title`：业务标题。
- `content`：用于 embedding/rerank 的短文本，限长，不包含可执行 SQL。
- `keywords`：同义词、业务名、字段名、指标 ID 等。
- `source_table`：可选表名。
- `metadata`：受控元信息，例如 `metric_id`、`dimension_id`、`source_columns`、`join_id`；不得放真实密钥、连接串、自由 SQL。

## 3. Collection 命名与 schema

- collection name：`{milvus_collection_prefix}_logistics_nl2sql_catalog`。
- vector field：`vector`，dimension 从 `embedding_dimension` 读取。
- scalar fields：`doc_id`、`catalog_id`、`catalog_version`、`doc_type`、`title`、`content`、`keywords_json`、`metadata_json`、`source_table`。
- index metric：`COSINE`。

## 4. Index / Recall 流程

### Index

1. 加载 `LogisticsSemanticCatalogLoader().load()`；
2. `LogisticsCatalogRecallDocumentBuilder.build(catalog)` 生成文档；
3. fail-closed 校验每个文档：禁止 `sys_query_log`、`V_SAP_*`、`ods_*`、`sap_mid`、`oracle_mid` 等非中间库/非白名单来源进入索引；
4. embedding client 批量生成向量；
5. Milvus store 创建 collection 并 upsert 文档。

### Recall

1. 输入原始问题、可选标准化问题、可选槽位摘要；
2. 去重后组合查询文本，生成 embedding；
3. Milvus topK 检索；
4. 校验命中 payload，若发现黑名单文档直接 fail-closed；
5. 按 `catalog_id` 去重，保留最高向量分；
6. Reranker 对候选文档重排；
7. 按 `nl2sql_rerank_top_k` 和 `nl2sql_rerank_min_score` 截断；
8. 返回只包含 catalog 元信息和业务文本的 `LogisticsCatalogRecallResult`。

## 5. 与 SQLPlan / 正式 QA 的边界

- M2 输出不能进入正式 Data QA 执行路径，只能给 shadow SQLPlan 生成链路使用。
- M2 不接受 LLM 生成的 SQL、where、表名自由输入或计算结果。
- 后续 SQLPlan 生成必须只引用 `catalog_id`，再由后端从 Semantic Catalog 回查受控表/字段/指标。
- 用户可见回答不得展示 `catalog_id`、SQL、schema、raw/debug、LLM、planner、query_key。

## 6. TDD 任务拆分

### Task 1: 召回文档转换

- 测试：catalog loader 加载真实 YAML 后，应生成 metric/dimension/rule/table/column/join 文档，且每条有 `catalog_id/catalog_version/doc_type/content`。
- 实现：`LogisticsCatalogRecallDocument` + `LogisticsCatalogRecallDocumentBuilder`。

### Task 2: 黑名单 fail-closed

- 测试：`sys_query_log`、`V_SAP_HFFN_EKKO`、`ods_logistic_ship_task`、`source_system=sap_mid/oracle_mid` 不能构造成召回文档，也不能作为 Milvus hit 返回。
- 实现：文档模型 validator + recall hit 解析校验。

### Task 3: mock embedding + mock Milvus index

- 测试：fake embedding 收到文档内容，fake vector store 收到同数量向量与 payload；缺 embedding 配置时不调用 store。
- 实现：`LogisticsBailianEmbeddingClient`、`LogisticsMilvusCatalogVectorStore`、`LogisticsCatalogRecallService.index_catalog()`。

### Task 4: mock Milvus recall + mock rerank

- 测试：fake vector store 返回重复候选，服务按 `catalog_id` 去重并用 fake reranker 排序、限长、保留 `vector_score/rerank_score`。
- 实现：`LogisticsBailianRerankClient`、`LogisticsCatalogRecallService.recall()`。

### Task 5: 脚本与配置

- 测试/验证：`--dry-run` 不访问外部服务并能打印文档数量；settings 能读取新增配置。
- 实现：reindex 脚本、`.env.example`、`config.py`。

## 7. 验证命令

```bash
backend/.venv/bin/python -m pytest tests/unit/logistics/nl2sql/test_catalog_retrieval.py -q
backend/.venv/bin/python -m pytest tests/unit/logistics/nl2sql/test_semantic_catalog.py tests/unit/logistics/query_planner_v2/test_logistics_query_planner_v2.py -q
backend/.venv/bin/python -m py_compile backend/app/domains/logistics/services/nl2sql/catalog_retrieval.py scripts/reindex_logistics_nl2sql_catalog.py
backend/.venv/bin/python scripts/reindex_logistics_nl2sql_catalog.py --dry-run
```

## 8. 验收产物

- `ai/outbox/kanban/t_4a5d380f/test.log`
- `ai/outbox/kanban/t_4a5d380f/diff.patch`
- `ai/outbox/kanban/t_4a5d380f/final-acceptance.md`
- 独立 review JSON/摘要。
