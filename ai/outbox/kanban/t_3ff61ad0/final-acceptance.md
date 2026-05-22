# LQG-6 Final Acceptance: execute_node 计划 BOM 分支接入 PlanBomQaService

## 任务概要

LQG-6 扩展 execute_node 支持 plan_bom 域，调用 PlanBomQaService.ask 执行计划 BOM 自然语言问答，
结果经清洗后写入 state.execution_result，保留 BOM NLU、单/多订单、版本对比、存在性检查、多候选追问等能力。

## 变更文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/domains/business_qa_graph/nodes/execute_node.py` | 修改 | 新增 plan_bom 域分支；提取 _execute_plan_bom/_execute_logistics 独立函数；新增 _sanitize_plan_bom_result/_default_plan_bom_service；新增 _build_error_state 公共异常处理 |
| `backend/app/domains/business_qa_graph/builder.py` | 修改 | _route_after_plan_build 扩展 logistics+plan_bom→execute；build_business_qa_graph 新增 plan_bom_service 参数 |
| `tests/unit/business_qa_graph/test_lqg6_execute_node_plan_bom.py` | 新增 | 9 个 focused 测试用例 |

## 测试结果

- **Focused tests**: 9/9 passed (LQG-6)
- **Regression tests**: 61/61 passed (LQG-1~LQG-5)
- **Total**: **70/70 passed**, 0 failed
- **Static scan**: 无安全问题 (0 hardcoded secrets, 0 dangerous ops, 0 eval/exec, 0 SQL injection)
- **Compile**: execute_node.py ✓ builder.py ✓

## 独立审查

- **Reviewer**: independent delegate_task subagent
- **Verdict**: **passed=true**
- **Security concerns**: 0
- **Logic errors**: 0
- **Non-blocking suggestions**: 4 (已记录，均为文档/测试增强建议，不影响功能正确性)

## 验收标准检查

| 标准 | 状态 |
|------|------|
| 计划 BOM 域问题经 execute_node 调用 PlanBomQaService.ask 并存储结果 | ✅ 通过 |
| stream fallback 优先 presentation.answer，避免 answer_summary 泄露槽位/内部字段 | ✅ 通过 |
| 执行结果不泄露 SQL/表名/字段名/query_key/planner/raw/debug | ✅ 通过 |
| 异常安全降级 | ✅ 通过 |
| 旧 /plan-bom/qa/ask 与 /stream 接口不受影响 | ✅ 通过 |
| 物流域仍正常工作（LQG-5 回归） | ✅ 通过 (61 regression tests pass) |
| BOM 单号/文件名/客户实例消歧不回退 | ✅ 确认（由 PlanBomQaService 内部保证） |
| 多候选业务化追问 | ✅ 确认（由 PlanBomQaService 内部保证） |
| 材料规格查询、版本对比、存在性查询正常 | ✅ 确认（由 PlanBomQaService 内部保证） |

## 设计决策

1. **domain-based routing**: execute_node 按 domain 分支，logistics→_execute_logistics, plan_bom→_execute_plan_bom
2. **presentation.answer 优先**: Plan BOM 的 answer_summary 可能携带槽位名等内部口径，优先使用 presentation.answer
3. **函数提取**: 将物流和 BOM 执行逻辑提取为独立函数，公共异常处理提取为 _build_error_state
4. **安全构造**: _default_plan_bom_service 使用 try/except 包裹，DB 不可达时返回 None，由 execute_node 优雅降级

## 未解决问题

1. (NB) calculation_logic 注释与代码不一致 — 已修复
2. (NB) _execute_plan_bom 中 "not supported" 分支当前为死代码（PlanBomQaResponse 硬编码 supported=True）— 已添加注释说明
3. (NB) 缺少 full-graph integration test（需 DB 连接的 BOM adapter 无法在测试环境自动构造）— 建议后续添加
4. (NB) BOM 域 unsupported 查询依赖上游 validation/classification 拦截 — 已记录依赖

## 阶段边界

- ✅ LangGraph 只做外层编排，不替代 PlanBomQaService/NL2SQL
- ✅ 禁止 LLM 自由 SQL、查数、算功率或改结构化事实
- ✅ 保留旧接口和回退（/plan-bom/qa/ask, /stream 未改动）
- ✅ 用户可见回答不暴露 SQL/表名/字段名/query_key/planner/guardrail/schema/raw/debug/LLM
- ✅ 不 touch data-agent/
- ✅ 不 push/deploy/reset/clean/stash/rebase/squash/自动解冲突

## 证据材料

- `ai/outbox/kanban/t_3ff61ad0/diff.patch` — scoped git diff
- `ai/outbox/kanban/t_3ff61ad0/test.log` — 70 tests output
- `tests/unit/business_qa_graph/test_lqg6_execute_node_plan_bom.py` — 9 focused tests
