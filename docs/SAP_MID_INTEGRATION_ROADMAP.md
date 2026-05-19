
# SAP MID 集成路线图（M1-M6）

## 1. M1-M6 阶段路线

| 阶段 | 目标 | 允许事项 | 禁止事项 | 验收标准 | 预计改动范围 |
|---|---|---|---|---|---|
| M1 | 数据资产审计、总体方案、前端适配方案 | 读附件、读代码、写文档、只读 smoke test | 正式开发、前端页面修改、大表导出、直接问答查 Oracle | 输出 8 个方案文档 + CURRENT_STATUS/NEXT_TASK/HANDOFF | docs、审计材料 |
| M2 | 库存/出入库同步 MVP + 物管问答入口 MVP | Oracle 连接器、两视图 ODS/DWD、手动同步、基础问数 | 采购/工单/BOM 全量扩展 | 小批量同步、幂等、5 个库存/出入库问题、前端入口可展示 | backend material_management、alembic、frontend smart-chat 小改 |
| M3 | 采购执行同步与问数 | EBAN/EKKO/EKPO/EKET/EKBE、采购 DWS、采购结果展示 | 工单/BOM 范围外扩张 | 可查采购单、未到货、延期、供应商交付 | 后端采购主题、前端采购展示 |
| M4 | 工单组件/实际用料同步与问数 | AFKO/AFPO/AUFK/RESB、缺料初步分析 | 理论 BOM 与实际工单混淆 | 可查工单组件、物料需求、基础缺料 | 后端工单主题、前端工单展示 |
| M5 | 计划 BOM SAP 数据源改造 | MAST/STKO/STPO/STAS/STZU ODS/DWD、source_type 并存 | 破坏 Excel BOM/功率预测 | SAP BOM 可查，Excel 原功能可用 | plan_bom 多数据源、BOM 来源展示 |
| M6 | 物管问数增强和同步管理增强 | 词典、模板、评测、状态页、日志页 | LLM 自由 SQL、前端直连 Oracle | 常见物管问数可回答，来源可追溯，同步管理可用 | 前后端体验增强 |

## 2. 后续 Codex 任务拆分建议

1. M2-A：Oracle 依赖和只读连接器，含配置脱敏测试。
2. M2-B：库存/出入库 ODS/DWD 迁移与 ORM。
3. M2-C：白名单同步服务、CLI/管理接口和日志。
4. M2-D：库存/出入库查询服务和 SQL 模板。
5. M2-E：前端物管 domain switch 与结果展示 MVP。
6. M2-F：focused/full/build/reviewer 验收材料。

## 3. 人工确认节点

1. Oracle 驱动、网络和只读账号权限。
2. M2 首批视图与同步时间窗口。
3. 移动类型方向、库存口径、未到货口径、缺料阈值。
4. `SAP_MID` source_type 命名。
5. 前端菜单命名和同步管理权限。

## 4. 回滚策略

1. 数据库迁移按阶段独立，可回滚新增表/索引。
2. 同步任务默认写新表，不覆盖现有物流/计划 BOM 数据。
3. 前端入口用 feature flag 或后端 readiness 控制。
4. 问数模板按 domain 隔离，物管失败不影响物流/计划 BOM。
5. SAP BOM 接入先 shadow，不改变 Excel 默认来源。

## 5. 风险清单

Oracle 驱动/网络不可用、视图数据量过大、增量字段不稳定、SAP 日期/删除标记口径复杂、移动类型业务含义未确认、Excel/SAP BOM source_type 命名冲突、前端入口过早暴露、LLM 润色越界。

## 6. 前后端协同开发节奏

后端先提供稳定 schema、同步任务状态和问答响应结构；前端先接 MVP result_type 和来源展示；每阶段后端接口冻结后再做前端增强。所有阶段必须保留现有物流、计划 BOM、功率预测回归。
