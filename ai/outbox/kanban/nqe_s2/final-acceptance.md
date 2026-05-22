# NQE-S2 最终验收报告

## 任务信息
- 任务ID: t_75f144ba
- 标题: NQE-S2：复杂问法 decomposition 与 NL2SQL 子计划
- 分支: feature/nqe-nl2sql-graph
- 工作区: /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai-nqe-nl2sql

## 验收标准验证

### 1. 复杂问法可拆分为子计划并分别执行
- 对比型问题 "去年和今年各承运商发运量对比" → 自动拆分为 2 个子问题
- 每个子问题通过 logistics adapter 生成受控查询计划
- 子计划存入 state.sub_plans，设置 understanding_status=COMPOSITE_DECOMPOSED

### 2. 子结果合并后格式正确
- comparison 型：并排展示，标注年份
- trend 型：按时间顺序排列
- composite 型：分段展示各子结果
- 不暴露 SQL/表名/字段名/query_key 等技术细节

### 3. 现有 composite 测试不回归
- 19/19 logistics_llm_led_composite_decomposition 测试通过
- 12/12 NQE-S1 test_nqe_s1_nl2sql_shadow 测试通过

## 测试结果

| 测试组 | 数量 | 结果 |
|--------|------|------|
| NQE-S2 focused | 15 | PASS |
| NQE-S1 focused | 12 | PASS |
| Composite acceptance | 19 | PASS |
| 总计 | 46 | 46/46 PASS |

## 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| backend/app/domains/business_qa_graph/schemas/state.py | 修改 | 新增 sub_plans/sub_results/composite_type 字段，understanding_status 扩展 COMPOSITE_DECOMPOSED |
| backend/app/domains/business_qa_graph/schemas/domain.py | 修改 | 新增 logistics_composite_decomposition capability |
| backend/app/domains/business_qa_graph/services/logistics_composite_decomposer.py | 新建 | 核心分解器：确定性规则分解+校验 |
| backend/app/domains/business_qa_graph/nodes/decomposition_node.py | 新建 | 复合分解节点：检测+拆分+子计划生成 |
| backend/app/domains/business_qa_graph/nodes/presentation_node.py | 新建 | 子结果合并展示节点 |
| backend/app/domains/business_qa_graph/nodes/__init__.py | 修改 | 导出新节点 |
| backend/app/domains/business_qa_graph/builder.py | 修改 | 注册 decomposition/presentation 节点到 graph |
| backend/app/domains/business_qa_graph/nodes/execute_node.py | 修改 | 新增 _execute_logistics_composite 复合执行路径 |
| backend/app/domains/business_qa_graph/nodes/plan_validate_node.py | 修改 | 放行 COMPOSITE_DECOMPOSED 状态 |
| backend/app/domains/business_qa_graph/nodes/plan_build_node.py | 修改 | 处理 COMPOSITE_DECOMPOSED 状态 |
| tests/unit/business_qa_graph/test_nqe_s2_composite_decomposition.py | 新建 | 15 个 focused tests |

## 风险点
1. 当前分解器使用确定性规则（非 LLM），仅覆盖对比型和简单分号分隔
2. 趋势型和复杂综合型在 NQE-S2 阶段作为整体处理，待 NQE-S3 接入 LLM
3. execute_node 的复合执行路径依赖 LogisticsDataQaService.query()，需数据库连接

## 阶段边界遵守
- 不破坏物流/计划 BOM 主链路 ✓
- 用户可见回答不暴露 SQL/表名/字段名 ✓
- 不自由生成 SQL ✓
- 不做物管/SAP MID M2 ✓
- 未 push/deploy ✓
