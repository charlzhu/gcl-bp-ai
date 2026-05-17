
# NEXT_TASK.md

## 下一步任务：M2 库存 / 出入库同步 MVP + 物管问答入口 MVP

M1 已完成。下一轮建议进入：

```text
M2：库存 / 出入库同步 MVP + 物管问答前端入口 MVP
```

首批范围：

```text
V_HF_SAP_INOUT_DAILY
V_SAP_HFFN_CRKLSZ
```

---

## 一、进入 M2 前必须先读取

1. `AGENTS.md`
2. `README_WORKSPACE.md`
3. `ai/inbox/requirement.md`
4. `docs/CURRENT_STATUS.md`
5. `docs/NEXT_TASK.md`
6. `docs/HANDOFF.md`
7. `docs/MATERIAL_MANAGEMENT_SAP_MID_DATA_ASSET_AUDIT.md`
8. `docs/MATERIAL_MANAGEMENT_MIDDLE_DB_MODEL_PLAN.md`
9. `docs/SAP_MID_SYNC_DESIGN.md`
10. `docs/MATERIAL_MANAGEMENT_AI_QUERY_PLAN.md`
11. `docs/FRONTEND_MATERIAL_MANAGEMENT_ADAPTATION_PLAN.md`
12. `docs/SAP_MID_ORACLE_SMOKE_TEST_REPORT.md`

---

## 二、M2 前置阻塞必须处理

1. 安装并锁定 Oracle Python 驱动：优先 `oracledb`。
2. 使用 `SAP_ORACLE_*` 环境变量完成只读连接 smoke test。
3. 验证 `SELECT 1 FROM dual`。
4. 验证白名单字段结构。
5. 对首批两个视图执行 count 与 `ROWNUM <= 5` 小样本。
6. 不输出真实 host/user/password/DSN。

---

## 三、M2 后端任务清单

1. 新建 `backend/app/domains/material_management/` 基础目录。
2. 新增 Oracle 基础设施层或遵循当前配置规范增加 Oracle client/config。
3. 新增白名单视图注册：只开放 `V_HF_SAP_INOUT_DAILY` 与 `V_SAP_HFFN_CRKLSZ`。
4. 新增库存/出入库 ODS/DWD 表迁移。
5. 新增同步任务服务：手动同步、增量同步、分批读取、幂等 upsert、任务日志、错误日志。
6. 新增库存/出入库查询服务和 SQL 模板。
7. 新增物管问答最小链路：业务域识别、意图分类、参数抽取、程序查中间库、LLM 润色。
8. 写 focused tests、compile、static scan、review 材料。

---

## 四、M2 前端任务清单

1. 在智能问答 domain switch 中增加物管入口或后端 readiness 后显示入口。
2. 新增 `frontend/src/api/materialManagement.ts`。
3. 复用 BusinessChatPage、streamingApi、ResultTable 展示库存/出入库结果。
4. 展示查询条件、来源中间库表、同步批次、数据日期。
5. 不改变现有物流和计划 BOM 页面行为。

---

## 五、M2 验收标准

1. Oracle 只读 smoke test 通过，且无密钥泄露。
2. 可从 Oracle MID 抽取受控小批量库存/出入库数据写入中间库。
3. 重复同步不产生重复脏数据。
4. 同步日志和错误日志可追溯。
5. 至少 5 个库存/出入库测试问题可基于中间库回答。
6. 前端可进入物管问答入口并展示库存/出入库结果。
7. 现有物流、计划 BOM、功率预测功能回归通过。

---

## 六、M2 禁止事项

1. 不全量导出 Oracle 大表。
2. 不让用户问答直接查 SAP Oracle MID。
3. 不让 LLM 自由生成 SQL 并执行。
4. 不把真实账号密码写入文档、日志、代码注释或提交记录。
5. 不扩展到采购、工单、SAP BOM，除非 M2 验收后另开任务。
