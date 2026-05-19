
# 前端物管域与 SAP/MID 适配方案（M1）

## 1. 当前前端页面结构分析

当前路由在 `frontend/src/router/index.ts`，主布局在 `frontend/src/layouts/AppLayout.vue`，统一智能问答页在 `frontend/src/views/business-chat/BusinessChatPage.vue`，API 封装在 `frontend/src/api/`，结果表格组件为 `frontend/src/components/ResultTable.vue`。

## 2. 当前物流问答页面如何实现

物流问答通过 `frontend/src/api/logistics.ts` 调用 `/logistics/data-qa/query` 与 `/logistics/data-qa/query/stream`，前端支持流式文本、结构化结果、查询历史和错误/澄清状态。

## 3. 当前计划 BOM 问答页面如何实现

计划 BOM 通过 `frontend/src/api/planBom.ts` 调用 `/plan-bom/qa/ask` 与 `/plan-bom/qa/ask/stream`，在 BusinessChatPage 内按 domain 区分展示计划 BOM 结果。

## 4. 当前前端路由结构

已存在 `/smart-chat`、`/logistics/data-qa`、`/plan-bom/detail-query`、`/bom-data`、`/trial-guide` 等。M1 不新增路由；M2 可先复用 `/smart-chat`，M6 再考虑同步管理页。

## 5. 当前 API 调用封装方式

前端统一使用 `http` 与 `postJsonLineStream`。物管建议新增 `frontend/src/api/materialManagement.ts`，封装问答、同步任务创建、任务列表、任务详情、重试。

## 6. 当前问答结果组件结构

BusinessChatPage 已有 domain switch、流式回答、结果 presentation 和表格展示；ResultTable 可复用。物管新增 result_type 配置和列映射即可先做 MVP。

## 7. 物管业务域前端入口设计

在现有 domain switch 中增加“物管数据”，枚举值建议 `material_management`。自动识别命中物管时切换到物管链路；用户手动选择时优先物管。

## 8. 物管问答页面设计

M2 MVP 仍使用智能问答页：输入框、流式回答、结果表格、查询条件、来源追溯、空结果/澄清/错误状态。避免新建大页面。

## 9. 智能问答页如何增加物管业务域

新增 domain 枚举、按钮文案、提交分支和结果解析。后端提供 `/material-management/qa/ask/stream` 后再接入；未就绪前前端不暴露不可用入口或展示“建设中”。

## 10. 库存查询结果展示设计

列：物料编码、物料名称、工厂、库存地点、批次、当前库存、单位、库存日期、来源表/同步批次。

## 11. 出入库流水结果展示设计

列：过账日期、物料编码、物料名称、移动类型、入库/出库方向、数量、单位、单据号、工单号、采购单号、来源。

## 12. 采购执行结果展示设计

列：采购单号、行号、物料、供应商、下单数量、已到货数量、未到货数量、交货日期、是否延期、来源。

## 13. 工单组件结果展示设计

列：工单号、产品物料、组件物料、组件名称、需求数量、已领数量、缺口数量、工厂、来源。

## 14. SAP/MID 手动同步入口设计

M2 后端接口稳定后，可在管理区或物管页面增加“SAP/MID 同步”入口。入口只调用后端任务接口，不保存、不展示 Oracle 连接信息。

## 15. 手动同步触发交互设计

表单字段：同步主题、视图、模式（全量/增量/时间范围/重跑）、时间范围、备注。提交后展示 task_id、状态和统计。

## 16. 同步任务状态展示设计

状态：待执行、执行中、成功、失败、部分成功。展示开始/结束时间、读取/插入/更新/跳过/失败行数、错误摘要。

## 17. 同步日志查看页面设计

M6 可增加任务详情抽屉/页面，展示视图级批次、错误阶段、错误摘要、重试入口。错误内容必须脱敏。

## 18. 来源追溯展示设计

问答结果底部展示来源主题、来源中间库表、源视图名、同步批次、数据日期、行数。不展示 Oracle host/user/password。

## 19. 复用方案

复用 BusinessChatPage、streamingApi、ResultTable、现有黑灰蓝绿视觉基调、空结果/错误/澄清卡片。新增物管列配置而不是复制整套页面。

## 20. M2-M6 前端开发路线

M2：物管入口 + 库存/出入库结果 MVP；M3：采购结果卡片；M4：工单/缺料；M5：BOM 来源展示；M6：同步管理页和体验增强。

## 21. 不影响现有页面的风险控制方案

所有前端改动必须通过 domain feature flag 或后端 readiness 控制；每阶段跑现有物流、计划 BOM、BOM 数据管理和 build 回归。M1 不修改前端文件。
