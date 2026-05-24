# NQE-SQL-MAIN-8：Milvus 元数据向量索引验收报告

## 1. 修改文件清单

1. `backend/app/services/nqe_metadata_vector_index.py`
   - 新增 NQE 元数据向量索引文档、摘要、document builder 和索引编排服务。
2. `scripts/reindex_nqe_metadata_chunks.py`
   - 新增默认 dry-run 的 NQE retrieval chunk 重建索引 CLI。
3. `tests/unit/nqe/test_nqe_metadata_vector_index.py`
   - 新增 focused 单测，覆盖构建、幂等、dry-run、fake apply、fail-closed、CLI 与脱敏边界。
4. `ai/outbox/kanban/t_cceeff7b/test.log`
   - 保存本轮指定测试、编译、dry-run 和 diff check 输出。
5. `ai/outbox/kanban/t_cceeff7b/dry-run-summary.json`
   - 保存本轮 dry-run 待索引统计。
6. `ai/outbox/kanban/t_cceeff7b/final-acceptance.md`
   - 本验收报告。

## 2. 关键实现说明

1. `NqeMetadataIndexDocumentBuilder` 复用 NQE-7 `NqeMetadataSyncBundle.retrieval_chunks`，将 chunk 标准化为 NQE 专用索引文档。
2. document id 使用 `chunk_code + content_hash` 的 sha256 稳定生成，长度不超过 128。
3. content 优先取 `chunk_text`，最长 4096 字符；超长文本截断并写入 warning。
4. `keywords_json`、`synonyms_json`、`extra_json` 采用安全 JSON 解析，解析失败只记录 warning，不抛异常。
5. `source_ref` 和 metadata 会过滤本机绝对路径、连接配置关键词、密钥类关键词，不写入真实连接信息。
6. `NqeMetadataVectorIndexService.index_documents(..., apply=False)` 不调用 embedding client 或 vector store，只返回统计。
7. `apply=True` 只使用显式注入的 `embedding_client` 和 `vector_store`；缺依赖、批大小非法、embedding 数量不一致或写入异常均 fail-closed。
8. CLI 默认 dry-run，不读取 `.env`，不创建真实 Milvus/embedding 客户端；`--apply-milvus` 缺显式安全依赖时返回非 0。

## 3. dry-run 统计摘要

```json
{
  "documents": 382,
  "domains": {
    "business_analysis": 98,
    "logistics": 151,
    "plan_bom": 133
  },
  "asset_type_counts": {
    "column": 226,
    "dimension": 51,
    "metric": 65,
    "rule": 21,
    "table": 19
  },
  "metadata_version": "nqe_catalog_v1",
  "dry_run": true,
  "apply_status": "dry_run",
  "indexed": 0,
  "warnings": [],
  "errors": []
}
```

## 4. 测试命令与结果

1. `/opt/anaconda3/bin/python3 -m pytest tests/unit/nqe/test_nqe_metadata_models.py tests/unit/nqe/test_nqe_metadata_sync.py tests/unit/nqe/test_nqe_metadata_vector_index.py -q`
   - 结果：`17 passed in 2.57s`
2. `/opt/anaconda3/bin/python3 -m py_compile backend/app/services/nqe_metadata_vector_index.py scripts/reindex_nqe_metadata_chunks.py`
   - 结果：通过，无输出。
3. `/opt/anaconda3/bin/python3 scripts/reindex_nqe_metadata_chunks.py --output-json tmp/hermes/nqe8_verify/dry-run-summary.json`
   - 结果：通过，生成 382 条待索引文档统计。
4. `git diff --check`
   - 结果：通过，无输出。

详细日志见：`ai/outbox/kanban/t_cceeff7b/test.log`。

## 5. 风险点与未解决事项

1. 本轮未接入真实 embedding provider 或真实 Milvus；真实写入仍需后续在受控环境中显式注入安全客户端并做 provider smoke。
2. 当前 `--apply-milvus` 为 fail-closed 边界，避免默认读取 `.env` 或真实连接配置；后续若要真实写入，需要另卡实现脱敏配置加载与真实 adapter。
3. 向量索引仅作为召回加速和语义匹配候选来源，主事实仍应以 MySQL `nqe_*` 元数据表为准。
4. 本轮没有替换正式召回/问答链路，也没有验证线上 Milvus collection schema。

## 6. 对现有主链路影响

1. 物流主链路：未修改。
2. 计划 BOM 主链路：未修改。
3. 经营分析主链路：未修改。
4. 物管现有主链路：未修改。
5. frontend：未修改。
6. `docs/CURRENT_STATUS.md`、`docs/NEXT_TASK.md`、`docs/HANDOFF.md`：未覆盖。

## 7. 发布与提交状态

1. 未连接生产 Milvus。
2. 未读取真实连接凭证。
3. 未写入或打印真实 host、user、password、DSN、Token、API Key 或代理地址。
4. 未自动 commit。
5. 未 push。
6. 未 deploy。
