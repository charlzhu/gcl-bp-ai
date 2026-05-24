# NQE-SQL-MAIN-7 元数据同步脚本最终验收

## 1. 修改文件清单

本轮新增文件：

1. `backend/app/services/nqe_metadata_sync.py`
2. `scripts/sync_nqe_metadata.py`
3. `tests/unit/nqe/test_nqe_metadata_sync.py`
4. `ai/outbox/kanban/t_c8b38b1a/test.log`
5. `ai/outbox/kanban/t_c8b38b1a/dry-run-summary.json`
6. `ai/outbox/kanban/t_c8b38b1a/final-acceptance.md`

本轮未修改正式问答入口、Graph 节点、业务 domain service、prompt、frontend、状态文档、模型或迁移文件。

## 2. 关键实现说明

1. 新增 `NqeMetadataSyncBundle`，统一承载 domains、data_sources、tables、columns、metrics、dimensions、business_rules、retrieval_chunks、metadata_versions、quality_gates 与 warnings。
2. 新增 `NqeMetadataSyncBuilder`，默认读取 `backend/app/domains/logistics/config/nl2sql_catalog/`，支持 root logistics、`business_analysis`、`plan_bom` 三类 catalog。
3. catalog 缺少某类 YAML 时按 fail-soft 处理：记录 warnings，并把质量门禁标记为 `warn`，不抛不可恢复异常。
4. `source_ref` 只保存相对 catalog 路径，不保存本机绝对路径或连接信息。
5. `extra_json`、`keywords_json`、`synonyms_json` 均使用 `ensure_ascii=False` 输出 JSON 字符串。
6. `code` 与 `chunk_code` 使用稳定业务键和 sha256 短 hash 截断，长度控制在 128 以内。
7. `build_retrieval_chunks` 覆盖 table、column、metric、dimension、rule 五类召回文本。
8. `upsert_nqe_metadata_bundle(session, bundle)` 按各模型 `code` 幂等 upsert，不执行删除，不依赖生产数据库。
9. CLI `scripts/sync_nqe_metadata.py` 默认 dry-run；只有显式传入 `--apply-sqlite` 时才写本地 SQLite 文件。

## 3. Dry-run 统计摘要

输出文件：`ai/outbox/kanban/t_c8b38b1a/dry-run-summary.json`

```json
{
  "domains": ["logistics", "business_analysis", "plan_bom"],
  "metadata_version": "nqe_catalog_v1",
  "quality_gate_status": "passed",
  "warnings": [],
  "counts": {
    "domains": 3,
    "data_sources": 3,
    "tables": 19,
    "columns": 226,
    "metrics": 65,
    "dimensions": 51,
    "business_rules": 21,
    "retrieval_chunks": 382,
    "metadata_versions": 1,
    "quality_gates": 1
  }
}
```

## 4. 测试命令与结果

完整输出保存于：`ai/outbox/kanban/t_c8b38b1a/test.log`

已执行：

1. `/opt/anaconda3/bin/python3 -m pytest tests/unit/nqe/test_nqe_metadata_models.py tests/unit/nqe/test_nqe_metadata_sync.py -q`
   - 结果：`9 passed`
2. `/opt/anaconda3/bin/python3 -m py_compile backend/app/services/nqe_metadata_sync.py scripts/sync_nqe_metadata.py`
   - 结果：通过，无编译错误。
3. `/opt/anaconda3/bin/python3 scripts/sync_nqe_metadata.py --output-json tmp/hermes/nqe7_verify/dry-run-summary.json`
   - 结果：通过，生成 dry-run JSON 摘要。
4. `git diff --check`
   - 结果：通过，无空白检查问题。

## 5. 风险点与未解决事项

1. 用户卡片指定的以下设计文档在当前 worktree 的 `docs/` 路径下未找到：
   - `docs/NQE_SQL_MAIN_2_METADATA_KB_DESIGN.md`
   - `docs/NQE_SQL_MAIN_3_RETRIEVAL_DESIGN.md`
   - `docs/NQE_SQL_MAIN_5_SQL_SAFETY_DESIGN.md`
2. 本轮实现依据为用户任务卡、当前 `backend/app/models/nqe_metadata.py` 模型字段，以及受控 catalog/YAML 现状。
3. Python catalog `semantic_catalog.py` 本轮仅只读理解形态，实际同步以现有 YAML catalog 为主。
4. 本轮只生成 NQE 元数据和召回 chunk，不生成向量索引；向量索引留给 NQE-SQL-MAIN-8。
5. 本轮不执行删除，旧版本元数据清理和发布/回滚策略需后续卡片继续收口。

## 6. 对现有主链路影响

1. 物流现有主链路：未修改。
2. 计划 BOM 现有主链路：未修改。
3. 经营分析现有主链路：未修改。
4. 物管现有主链路：未修改。
5. 前端：未修改。

## 7. 边界确认

1. 未连接生产库。
2. 未读取 `.env` 中真实连接信息。
3. 未调用外部服务。
4. 未全量扫描业务大表。
5. 未让 LLM 自由生成或执行 SQL。
6. 未替换任何正式问答链路。
7. 未修改 frontend。
8. 未覆盖 `docs/CURRENT_STATUS.md`、`docs/NEXT_TASK.md`、`docs/HANDOFF.md`。
9. 未自动 commit。
10. 未 push。
11. 未 deploy。
