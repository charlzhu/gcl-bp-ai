# gcl-bp-ai: NL2SQL M2 Milvus 语义召回启动 - Final Acceptance

## 结论

任务已从 stopped/blocked 状态补完，建议判定为完成。

## 停止原因分析

看板日志显示任务停止不是业务决策停止，而是 worker 达到迭代预算上限：`Iteration budget exhausted (90/90)`。停止时补丁已有主体，但未百分百完成；现场复跑发现 focused test 和 dry-run 均失败。

## 根因

1. `catalog_retrieval.py` 引用了 `_iter_payload_strings` 等 payload 安全扫描 helper，但实现缺失，导致 recall 文档构建和 dry-run 报 `NameError`。
2. Milvus collection schema 仍需显式声明 string primary key、vector field 和 vector index。
3. Milvus hit 信任边界需要补强：召回命中返回前必须按当前 catalog_id/catalog_version 回查 canonical catalog，不能信任向量库 payload。
4. 初版测试存在 DSN 脱敏伪绿风险，且 payload 需过滤 SAP/source-system 技术字段。

## 已完成修复

- 新增物流 NL2SQL M2 Semantic Catalog 文档构建、embedding、Milvus vector store、rerank、recall service 和 reindex dry-run/索引脚本。
- Milvus payload 只保存业务安全 catalog 文档：过滤 `sap_order_no`/SAP、sys_query_log、ODS、Oracle MID 等来源系统技术字段；join 文档不保存 `join.on` 和等号条件，只保留业务描述与条件数量。
- Recall hit 按 allow-list catalog_id 和 catalog_version fail-closed，并重建 canonical document 后再进入 rerank/返回。
- 异常信息返回前脱敏 password/token/DSN。
- `.env.example`/Settings 增加 M2 embedding/rerank/Milvus 参数占位；`requirements.txt` 增加真实 embedding 依赖 `openai==2.16.0`，未新增无关 Oracle 驱动。
- `scripts/reindex_logistics_nl2sql_catalog.py` 支持 `--dry-run`，非 dry-run 输出兼容 pydantic 2.9，不使用 `model_dump_json(..., ensure_ascii=...)`。
- 输出验收材料：`diff.patch`、`test.log`、`static-scan.json`、`final-acceptance.md`。

## 测试结果

- `pytest tests/unit/logistics/nl2sql/test_catalog_retrieval.py -q`：15 passed
- `pytest tests/unit/logistics/nl2sql/test_semantic_catalog.py tests/unit/logistics/query_planner_v2/test_logistics_query_planner_v2.py -q`：32 passed
- `pytest tests/unit/logistics -q`：47 passed
- `pytest tests/unit -q`：91 passed
- `py_compile catalog_retrieval.py reindex_logistics_nl2sql_catalog.py`：通过
- `scripts/reindex_logistics_nl2sql_catalog.py --dry-run`：通过，125 docs
- `git diff --check`：通过
- static scan：passed，无 findings

## 独立 Review

最终独立 reviewer 结论：`passed=true`，无 security_concerns，无 logic_errors。

## 阶段边界确认

本次仍限定在 NL2SQL M2 语义召回启动能力：不接正式 QA、不生成 SQL、不执行业务库、不改前端、不影响现有物流/BOM 主链路。

## 建议下一步

不建议启动别的任务跳过 M2；本轮已把 M2 剩余阻塞补完。下一步可进入 M3：SQL Plan/SQL 生成前的召回接入设计与安全门禁扩展，但应先由用户确认。