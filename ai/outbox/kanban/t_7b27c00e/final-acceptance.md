# t_7b27c00e / NQE-SQL-MAIN-13 最终验收

## 1. 当前结论

通过。`NQE-SQL-MAIN-13: trace / query log / replay` 的 review-blocked 问题已处理，可标记完成。

## 2. 阻塞原因

本卡不是 wrong-cwd 或 watchdog 调度异常，而是独立 review 发现真实交付阻塞：

1. EXPLAIN 离线校验放过 `SELECT *`，可能导致过宽字段在只读执行前未被拦截。
2. EXPLAIN 离线校验只检查 SELECT 投影字段，没有校验 WHERE 条件字段，`WHERE missing_metric = 1` 可绕过。
3. replay_record 原先会持久化原始上下文，存在 client/user/retrieval 上下文扩散风险。
4. outbox `diff.patch` 没有包含未跟踪依赖 `nqe_sql_safety.py`，导致 scoped patch 不完整。

## 3. 修复内容

### 3.1 EXPLAIN 校验

- 新增通配投影检测：`SELECT *`、`对象.*` 进入 `select_star_not_allowed`。
- 新增 WHERE 条件字段抽取与字段白名单比对。
- SELECT 投影字段与 WHERE 过滤字段统一进入字段级解释校验。
- 解释校验仍不连接真实数据库，不执行真实 EXPLAIN，只做确定性元数据预检。

### 3.2 replay 脱敏

- 持久化 replay_input 不再保存原始 `client_context`、`user_context`、`retrieval_context_package`。
- 原始问题替换为脱敏重放问题，占位字段保留摘要。
- replay_context_summary 只保存问题摘要、长度、上下文是否存在、是否发现敏感键等低敏信息。
- replay 重放时在内存中合成最小上下文，只验证终态、节点顺序和关键摘要。

### 3.3 outbox patch 完整性

已重新生成：

- `diff.patch`
- `diff_stat.txt`
- `test.log`
- `static-scan.log`

`diff.patch` 已包含 NQE 独立 Graph 运行所需的未跟踪依赖：

- `backend/app/domains/business_qa_graph/nqe_sql_safety.py`

## 4. 验收命令

```bash
PYTHONPATH=. /opt/anaconda3/bin/python3 -m pytest tests/unit/business_qa_graph/test_nqe_sql_agent_explain_correct.py tests/unit/business_qa_graph/test_nqe_sql_agent_trace_replay.py -q
PYTHONPATH=. /opt/anaconda3/bin/python3 -m pytest tests/unit/business_qa_graph/test_nqe_sql_agent_graph_skeleton.py tests/unit/business_qa_graph/test_nqe_sql_agent_safety_precheck.py tests/unit/business_qa_graph/test_nqe_sql_agent_explain_correct.py tests/unit/business_qa_graph/test_nqe_sql_agent_trace_replay.py -q
PYTHONPATH=. /opt/anaconda3/bin/python3 -m py_compile backend/app/domains/business_qa_graph/nqe_sql_agent_graph.py backend/app/domains/business_qa_graph/nqe_sql_agent_trace.py backend/app/domains/business_qa_graph/nqe_sql_agent_state.py backend/app/domains/business_qa_graph/nqe_sql_safety.py tests/unit/business_qa_graph/test_nqe_sql_agent_explain_correct.py tests/unit/business_qa_graph/test_nqe_sql_agent_trace_replay.py
git diff --check
PYTHONPATH=. /opt/anaconda3/bin/python3 tmp/hermes/nqe13_recovery/probe_review_blockers.py
```

## 5. 验收结果

| 验收项 | 结果 |
|---|---:|
| review blocker tests | 8 passed, 7 warnings |
| NQE focused tests | 31 passed, 7 warnings |
| py_compile | passed |
| git diff --check | passed |
| manager probe | passed |
| scoped static scan | issue_count=0 |

## 6. Manager probe 结果

| 探针 | 结果 |
|---|---|
| `SELECT * FROM nqe_safe_metric_view` | error / `select_star_not_allowed` |
| `SELECT metric_value ... WHERE missing_metric = 1` | error / `unknown_column` |
| 正常候选 `SELECT metric_value ...` | completed |
| replay secret marker | false |

## 7. 独立 Review

已追加独立 scoped review：`ai/outbox/kanban/t_7b27c00e/review-result.json`。

Review 结论：

- `passed=true`
- `blockers=[]`
- `security_concerns=[]`
- 复核项包含 focused pytest、py_compile、git diff --check、手工 graph probes、临时仓库 `git apply --check`。

## 8. 边界确认

未执行：

- 未连接真实数据库。
- 未读取 `.env`。
- 未改前端。
- 未改物管 / SAP MID 状态文件。
- 未修改 `docs/HANDOFF.md`、`docs/CURRENT_STATUS.md`、`docs/NEXT_TASK.md`。
- 未 commit / push / deploy。

## 9. 风险点

- 当前仍是 NQE 独立 Graph 骨架和离线确定性校验，不代表正式入口已切换。
- replay 为脱敏重放，只验证路径和摘要一致性，不复原真实召回上下文。
- 全量旧 `business_qa_graph` 邻接回归仍存在历史失败，前次 review 判断不属于本卡新增 scoped 文件引入。
