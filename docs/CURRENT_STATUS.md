# CURRENT_STATUS.md

## 当前阶段：总体架构已确认，近期执行口径统一到物管 SAP MID M2 准备

当前项目长期定位已由以下文档确认：

```text
docs/PLATFORM_OVERALL_ARCHITECTURE_AND_ROADMAP.md
```

总体方向为：

```text
多 Agent 受控调度 + 多业务域智能问答 + 多工具调用 + 第三方平台数据接入分析 + 普通非业务问答
```

四大业务域为：

1. 物流。
2. 计划。
3. 物控/物管。
4. 经营分析。

当前近期正式执行口径为：

```text
物管域 SAP Oracle MID 数据同步、智能问数与前端适配建设
```

上一阶段 M1 已完成。下一阶段建议进入：

```text
M2：库存 / 出入库同步 MVP + 物管问答前端入口 MVP
```

> 说明：计划 BOM 功率预测 M1 已作为计划域历史/专项能力沉淀，不再作为当前阶段入口；后续如继续功率预测，应按 `docs/PLAN_POWER_IMPLEMENTATION_PLAN.md` 另行确认阶段边界。

---

## 一、总体架构确认状态

1. 已新增并由用户确认：`docs/PLATFORM_OVERALL_ARCHITECTURE_AND_ROADMAP.md`。
2. 总规文档作为上位规划，负责统一长期方向、业务域划分、Agent/工具/数据/问答职责边界。
3. 总规文档不替代具体执行阶段；每轮执行仍以最新用户确认、`docs/CURRENT_STATUS.md`、`docs/NEXT_TASK.md`、`ai/inbox/requirement.md` 为准。
4. 已确认核心原则：
   - LLM 负责理解、拆解、归一化辅助和表达。
   - 后端确定性代码负责查数、计算、校验和追溯。
   - 用户问答必须优先基于智能助手中间库。
   - SAP Oracle MID 等第三方系统作为同步源或受控工具源，不作为用户实时问答直查库。
   - 多 Agent 与多工具调用必须受白名单、权限、审计和阶段边界控制。

---

## 二、物管 SAP MID M1 已完成内容

1. 只读审计 `ai/inbox/requirement.md`。
2. 只读审计 SAP MID 附件：87 个视图、7718 行字段元数据、16 个重点视图样例、87 条视图 SQL 记录。
3. 只读审计智能助手中间库附件：物流 ODS/DWD/DWS/DM、计划 BOM 表、sys_task/sys_query 日志表。
4. 只读审计现有后端：物流同步/问数链路、计划 BOM Excel 导入/查询/QA、配置与 DB session。
5. 只读审计现有前端：路由、布局、BusinessChatPage、物流/计划 BOM API、ResultTable、流式 API。
6. 完成 Oracle 只读 smoke test 前置检查：`SAP_ORACLE_*` 配置项存在，但本地缺少 `oracledb/cx_Oracle` 驱动，未连接 Oracle、未执行 SQL、未导出数据。
7. 输出 M1 文档：
   - `docs/MATERIAL_MANAGEMENT_SAP_MID_DATA_ASSET_AUDIT.md`
   - `docs/MATERIAL_MANAGEMENT_MIDDLE_DB_MODEL_PLAN.md`
   - `docs/SAP_MID_SYNC_DESIGN.md`
   - `docs/MATERIAL_MANAGEMENT_AI_QUERY_PLAN.md`
   - `docs/PLAN_BOM_SAP_DATA_SOURCE_MIGRATION_PLAN.md`
   - `docs/FRONTEND_MATERIAL_MANAGEMENT_ADAPTATION_PLAN.md`
   - `docs/SAP_MID_INTEGRATION_ROADMAP.md`
   - `docs/SAP_MID_ORACLE_SMOKE_TEST_REPORT.md`

---

## 三、M1 未做事项

1. 未新增正式业务接口。
2. 未修改前端页面。
3. 未创建数据库迁移。
4. 未接入用户问答生产链路。
5. 未让智能助手实时直接查询 SAP Oracle MID。
6. 未让 LLM 自由生成 SQL 并执行。
7. 未导出 Oracle 大表。
8. 未写入或泄露真实 Oracle 账号密码。

---

## 四、当前结论

1. 当前阶段口径已统一：不再把计划 BOM 功率预测 M1 作为当前默认入口。
2. 下一步建议执行物管 SAP MID M2，首批范围只聚焦：
   - `V_HF_SAP_INOUT_DAILY`
   - `V_SAP_HFFN_CRKLSZ`
3. M2 开发前必须先补齐 Oracle Python 驱动，完成只读 smoke test：`SELECT 1 FROM dual`、字段结构、count、小样本验证。
4. 现有物流链路可复用同步日志、ODS/DWD/DWS/DM 分层、SQL 模板、查询服务、StreamingResponse 和前端结果表格模式。
5. 现有计划 BOM 已具备 `source_type/source_tag/import_batch_id` 等多来源基础，但 `SAP` 与需求中的 `SAP_MID` 命名需要 M2 前人工确认。
6. 总规中的多 Agent、多工具、经营分析、统一入口属于中长期路线，不等于当前可直接进入完整实现。

---

## 五、现有能力基线仍需保持

M2 及后续开发必须保持以下既有能力不被破坏：

1. 物流问答与物流回归能力。
2. 计划 BOM Excel 导入、查询、QA、消歧与对比能力。
3. 计划 BOM 功率预测相关已沉淀文档与阶段边界。
4. 前端智能问答现有物流 / 计划 BOM 展示能力。
5. 用户可见回答不暴露 SQL、表名、字段名、query_key、planner、guardrail、schema、raw/debug、LLM 等内部实现。

---

## 六、当前禁止事项

1. 不在未确认 M2 前自动进入代码开发。
2. 不全量导出 Oracle 大表。
3. 不让用户问答实时直查 SAP Oracle MID。
4. 不让 LLM 自由生成 SQL 并执行。
5. 不把真实账号密码、host、DSN、API Key 写入文档、日志、代码注释或提交记录。
6. 不因为总规已确认就直接实现完整多 Agent、多工具、经营分析或 RAG。
7. 不修改或覆盖 `ai/inbox/attachments/` 原始附件。
