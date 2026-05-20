# 当前进度与遗留问答

## 当前进度

- 已创建看板任务：`t_236bba5f`。
- 已创建独立 worktree：`/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/nl2sql-m10-preflight-revalidation`。
- 分支：`feature/nl2sql-m10-preflight-revalidation`。
- 本任务定位：M10 启动前 M9 当前树复核，非代码开发。

## 已确认通过

1. 物流 NL2SQL 单测：`190 passed, 9 warnings in 6.02s`。
2. compileall：通过。
3. git diff --check：通过。
4. fake/shadow M9 SQLPlan generation：通过。
   - total=3
   - success=2
   - validation_failed=1
   - expected_status_mismatch_count=0

## 已确认阻塞

1. provider smoke：BLOCKED。
   - Milvus：PASS。
   - embedding：缺 `llm_base_url`、`llm_api_key`、`embedding_model`。
   - rerank：缺 `llm_base_url`、`llm_api_key`、`rerank_model`。
   - LLM provider：缺 `llm_base_url`、`llm_api_key`、`llm_model`。
2. catalog reindex：BLOCKED，`embedding_unavailable`。
3. live provider shadow gate：BLOCKED，`recall_failed=1`。

## 遗留问答

1. provider 配置应该由哪个环境注入到 M9 脚本：主项目 backend `.env`、当前 worktree backend `.env`，还是 Hermes/外部环境？
2. 当前缺失配置是实际未配置，还是 worker 的独立 worktree 没有加载已有 `.env`？
3. 补齐配置后，live provider gate 是否仍能达到 M9.1 历史标准：`total=3`、`success=2`、`validation_failed=1`、`expected_status_mismatch_count=0`？
4. live gate 通过前，M10 candidate-SQL safety-gate 是否可以启动？结论：不建议启动。

## 建议下一步

先处理 provider 配置注入/读取，再重跑 M9 live gate。若只是环境配置问题，不需要代码开发；若确认脚本未按项目配置规范加载 `.env`，再创建单独的代码开发看板任务修复。
