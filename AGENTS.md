# AGENTS.md

## 一、文件用途

本文件用于让接手本项目的 Codex / 工程代理在开始工作前，快速理解项目目标、当前边界、工作规则和代码约束。

本文件只定义当前项目执行口径与长期规则，不代表可以越过 `docs/CURRENT_STATUS.md`、`docs/NEXT_TASK.md`、`ai/inbox/requirement.md` 中声明的阶段边界。

---

## 二、项目概述

### 1. 项目名称

经营计划智能助手。

### 2. 已确认的总体定位

用户已确认项目长期方向为：

```text
多 Agent 受控调度 + 多业务域智能问答 + 多工具调用 + 第三方平台数据接入分析 + 普通非业务问答
```

正式总体架构与阶段路线文档：

```text
docs/PLATFORM_OVERALL_ARCHITECTURE_AND_ROADMAP.md
```

长期目标覆盖四大业务域：

1. 物流。
2. 计划。
3. 物控/物管。
4. 经营分析。

平台建设核心边界：

1. LLM 负责理解、拆解、归一化辅助和答案表达。
2. 后端确定性代码负责查数、计算、校验和追溯。
3. 用户问答优先基于智能助手中间库。
4. SAP Oracle MID、ERP、MES、WMS、TMS 等外部系统应作为同步源或受控工具源，不作为用户实时问答直查库。
5. 多 Agent 与多工具调用必须受白名单、权限、审计日志和阶段边界控制。
6. 用户可见回答不得暴露 SQL、表名、字段名、query_key、planner、guardrail、schema、raw/debug、LLM 等内部技术内容。

### 3. 当前阶段口径

当前阶段口径已从“计划 BOM 功率预测 M1”刷新为：

```text
物管域 SAP Oracle MID 数据同步、智能问数与前端适配建设
```

当前状态：

```text
M1：数据资产审计、同步方案、中间库建模、智能问数链路、计划 BOM SAP 数据源改造、前端适配方案、Oracle 只读 smoke test 报告 —— 已完成。
```

下一步建议：

```text
M2：库存 / 出入库同步 MVP + 物管问答前端入口 MVP。
```

首批范围只允许聚焦：

```text
V_HF_SAP_INOUT_DAILY
V_SAP_HFFN_CRKLSZ
```

### 4. 历史能力基线仍需保持

上一阶段“物流 + BOM 全量样例题真实网页 E2E”已形成重要基线：

- 真实网页 E2E：`3281/3281` 完成，`PASS=3281 / FAIL=0`
- 物流：`A=656 / B=178 / C=69 / D=0`
- BOM：`A=86 / B=40 / C=3 / D=0`
- BOM QA API E2E：`30/30`
- BOM 多问法语义回归：`129/129`
- 物流 903 语义回归：`1559/1559`
- 前端 build：通过

后续任何开发不得破坏：

1. 物流问答主链路。
2. 计划 BOM Excel 导入、查询、QA、消歧与对比能力。
3. 计划 BOM 功率预测已沉淀的文档和阶段边界。
4. 前端现有物流 / 计划 BOM 问答体验。
5. 用户可见回答业务化与技术泄露防护。

---

## 三、当前必须读取的任务资料

每次开始工作前必须先读取：

1. `AGENTS.md`
2. `README_WORKSPACE.md`
3. `docs/PLATFORM_OVERALL_ARCHITECTURE_AND_ROADMAP.md`
4. `docs/CURRENT_STATUS.md`
5. `docs/NEXT_TASK.md`
6. `docs/HANDOFF.md`（如存在）
7. `ai/protocols/company_task_protocol.md`
8. `ai/company/roles/technical_manager.md`
9. `ai/hermes_skills/company-code-builder/SKILL.md`
10. `ai/inbox/requirement.md`
11. `ai/inbox/attachments_manifest.md`
12. `ai/inbox/attachments/` 下与本轮任务相关的附件

进入物管 SAP MID M2 前，还必须读取：

1. `docs/MATERIAL_MANAGEMENT_SAP_MID_DATA_ASSET_AUDIT.md`
2. `docs/MATERIAL_MANAGEMENT_MIDDLE_DB_MODEL_PLAN.md`
3. `docs/SAP_MID_SYNC_DESIGN.md`
4. `docs/MATERIAL_MANAGEMENT_AI_QUERY_PLAN.md`
5. `docs/PLAN_BOM_SAP_DATA_SOURCE_MIGRATION_PLAN.md`
6. `docs/FRONTEND_MATERIAL_MANAGEMENT_ADAPTATION_PLAN.md`
7. `docs/SAP_MID_INTEGRATION_ROADMAP.md`
8. `docs/SAP_MID_ORACLE_SMOKE_TEST_REPORT.md`

如果附件不存在、文件名不一致或无法读取，必须停止并报告，不允许编造附件内容。

---

## 四、当前 M2 目标与边界

### 1. M2 目标

```text
库存 / 出入库同步 MVP + 物管问答前端入口 MVP
```

M2 是总规中“物控/物管域 SAP MID 数据接入与问答 MVP”的近期落地切片。

M2 只验证：

1. 第三方平台只读同步源接入。
2. 智能助手中间库分层沉淀。
3. 物控/物管域最小问答链路。
4. 前端多业务域入口扩展。
5. 同步与问答结果可追溯。

M2 不验证完整多 Agent、多工具、RAG、经营分析和全域 NL2SQL 能力。

### 2. M2 前置阻塞

进入 M2 开发前必须处理：

1. 安装并锁定 Oracle Python 驱动，优先 `oracledb`。
2. 使用 `SAP_ORACLE_*` 环境变量完成只读连接 smoke test。
3. 验证 `SELECT 1 FROM dual`。
4. 验证首批白名单视图字段结构。
5. 对首批两个视图执行 count 与 `ROWNUM <= 5` 小样本。
6. 不输出真实 host、user、password、DSN、连接串或其他密钥。
7. 确认 Oracle 账号只读权限和查询边界。

### 3. M2 后端范围

1. 新建或完善 `backend/app/domains/material_management/` 基础目录。
2. 新增 Oracle 基础设施层或遵循当前配置规范增加 Oracle client/config。
3. 新增白名单视图注册：只开放 `V_HF_SAP_INOUT_DAILY` 与 `V_SAP_HFFN_CRKLSZ`。
4. 新增库存 / 出入库 ODS/DWD 表迁移。
5. 新增同步任务服务：手动同步、增量同步、分批读取、幂等 upsert、任务日志、错误日志。
6. 新增库存 / 出入库查询服务和受控 SQL 模板。
7. 新增物管问答最小链路：业务域识别、意图分类、参数抽取、程序查中间库、LLM 润色。
8. 写 focused tests、compile、static scan、review 材料。

### 4. M2 前端范围

1. 在智能问答 domain switch 中增加物管入口，或在后端 readiness 后显示入口。
2. 新增 `frontend/src/api/materialManagement.ts`。
3. 复用 BusinessChatPage、streamingApi、ResultTable 展示库存 / 出入库结果。
4. 展示查询条件、来源中间库表、同步批次、数据日期。
5. 展示空结果、错误、暂不支持、需要澄清等状态。
6. 不改变现有物流和计划 BOM 页面行为。

### 5. M2 禁止事项

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

## 五、关键业务规则

### 1. SAP Oracle MID 与智能助手中间库规则

1. SAP Oracle MID 只作为外部同步源。
2. 面向用户的智能问答必须基于智能助手中间库。
3. 不允许用户问答实时直接查询 SAP Oracle MID。
4. 不允许全量导出 Oracle 大表。
5. 不允许将 `.env` 中真实连接信息写入文档、日志、代码注释或提交记录。
6. 任何 Oracle 连接测试都必须只读、小样本、可审计。

### 2. LLM 与后端职责边界

LLM 只允许负责：

1. 领域识别。
2. 意图识别。
3. 槽位抽取。
4. 同义词归一化辅助。
5. 多问法理解与受控拆解候选。
6. 答案表达。

后端确定性代码必须负责：

1. 数据同步。
2. 中间库查询。
3. SQL 模板和 SQLPlan 校验。
4. 业务指标计算。
5. 功率预测、齐套缺料、预算达成率等公式型计算。
6. 工具调用权限、参数校验和审计。
7. 版本追溯。
8. 用户可见回答的技术泄露防护。

不允许让 LLM 直接计算业务事实、自由生成 SQL 并执行，或直接调用未注册工具。

### 3. 计划 BOM 与功率预测历史规则

计划 BOM 功率预测能力属于现有 **计划 BOM 业务域** 的子能力，不新建独立业务域。

若后续继续该专项，必须遵守：

1. `GCL功率测试基准` xlsm 是动态模型，不是静态明细表。
2. 功率预测结果必须由后端确定性计算引擎产生。
3. LLM 不允许直接计算功率档位、比例、供应商效率或匹配度。
4. 功率预测相关建议使用 `plan_power_` 前缀。
5. 继续开发前必须以 `docs/PLAN_POWER_EXCEL_FORMULA_AUDIT.md` 与 `docs/PLAN_POWER_IMPLEMENTATION_PLAN.md` 为边界，并等待用户确认新阶段。

### 4. BOM 配置搭配问询样例文档规则

`BOM配置搭配问询：.docx` 只作为业务问题类型和问法参考。

必须遵守：

1. 文档中的版型号是假的。
2. 文档中的订单号是假的。
3. 文档中的评审号是假的。
4. 文档中的项目名是假的。
5. 文档中的问题不能当成真实验收数据。
6. 不能 hardcode 文档中的问题或答案。
7. 不能为了让样例题通过而伪造结果。
8. 正式测试题必须基于当前项目真实 BOM 数据自行生成。

---

## 六、当前代码状态判断规则

最重要规则：

**不要根据历史聊天、历史补丁、历史 zip 文件或上位总规文档，推断当前仓库已经具备某项能力。**

一切必须遵循：

1. 先读取当前仓库代码。
2. 先判断当前能力是否已真实合入。
3. 再决定是否继续开发或修复。
4. 如果文档与代码冲突，以当前代码和本轮任务要求为准，并在报告中说明差异。

严禁行为：

1. 不要假设“之前做过的版本”一定已经在当前仓库里。
2. 不要用历史 zip 名称当事实来源。
3. 不要跳过代码审查，直接继续写下一版。
4. 不要因为看到样例题就 hardcode 答案。
5. 不要因为总规已确认就直接实现后续远期阶段。

---

## 七、Codex 工作流程要求

### 第一步：先审查再开发

每次开始工作时，必须先输出：

1. 当前仓库已完成能力判断。
2. 当前未完成能力判断。
3. 本次任务是否与当前仓库状态一致。
4. 本轮允许修改范围。
5. 本轮禁止修改范围。

### 第二步：复杂任务先给计划

如果任务涉及多个文件、多个步骤或多个工具，必须先给计划，再开始修改。

阶段型任务必须先确认当前阶段边界，不得自动进入下一阶段。

### 第三步：增量修改优先

1. 优先增量修改。
2. 不大规模重构目录结构。
3. 不轻易改接口命名。
4. 不随意改变返回字段结构。
5. 不污染现有物流、计划 BOM、功率预测主链路。

### 第四步：中文注释

所有新增和修改代码必须写中文注释。

中文注释要求：

1. 说明函数功能。
2. 说明参数含义。
3. 说明返回值。
4. 说明重要业务逻辑。
5. 对复杂判断、兼容逻辑、降级逻辑写清楚原因。

### 第五步：完成后必须输出

1. 修改文件清单。
2. 关键改动说明。
3. 测试方法。
4. 风险点。
5. 当前仍未解决的问题。
6. 是否影响现有 BOM / 物流 / 功率预测能力。
7. 是否遵守本轮阶段边界。
8. 是否未自动 commit / push / deploy。

---

## 八、完整交付模式与阶段边界

当用户明确说“完整交付模式”时，按完整交付规则执行。

但如果 `ai/inbox/requirement.md`、`docs/CURRENT_STATUS.md` 或 `docs/NEXT_TASK.md` 明确规定“本轮只执行 M1 / M2 / 只产出文档 / 完成后等待确认”，则必须遵守该阶段边界。

即使总规文档已经确认，也不能自动进入完整多 Agent、多工具、RAG、经营分析或后续未确认阶段。

---

## 九、代码风格要求

### 后端

1. 保持当前 FastAPI / service / repository 分层风格。
2. 优先复用现有 service，不重复造一套新 service。
3. 保持当前 logistics 域目录结构不被破坏。
4. 物管域建议归入 `backend/app/domains/material_management/`，不要新建割裂的 `sap` 业务域。
5. 计划 BOM 功率预测能力应作为 `plan_bom` 域子能力接入。
6. 后续如新增功率预测模块，应保持边界清晰，避免污染 BOM 查询主链路。
7. 后续如新增 Query Planning / NL2SQL / 工具层能力，必须先 shadow / 受控 / 可审计，不得直接替换成熟主链路。

### 前端

1. 保持当前 Vue3 + Element Plus 风格。
2. 当前前端以“可联调、可展示、可回溯”为优先。
3. 不要一上来做重 UI 重动画。
4. M2 如增加物管入口，必须复用现有 BusinessChatPage / streamingApi / ResultTable 等成熟组件。
5. 不改变现有物流和计划 BOM 页面行为。
6. 用户可见回答不得暴露技术实现细节。

### 命名

1. 指标名、字段名、模板名与当前项目统一。
2. 若引入新命名，必须与现有语义兼容。
3. 物管域内部目录建议使用 `material_management`。
4. “物控/物管”的用户展示命名需业务确认后统一。
5. 功率预测相关建议使用 `plan_power_` 前缀。

---

## 十、安全与配置要求

严禁提交：

1. `.env`
2. 真实数据库密码
3. Redis / Milvus 密码
4. Oracle / SAP / ERP / MES / WMS / TMS 生产连接串
5. API Key
6. 真实 host、user、password、DSN

应只保留：

1. `.env.example`
2. 示例配置
3. 安全占位值

打包与提交前应清理：

1. `__pycache__/`
2. `*.pyc`
3. `__MACOSX/`
4. `.idea/`
5. `.pytest_cache/`
6. `.env`
7. `.DS_Store`

---

## 十一、当前优先级

### 当前第一优先级

完成阶段口径统一，并以 `docs/PLATFORM_OVERALL_ARCHITECTURE_AND_ROADMAP.md` 作为上位规划依据。

### 当前第二优先级

在用户确认启动后，进入：

```text
M2：库存 / 出入库同步 MVP + 物管问答前端入口 MVP
```

M2 必须先处理 Oracle 只读 smoke test 前置阻塞，再进入同步、中间库、问答和前端入口开发。

### 当前第三优先级

保持并回归既有能力：

1. 物流问答。
2. 计划 BOM 问答。
3. 计划 BOM 功率预测相关能力。
4. 前端智能问答现有体验。

当前不要因为总规确认而直接扩完整多 Agent、完整多工具、经营分析、RAG 或全域统一入口。

---

# Hermes 命令安全执行规则

为了减少人工审批阻塞，并保证本机项目安全，后续执行命令时必须遵守：

1. 禁止使用以下高风险命令模式：
   - `curl ... | bash`
   - `curl ... | sh`
   - `wget ... | bash`
   - `command | python`
   - `command | python -`
   - `command | node`
   - `command | bash`
   - `python - <<'PY'`
   - `bash - <<'SH'`
   - 将外部命令输出直接 pipe 给解释器执行或处理

2. 如果需要处理 JSON / 日志 / 命令输出：
   - 先将输出保存到 `tmp/hermes/` 目录下的临时文件
   - 再调用项目内固定脚本处理
   - 不允许在 shell 命令中临时拼接大段 Python / Bash 代码

3. 推荐模式：

   ```bash
   mkdir -p tmp/hermes
   hermes kanban show <task_id> --json > tmp/hermes/kanban_<task_id>.json
   backend/.venv/bin/python scripts/dev/parse_kanban_show.py tmp/hermes/kanban_<task_id>.json
   ```
