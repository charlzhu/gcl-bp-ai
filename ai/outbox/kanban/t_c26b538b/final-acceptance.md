# NQE-SQL-MAIN-12 final acceptance

## 任务结论
已完成 EXPLAIN validate 与 correct SQL 节点的最小闭环实现，并完成 reviewer 反馈修复。当前实现仍保持 NQE SQL Agent 独立骨架边界：不连接真实数据库、不引入自由模型修正、不绕过安全预检、不替换旧链路。

## 修改文件
- backend/app/domains/business_qa_graph/nqe_sql_agent_graph.py
- tests/unit/business_qa_graph/test_nqe_sql_agent_explain_correct.py
- ai/outbox/kanban/t_c26b538b/*

## 关键改动
1. 新增离线解释校验辅助逻辑：从 safe candidate 中抽取投影字段，并与 retrieval_context_package 中的字段白名单比对。
2. explain_validate_sql 从占位状态升级为确定性元数据校验：字段不存在时失败并进入受控修正循环。
3. correct_sql 只接受上下文包显式提供的 correction candidates，记录修正轮次，并重新回到 precheck_sql_safety。
4. 修复独立 Codex review 指出的 fail-open 漏洞：SUM(missing_metric) 与双引号包裹未知字段不再绕过投影字段校验。
5. 用户可见错误文案仍走业务化终态，不暴露内部技术细节。

## TDD / Review 证据
- 初始 RED：red-test.log，2 failed。
- 初始 GREEN：green-test.log，最终 3 passed。
- Reviewer RED：reviewer-red-test.log，新增 SUM/quoted projection case 先失败。
- Reviewer GREEN：reviewer-green-test.log，1 passed。
- 独立 Codex read-only review：codex-review-result.json，passed=true，security_concerns=[]，logic_errors=[]。

## 验证命令与结果
- /opt/anaconda3/bin/python3 -m py_compile backend/app/domains/business_qa_graph/nqe_sql_agent_graph.py tests/unit/business_qa_graph/test_nqe_sql_agent_explain_correct.py：通过。
- /opt/anaconda3/bin/python3 -m pytest tests/unit/business_qa_graph/test_nqe_sql_agent_explain_correct.py -q：3 passed，7 warnings。
- /opt/anaconda3/bin/python3 -m pytest tests/unit/business_qa_graph/test_nqe_sql_agent_graph_skeleton.py tests/unit/business_qa_graph/test_nqe_sql_agent_safety_precheck.py tests/unit/business_qa_graph/test_nqe_sql_agent_explain_correct.py -q：26 passed，7 warnings。
- scoped diff --check：无 whitespace error。
- scoped secret scan：0 matches。
- 探索性 broader run：/opt/anaconda3/bin/python3 -m pytest tests/unit/business_qa_graph -q：213 passed / 22 failed / 7 warnings；失败集中在本卡未触碰的 builder/adapter/assist 旧测试链路，已记录在 business-qa-graph-full-dir-test.log，不作为本卡通过条件。

## 验收材料路径
- ai/outbox/kanban/t_c26b538b/diff.patch
- ai/outbox/kanban/t_c26b538b/final-acceptance.md
- ai/outbox/kanban/t_c26b538b/focused-test.log
- ai/outbox/kanban/t_c26b538b/green-test.log
- ai/outbox/kanban/t_c26b538b/red-test.log
- ai/outbox/kanban/t_c26b538b/reviewer-red-test.log
- ai/outbox/kanban/t_c26b538b/reviewer-green-test.log
- ai/outbox/kanban/t_c26b538b/codex-review-result.json
- ai/outbox/kanban/t_c26b538b/business-qa-graph-full-dir-test.log
- ai/outbox/kanban/t_c26b538b/secret-scan.log
- ai/outbox/kanban/t_c26b538b/git-status.log

## 风险与未解决问题
- 当前实现是离线解释校验，不是真实数据库 EXPLAIN；符合本卡骨架阶段边界，但后续接真实执行器时仍需加数据库级 explain/trial gate。
- broader business_qa_graph 目录仍有 22 个非本卡范围失败，主要涉及旧 builder/adapter/assist 参数与状态字段，不在本卡改动范围内。
- git-status 显示当前工作区存在较多前序 NQE 卡遗留的未跟踪/已修改文件；本卡仅生成 scoped diff.patch，未尝试清理或提交。

## 影响范围
- 不影响前端。
- 不改物流、计划 BOM、功率预测、产销存业务入口。
- 不改 SAP MID / 物管状态文档。
- 不新增数据库连接或外部凭据读取。

## 操作声明
- 未 commit。
- 未 push。
- 未 deploy。
- 未读取或写入 .env / 真实凭据。
