# LQG-1 final acceptance

## 结论

LQG-1 通过。已完成默认关闭的 LangGraph 基础骨架：配置项、request/response/event/state、receive_node、START -> receive -> END 的最小 StateGraph、runner，以及 BUSINESS_QA_LANGGRAPH_ROADMAP.md。

本卡不接正式 API、不接前端入口、不执行真实业务查数、不替代 Query Planning V2 / 受控 NL2SQL、不引入自由 SQL、不接工具调用或多 Agent 完整编排。

## 修改文件清单

- backend/requirements.txt
- backend/app/core/config.py
- backend/app/domains/business_qa_graph/__init__.py
- backend/app/domains/business_qa_graph/builder.py
- backend/app/domains/business_qa_graph/runner.py
- backend/app/domains/business_qa_graph/nodes/__init__.py
- backend/app/domains/business_qa_graph/nodes/receive_node.py
- backend/app/domains/business_qa_graph/schemas/__init__.py
- backend/app/domains/business_qa_graph/schemas/event.py
- backend/app/domains/business_qa_graph/schemas/request.py
- backend/app/domains/business_qa_graph/schemas/response.py
- backend/app/domains/business_qa_graph/schemas/state.py
- docs/BUSINESS_QA_LANGGRAPH_ROADMAP.md
- tests/unit/business_qa_graph/test_business_qa_graph_skeleton.py

## 验证结果

见 ai/tasks/running/TASK-business-qa-langgraph-lqg1/test.log：

- focused：tests/unit/business_qa_graph/test_business_qa_graph_skeleton.py，4 passed。
- 相邻回归：tests/unit/query_planning/test_query_plan_v2_schema.py + tests/unit/query_planning/test_query_planning_phase4.py，10 passed。
- Python compile：backend/app/domains/business_qa_graph + backend/app/core/config.py，passed。

见 ai/tasks/running/TASK-business-qa-langgraph-lqg1/static-scan.log：

- git diff --check：PASS。
- added-line secret/token/password scan：PASS。
- dangerous execution scan：PASS。

见 ai/tasks/running/TASK-business-qa-langgraph-lqg1/review-result.json：

- 独立 review：passed=true。
- security_concerns：0。
- logic_errors：0。
- suggestions：2 条非阻塞增强建议。

## 风险与边界

- 当前 Graph 仅为外层编排骨架，不代表 NL2SQL 已完成。
- 当前 Graph 仅执行 receive 节点，不允许查中间库或外部源库。
- 默认配置关闭，不应影响旧物流 / 计划 BOM 接口。
- LQG-1 不包含领域路由、capability registry、工具调用、SQLPlan 执行、前端接入。
- 用户可见回答未由本卡变更，未引入技术泄露面。

## 对既有能力影响

- 物流问答：不替换、不接入正式路径，仅相邻 Query Planning 单测回归。
- 计划 BOM / 功率预测：不替换、不改业务逻辑。
- 物管 / SAP MID：不进入 M2，不访问 Oracle。
- 经营分析：不接入真实问答执行。

## 当前工作区注意事项

本验收证据在 LQG-1 scoped diff 基础上生成。Kanban 已自动推进子任务 LQG-2，且同一工作区中后续 LQG-2 可能继续修改 tests/unit/business_qa_graph 与 backend/app/domains/business_qa_graph；因此 LQG-1 的验收以本目录下冻结的 diff.patch/test.log/static-scan.log/review-result.json 为准。

## 提交/部署状态

- 未 push。
- 未 deploy。
- 未 reset / clean / stash / rebase / squash。
- 本卡按 Kanban review-required/验收材料口径完成；如需提交，应只提交 scoped 文件与本 evidence 目录。
