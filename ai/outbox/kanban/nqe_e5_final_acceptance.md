# NQE-E5 评测结果一致性评估 —— 最终验收

## 任务目标
在 EvaluationReport 中新增一致性校验逻辑：状态、数值、口径、技术泄露。
评测结果按 fail/pass/warning 三级分级。

## 修改清单

| 文件 | 改动说明 |
|------|---------|
| `backend/app/domains/qa_evaluation/schema.py` | 新增 ConsistencyGrade 类型（Literal["pass","fail","warning"]）；EvaluationResult 新增 consistency_grade 和 numeric_error_pct 字段；EvaluationReport 新增 evaluate_consistency() 和 _grade_one() 方法 |
| `backend/app/domains/qa_evaluation/eval_runner.py` | run() 中调用 report.evaluate_consistency() 自动分级 |
| `backend/app/domains/qa_evaluation/__init__.py` | 导出 ConsistencyGrade |
| `tests/unit/qa_evaluation/test_e5_consistency.py` | 新增 23 个 focused tests |

## 一致性分级规则

| 级别 | 触发条件 |
|------|---------|
| **fail** | leak_found=True 或 matched_status=False 或 key_numbers_match=False |
| **warning** | 不满足 fail，且（text_similarity < 0.5 或 numeric_error_pct > 0.10） |
| **pass** | 不满足以上任一条件 |

fail 优先级高于 warning。阈值边界值（0.5 / 0.10）属于 pass。

## 测试结果

```
tests/unit/qa_evaluation/ — 88 passed (23 E5 + 30 E2 + 35 E1)
business_qa_graph 回归：154 passed（12 个预存失败，非本次引入）
```

| 测试类 | 数量 | 状态 |
|--------|------|------|
| test_e5_consistency.py | 23 | ✅ 全通过 |
| test_evaluation_schema.py | 35 | ✅ 全通过 |
| test_eval_runner.py | 20 | ✅ 全通过 |
| test_plan_bom_eval.py | 10 | ✅ 全通过 |

## 验收检查

- [x] RED：23 个 focused tests 先验证失败（字段/方法缺失）
- [x] GREEN：实现最小代码，23/23 通过
- [x] 相邻回归：E1+E2 全量通过（88/88）
- [x] Compile 检查：schema.py/__init__.py/eval_runner.py 均通过 py_compile
- [x] 独立 review：passed=true，无安全问题
- [x] 中文注释：全部新增代码中文注释
- [x] 未破坏基线：物流/计划BOM/功率预测主链路未受影响
- [x] 未暴露技术细节：新增字段不含 SQL/表名/query_key 等

## 已知局限（下一卡处理）

- `numeric_error_pct` 字段已定义但 `_evaluate_case()` 尚未计算填充（需从答案中提取数值比对）
- 建议后续卡（NQE-E6）实现实际的数值误差计算逻辑

## 材料路径

- `ai/outbox/kanban/nqe_e5_diff.patch` — 完整 diff
- `ai/outbox/kanban/nqe_e5_test.log` — 测试日志
- `ai/outbox/kanban/nqe_e5_review_result.json` — 独立 review 结果
- `ai/outbox/kanban/nqe_e5_final_acceptance.md` — 本文件
