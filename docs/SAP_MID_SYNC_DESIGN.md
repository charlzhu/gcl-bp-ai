
# SAP MID 自动/手动同步方案（M1）

## 1. Oracle 连接配置读取方案

新增基础设施层建议路径：`backend/app/infra/oracle/`。配置只从环境变量读取：`SAP_ORACLE_HOST`、`SAP_ORACLE_PORT`、`SAP_ORACLE_SERVICE`、`SAP_ORACLE_USER`、`SAP_ORACLE_PASSWORD`。文档、日志和错误返回只记录配置项是否存在，不记录真实值。

## 2. Oracle 连接池方案

优先采用 `oracledb` thin 模式；如企业环境要求 Oracle Client，再启用 thick 模式。连接池设置建议：最小连接 1、最大连接 3-5、连接超时 5-10 秒、查询超时 60-300 秒、fetch size 1000-5000。连接层只暴露白名单视图读取接口，不暴露任意 SQL 执行。

## 3. 白名单视图设计

以配置文件/常量注册允许视图、业务主题、主键候选、增量字段、默认字段集合、最大单批行数。M2 首批白名单只开放：`V_HF_SAP_INOUT_DAILY`、`V_SAP_HFFN_CRKLSZ`。后续按路线逐步开放采购、工单、SAP BOM。

## 4. 自动同步设计

自动同步由调度器触发 `business_topic + sync_mode`。支持全量初始化、增量、指定视图、指定主题。每次执行创建 `sys_task_log`，同步中分批读取 Oracle，写 ODS，再转换 DWD/DWS，最后写统计和状态。

## 5. 手动同步设计

手动同步入口只触发后端同步任务，不允许前端直接连 Oracle。请求参数：主题、视图、同步模式、时间范围、重跑批次、操作人。后端校验白名单与权限后创建任务。

## 6. 全量同步设计

全量同步仅用于初始化或人工批准重建。必须分批分页，不允许无条件大表导出。写入时采用 staging/临时批次策略，批次成功后切换 active 标记；失败批次不污染现有可用数据。

## 7. 增量同步设计

按视图配置的增量字段读取 `last_success_watermark` 之后的数据，并设置回看窗口（例如 1-3 天）处理迟到更新。ODS upsert 以 `source_pk/source_hash` 幂等。

## 8. 指定时间范围同步设计

时间范围同步要求选择支持的时间字段，例如库存日期、过账日期、BUDAT、EINDT。时间范围必须有上限，避免误触发大表导出。

## 9. 指定视图同步设计

视图名必须命中白名单。执行前检查目标 ODS 表、字段映射和主键配置是否存在，缺失则拒绝执行并写错误日志。

## 10. 指定主题同步设计

主题映射：inventory、material_flow、purchase_execution、work_order_component、sap_bom。主题同步内部按依赖顺序执行多个视图，例如采购先头/行/交货计划/历史，再构建 DWS。

## 11. 分批读取设计

Oracle 侧只选择必要字段；分页可用 ROWNUM 包装、时间窗口或主键范围。每批记录 read_count、insert_count、update_count、skip_count、error_count。单批失败可重试，超过阈值后任务失败并保留已成功批次状态。

## 12. 幂等写入设计

ODS 使用唯一键 `source_view + source_pk`；无源主键时使用 `source_view + source_hash`。DWD/DWS 使用业务主键 + `source_type`。重复同步应更新变更字段或跳过完全一致记录。

## 13. 失败重试设计

失败重试按任务/视图/批次粒度进行。可重试错误：网络断开、查询超时、临时锁等待；不可重试错误：白名单外视图、字段映射缺失、主键缺失率过高。重试需继承原始任务上下文并生成新 run 记录。

## 14. 同步日志设计

复用 `sys_task_log` 记录任务级状态；扩展业务字段：business_topic、source_system、source_view、target_table、sync_mode、sync_batch_no、trigger_type、operator、watermark_start/end、read/insert/update/skip/error_count。

## 15. 错误日志设计

复用 `sys_task_error_log`，记录 error_stage、source_view、target_table、source_pk、safe_error_code、safe_error_message、raw_sample_hash。错误日志不得包含 Oracle DSN、用户名、密码或完整敏感 SQL。

## 16. 安全控制

1. Oracle 账号只读。
2. 视图白名单 + 字段白名单。
3. 不接受用户输入拼接 SQL。
4. 前端无 Oracle 密码展示。
5. 问数只查中间库。
6. 日志和文档只保存配置存在性与安全错误摘要。

## 17. 性能风险

风险包括 Oracle 大视图、网络抖动、无索引增量字段、字段宽度大、DWD/DWS 聚合慢。应通过限流、分批、回看窗口、只读副本时间窗和异步任务规避。

## 18. Oracle 不可访问时的降级策略

当前本机 smoke test 因 Oracle Python 驱动缺失阻塞。Oracle 不可访问时不伪造结果，使用附件继续设计；同步任务在运行态应返回 `ORACLE_UNAVAILABLE` 并提示人工检查网络、驱动、权限。

## 19. 前端手动同步触发接口规划

M2 后端接口建议：`POST /api/v1/material-management/sap-mid/sync-tasks`。请求包括 topic、view_name、sync_mode、date_range、rerun_batch_no。响应返回 task_id 和初始状态。

## 20. 前端同步状态查询接口规划

建议：`GET /api/v1/material-management/sap-mid/sync-tasks`、`GET /api/v1/material-management/sap-mid/sync-tasks/{task_id}`、`POST /api/v1/material-management/sap-mid/sync-tasks/{task_id}/retry`。状态展示只返回业务统计和安全错误摘要。
