
# HANDOFF.md

## 交接结论：物管域 SAP MID 接入 M1 方案已完成

本轮完成的是 M1 文档和只读审计，不是正式开发。未新增正式接口、未修改前端页面、未创建迁移、未导出 Oracle 大表、未把用户问答接到 Oracle。

---

## 一、已完成产物

1. `docs/MATERIAL_MANAGEMENT_SAP_MID_DATA_ASSET_AUDIT.md`
2. `docs/MATERIAL_MANAGEMENT_MIDDLE_DB_MODEL_PLAN.md`
3. `docs/SAP_MID_SYNC_DESIGN.md`
4. `docs/MATERIAL_MANAGEMENT_AI_QUERY_PLAN.md`
5. `docs/PLAN_BOM_SAP_DATA_SOURCE_MIGRATION_PLAN.md`
6. `docs/FRONTEND_MATERIAL_MANAGEMENT_ADAPTATION_PLAN.md`
7. `docs/SAP_MID_INTEGRATION_ROADMAP.md`
8. `docs/SAP_MID_ORACLE_SMOKE_TEST_REPORT.md`
9. `docs/CURRENT_STATUS.md`
10. `docs/NEXT_TASK.md`
11. `docs/HANDOFF.md`

审计中间材料位于：`ai/outbox/kanban/t_a252ec3a/`。

---

## 二、关键结论

1. SAP MID 附件显示 87 个视图、7718 行字段元数据；16 个重点视图覆盖库存、出入库、采购、工单、SAP BOM。
2. M2 建议只做库存/出入库 MVP：`V_HF_SAP_INOUT_DAILY` 与 `V_SAP_HFFN_CRKLSZ`。
3. 用户问数必须查智能助手中间库，不能实时直接查 SAP Oracle MID。
4. LLM 只负责理解和表达，程序负责基于模板准确查数；禁止 LLM 自由 SQL。
5. 计划 BOM 可扩展 SAP MID 数据源，但需确认 `SAP_MID` 与现有 `SAP` source_type 命名兼容策略。

---

## 三、Oracle smoke test 状态

`SAP_ORACLE_*` 配置项存在性已确认，但本地 `backend/.venv` 缺少 Oracle Python 驱动（`oracledb` / `cx_Oracle` 均不可导入），因此未连接 Oracle、未执行 `SELECT 1 FROM dual`、未做 count、未读取 live 字段结构、未抽样 Oracle 数据。

不要伪造 Oracle 结果。M2 前必须先补齐驱动并做只读 smoke test。

---

## 四、下一步建议

进入 M2 前，先处理 Oracle 驱动和只读连接验证；验证通过后，由 Codex/开发子任务按 `docs/NEXT_TASK.md` 拆分实现库存/出入库同步 MVP、查询模板和前端物管入口 MVP。

---

## 五、人工确认项

1. Oracle 驱动和网络权限。
2. MID schema/owner 与只读账号权限。
3. 库存/出入库业务口径：移动类型方向、库存结存、退料/冲销净额化。
4. `source_type = SAP_MID` 是否作为正式枚举。
5. 前端物管入口命名、同步管理权限和展示口径。

---

## 六、边界提醒

1. 不要改 main。
2. 不要恢复任何临时 token。
3. 不要把真实账号密码写入文档/日志/代码。
4. 不要让智能助手问答直接查 Oracle。
5. 不要在 M2 范围外提前做采购、工单、SAP BOM 的正式开发。
6. 每轮开发必须保留并回归现有物流、计划 BOM、功率预测能力。
