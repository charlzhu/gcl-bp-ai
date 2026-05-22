# NQE-E4 最终验收报告

## 任务
让 Graph 可自动运行功率评测集并生成报告。

## 完成内容

### 1. 新增评测样例
- **文件**: `tests/evaluation/plan_power/__init__.py` — 模块初始化，含业务说明
- **文件**: `tests/evaluation/plan_power/samples.py` — 首批评测样例集（10条），含 `load_power_suite()` 入口
- 覆盖场景:
  - 功率预测（plan_power_prediction）：2条
  - 供应商推荐（plan_power_supplier_recommendation）：2条
  - 配置影响值对比（plan_power_factor_effect_compare）：2条
  - 澄清场景（缺少关键槽位）：2条
  - 暂不支持场景（导出/全量计算）：2条

### 2. EvalGraphRunner 支持 power_prediction 域
- domain_registry.py 已内置 `"power_prediction" → "plan_bom"` 路由映射（NQE-E3 已完成）
- EvalGraphRunner 无需修改：power_prediction domain 的评测套件通过 `domain_hint` 自动路由到 plan_bom 域执行

### 3. 新增 Focused Tests（2条）
- `test_eval_runner_power_prediction_domain_suite`: 验证 power_prediction 域套件能被 EvalGraphRunner 正确执行
- `test_power_evaluation_samples_loadable`: 验证功率评测样例可从 tests/evaluation/plan_power/ 加载

### 4. 不改变现有功率能力
- 未修改任何功率预测/供应商推荐/配置影响对比的确定性计算逻辑
- 未修改 LQG-7 execute_node_power 的执行链路

## 测试结果

| 测试集 | 用例数 | 通过 | 失败 |
|--------|--------|------|------|
| test_eval_runner.py | 19 | 19 | 0 |
| test_business_qa_graph_skeleton (power路由) | 2 | 2 | 0 |
| test_lqg7_execute_node_power.py | 11 | 11 | 0 |
| **合计** | **32** | **32** | **0** |

预存失败（12条，与本卡无关）：`logistics_nl2sql_assist_via_graph` 未在 worktree config 中配置、LQ8 unified_stream 端点注册、NQE-S4 assist graph 测试等。

## 验收标准

| 标准 | 状态 | 说明 |
|------|------|------|
| 评测 runner 可对功率评测集做自动评估 | ✅ | EvalGraphRunner 已支持 power_prediction domain |
| 输出评测报告 | ✅ | 通过 fake GraphRunner 验证 JSONL 输出正常 |
| 不改变现有功率能力 | ✅ | 未修改确定性计算链路 |
| 新增 focused tests | ✅ | 2条新测试均通过 |
| 中文注释 | ✅ | 所有文件含中文注释 |

## 交付物

- `ai/outbox/kanban/nqe_e4_diff.patch` — 变更 diff（含新文件）
- `ai/outbox/kanban/nqe_e4_test.log` — 32条 focused 测试日志
- `ai/outbox/kanban/nqe_e4_review_result.json` — 独立 review 结果
- `ai/outbox/kanban/nqe_e4_final_acceptance.md` — 本文件

## Reviewer 意见

- passed: true
- security_concerns: []
- logic_errors: []
- suggestions: __init__.py 函数名引用已修正
