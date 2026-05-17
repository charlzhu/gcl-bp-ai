
# CURRENT_STATUS.md

## 当前阶段：物管域 SAP MID 接入 M1 方案已完成，建议进入 M2 准备

当前正式任务：

```text
物管域 SAP Oracle MID 数据同步、智能问数与前端适配建设
```

本轮只执行 M1：数据资产审计、同步方案、中间库建模、智能问数链路、计划 BOM SAP 数据源改造、前端适配方案、Oracle 只读 smoke test 报告。

---

## 一、M1 已完成内容

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

## 二、本轮未做事项

1. 未新增正式业务接口。
2. 未修改前端页面。
3. 未创建数据库迁移。
4. 未接入用户问答生产链路。
5. 未让智能助手实时直接查询 SAP Oracle MID。
6. 未让 LLM 自由生成 SQL 并执行。
7. 未导出 Oracle 大表。
8. 未写入或泄露真实 Oracle 账号密码。

---

## 三、当前结论

1. M2 可优先从库存/出入库两视图开始：`V_HF_SAP_INOUT_DAILY`、`V_SAP_HFFN_CRKLSZ`。
2. 现有物流链路可复用同步日志、ODS/DWD/DWS/DM 分层、SQL 模板、查询服务、StreamingResponse 和前端结果表格模式。
3. 现有计划 BOM 已具备 `source_type/source_tag/import_batch_id` 等多来源基础，但 `SAP` 与需求中的 `SAP_MID` 命名需要 M2 前人工确认。
4. Oracle live 验证当前被驱动缺失阻塞，M2 开发前必须补齐驱动并做只读 `SELECT 1`、字段结构、count、小样本验证。

---

## 四、现有能力基线仍需保持

历史物流/计划 BOM/功率预测能力不属于本轮 M1 改造对象。本轮文档工作不应改变既有能力边界：物流、计划 BOM、功率预测、试运行 E2E 基线均需在 M2 开发时继续回归。
