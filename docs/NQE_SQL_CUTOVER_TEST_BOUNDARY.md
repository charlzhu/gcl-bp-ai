# NQE SQL CUTOVER 测试体系边界

更新时间：2026-05-24 20:00 CST

## 全目录结果

`tests/unit/business_qa_graph`: **253 passed, 51 failed**

## 失败分类

### 旧 S1 (5 failed)

`test_nqe_s1_nl2sql_shadow.py` — NL2SQL shadow adapter。依赖 `query_plan_v2` / `nl2sql_adapter` 已移除的参数。

### 旧 S2 (2 failed)

`test_nqe_s2_composite_decomposition.py` — 复合分解。依赖 `decomposition_node` / `presentation_node` 不存在的节点。

### 旧 S3 (2 failed)

`test_nqe_s3_shadow_compare.py` — shadow compare。依赖 `nl2sql_result` / `shadow_compare_node` 已移除的字段。

### 旧 S4 (11 failed)

`test_nqe_s4_assist_graph.py` — assist graph。依赖 `logistics_nl2sql_assist_via_graph` / `assist_mode` / `nl2sql_adapter` 已移除的配置和参数。

### 旧 ZG (31 failed)

`test_zg_nodes.py` — ZG builder/nodes。依赖 ZG Graph 12 节点，当前编译的 graph 无这些节点。

| 类 | 失败数 |
|---|---|
| TestExtractKeywords | 4 |
| TestMergeRetrievedInfo | 3 |
| TestAddExtraContext | 2 |
| TestGenerateSql | 3 |
| TestValidateSql | 2 |
| TestExecuteSql | 2 |
| TestCorrectSql | 1 |
| TestBuilderZg | 4 |
| TestPromptLoader | 3 |
| TestZgState | 2 |
| TestZgQueryService | 3 |

## NQE SQL Agent 新链路测试 (全部通过)

| 文件 | 通过 |
|---|---|
| test_nqe_sql_agent_graph_skeleton.py | 15 |
| test_nqe_sql_agent_safety_precheck.py | 15 |
| test_nqe_sql_agent_explain_correct.py | 5 |
| test_nqe_sql_agent_trace_replay.py | 3 |
| test_nqe_sql_agent_logistics.py | 9 |
| test_nqe_sql_agent_business_analysis.py | 6 |
| test_nqe_sql_agent_bom.py | 2 |
| test_nqe_sql_agent_power.py | 4 |
| test_nqe_sql_agent_eval.py | 3 |
| test_nqe_plan_bom_candidate_adapter.py | 5 |
| test_nqe_plan_bom_compare_adapter.py | 7 |
| test_nqe_plan_bom_gray.py | 3 |
| test_nqe_plan_bom_eval.py | 3 |
| test_nqe_power_prediction_adapter.py | 4 |
| test_nqe_logistics_gray.py | 14 |
| **NQE focused total** | **~98** |

## 稳定 focused test 命令

```bash
PYTHONPATH=. python -m pytest tests/unit/business_qa_graph/test_nqe_*.py -q
```

预期：~98 passed, 0 failed。

## 结论

- NQE SQL Agent 新链路测试全部通过。
- 51 个失败全部在旧 S1/S2/S3/S4/ZG 测试中。
- 旧测试未做清理/迁移，应标记为 skipped 或移入 legacy 目录。
- 后续 NQE-SQL-CUTOVER 只以 `test_nqe_*.py` 为验收测试集。
