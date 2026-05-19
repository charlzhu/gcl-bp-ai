# NEXT_TASK.md

## 下一步任务：M2 库存 / 出入库同步 MVP + 物管问答入口 MVP

当前总体架构已确认：

```text
docs/PLATFORM_OVERALL_ARCHITECTURE_AND_ROADMAP.md
```

当前近期执行主线不再是计划 BOM 功率预测 M1，而是物管域 SAP MID 接入后续阶段。

M1 已完成。下一轮建议进入：

```text
M2：库存 / 出入库同步 MVP + 物管问答前端入口 MVP
```

首批范围只允许聚焦：

```text
V_HF_SAP_INOUT_DAILY
V_SAP_HFFN_CRKLSZ
```

> 说明：总规中的多 Agent、多工具、统一入口、经营分析、RAG 均为中长期路线。M2 不应直接扩展到完整 Agent 平台或全域工具系统。

---

## 一、进入 M2 前必须先读取

1. `AGENTS.md`
2. `README_WORKSPACE.md`
3. `docs/PLATFORM_OVERALL_ARCHITECTURE_AND_ROADMAP.md`
4. `docs/CURRENT_STATUS.md`
5. `docs/NEXT_TASK.md`
6. `docs/HANDOFF.md`
7. `ai/protocols/company_task_protocol.md`
8. `ai/company/roles/technical_manager.md`
9. `ai/hermes_skills/company-code-builder/SKILL.md`
10. `ai/inbox/requirement.md`
11. `ai/inbox/attachments_manifest.md`
12. `docs/MATERIAL_MANAGEMENT_SAP_MID_DATA_ASSET_AUDIT.md`
13. `docs/MATERIAL_MANAGEMENT_MIDDLE_DB_MODEL_PLAN.md`
14. `docs/SAP_MID_SYNC_DESIGN.md`
15. `docs/MATERIAL_MANAGEMENT_AI_QUERY_PLAN.md`
16. `docs/PLAN_BOM_SAP_DATA_SOURCE_MIGRATION_PLAN.md`
17. `docs/FRONTEND_MATERIAL_MANAGEMENT_ADAPTATION_PLAN.md`
18. `docs/SAP_MID_INTEGRATION_ROADMAP.md`
19. `docs/SAP_MID_ORACLE_SMOKE_TEST_REPORT.md`

如果上述文件缺失、内容冲突或附件无法读取，必须先停止并报告，不允许编造。

---

## 二、M2 前置阻塞必须处理

1. 安装并锁定 Oracle Python 驱动：优先 `oracledb`。
2. 使用 `SAP_ORACLE_*` 环境变量完成只读连接 smoke test。
3. 验证 `SELECT 1 FROM dual`。
4. 验证首批白名单视图字段结构。
5. 对首批两个视图执行 count 与 `ROWNUM <= 5` 小样本。
6. 不输出真实 host、user、password、DSN、连接串或其他密钥。
7. 确认 Oracle 账号只读权限和查询边界。
8. 确认 M2 仅以 SAP Oracle MID 为同步源，用户问答仍基于智能助手中间库。

---

## 三、M2 后端任务清单

1. 新建或完善 `backend/app/domains/material_management/` 基础目录。
2. 新增 Oracle 基础设施层或遵循当前配置规范增加 Oracle client/config。
3. 新增白名单视图注册：只开放 `V_HF_SAP_INOUT_DAILY` 与 `V_SAP_HFFN_CRKLSZ`。
4. 新增库存 / 出入库 ODS/DWD 表迁移。
5. 新增同步任务服务：手动同步、增量同步、分批读取、幂等 upsert、任务日志、错误日志。
6. 新增库存 / 出入库查询服务和受控 SQL 模板。
7. 新增物管问答最小链路：业务域识别、意图分类、参数抽取、程序查中间库、LLM 润色。
8. 写 focused tests、compile、static scan、review 材料。
9. 保持现有物流、计划 BOM、功率预测相关能力不被破坏。

---

## 四、M2 前端任务清单

1. 在智能问答 domain switch 中增加物管入口，或在后端 readiness 后显示入口。
2. 新增 `frontend/src/api/materialManagement.ts`。
3. 复用 BusinessChatPage、streamingApi、ResultTable 展示库存 / 出入库结果。
4. 展示查询条件、来源中间库表、同步批次、数据日期。
5. 展示空结果、错误、暂不支持、需要澄清等状态。
6. 不改变现有物流和计划 BOM 页面行为。
7. 用户可见回答不得暴露 SQL、表名、字段名、query_key、planner、guardrail、schema、raw/debug、LLM 等内部技术内容。

---

## 五、M2 验收标准

1. Oracle 只读 smoke test 通过，且无密钥泄露。
2. 可从 Oracle MID 抽取受控小批量库存 / 出入库数据写入智能助手中间库。
3. 重复同步不产生重复脏数据。
4. 同步日志和错误日志可追溯。
5. 至少 5 个库存 / 出入库测试问题可基于中间库回答。
6. 前端可进入物管问答入口并展示库存 / 出入库结果。
7. 现有物流、计划 BOM、功率预测功能回归通过。
8. 用户问答链路不实时直查 SAP Oracle MID。
9. LLM 未直接计算业务事实、未自由生成 SQL 并执行。
10. 形成验收材料：测试日志、diff、风险说明、最终报告。

---

## 六、M2 禁止事项

1. 不全量导出 Oracle 大表。
2. 不让用户问答直接查 SAP Oracle MID。
3. 不让 LLM 自由生成 SQL 并执行。
4. 不把真实账号密码写入文档、日志、代码注释或提交记录。
5. 不扩展到采购、工单、SAP BOM，除非 M2 验收后另开任务。
6. 不直接实现完整多 Agent 编排。
7. 不直接实现完整多工具平台。
8. 不直接扩经营分析、RAG 或全域统一入口。
9. 不修改或覆盖 `ai/inbox/attachments/` 原始附件。
10. 不破坏既有物流 / 计划 BOM / 功率预测能力。

---

## 七、M2 与总规文档的关系

M2 是 `docs/PLATFORM_OVERALL_ARCHITECTURE_AND_ROADMAP.md` 中“物控/物管域 SAP MID 数据接入与问答 MVP”的近期落地切片。

M2 只验证以下平台能力：

1. 第三方平台只读同步源接入。
2. 智能助手中间库分层沉淀。
3. 物控/物管域最小问答链路。
4. 前端多业务域入口扩展。
5. 同步与问答结果可追溯。

M2 不验证完整多 Agent、多工具、RAG、经营分析和全域 NL2SQL 能力。
