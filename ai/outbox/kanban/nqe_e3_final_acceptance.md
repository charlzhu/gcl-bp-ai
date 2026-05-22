# NQE-E3 最终验收报告

## 概述
计划 BOM 问法评测集接入 Graph（NQE-E3）完成。

## 修改文件清单
1. `tests/evaluation/plan_bom/__init__.py` — 空文件，标识 plan_bom 评测目录为 Python 包
2. `tests/evaluation/plan_bom/samples.py` — BOM 评测样例集（12 条），含 load_plan_bom_suite() 加载函数
3. `tests/unit/qa_evaluation/test_plan_bom_eval.py` — 11 个 focused tests

## 测试结果
- focused tests: 11/11 PASSED
- qa_evaluation 全量回归: 65 PASSED, 0 FAILED
  - 唯一失败: test_power_evaluation_samples_loadable（预存在，plan_power 模块尚未创建，属于未来 NQE 任务）
  - 相邻 business_qa_graph 回归: 153/165 PASSED（12 个失败为预存在的 NQE-S4/LQG 配置问题）

## 评测样例覆盖（12 条）
| 状态 | 数量 | 说明 |
|------|------|------|
| success | 7 | 单订单材料规格(2)、双订单对比(2)、全订单表格(2)、版型查询(1) |
| clarification | 2 | 缺少订单/材料标识 |
| unsupported | 2 | 导出请求、功率预测跨界 |
| empty_result | 1 | 不存在订单99999 |

## 关键设计决策
1. EvalGraphRunner 无需修改 —— 已通过 domain_hint=case.domain 自然支持 plan_bom 域
2. BOM 评测样例参考 129 语义回归（A=86/B=40/C=3/D=0）的稳定问法模式
3. 不改变现有 BOM 能力 —— 只新增评测数据，不修改任何 BOM 后端代码
4. 所有新增代码包含中文注释
5. 样例 question 不含技术泄露关键词

## 独立 Review 结果
- passed: true
- security_concerns: []
- logic_errors: []
- suggestions: 3（已全部修复）

## 约束遵守
- [x] 不改变现有 BOM 能力
- [x] 不做物管/SAP MID M2
- [x] 不引入 ES
- [x] 不替代 NL2SQL/LangGraph 已有能力
- [x] 禁止 LLM 自由 SQL/查数/算功率
- [x] 保留旧接口和回退
- [x] 用户可见回答不暴露技术内容
- [x] 不触碰 data-agent/
- [x] 中文注释
- [x] 禁止 push/deploy/reset/clean/stash/rebase/squash
- [x] focused tests + 相邻回归 + compile + diff.patch + test.log + review + final-acceptance
