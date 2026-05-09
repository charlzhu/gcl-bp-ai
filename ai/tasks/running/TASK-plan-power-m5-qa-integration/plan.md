# TASK-plan-power-m5-qa-integration 实施计划

## 1. 当前仓库已完成能力判断

- M2：功率模型版本化入库、active 模型读取、管理导入/激活链路已由用户验收通过。
- M3：`PowerPredictionEngine` 与 `PowerRecommendationService` 已由用户验收通过，负责确定性功率预测与供应商推荐。
- M4：`PlanBomPowerConfigResolverService` 已由用户验收通过，负责从真实 BOM 映射 M3 可消费的 `configuration`。
- 现有 PlanBom QA：已有 `/plan-bom/qa/ask`、`PlanBomNluCenterService`、`PlanBomQaService`、`PlanBomAnswerPresentationService` 和前端经营计划智能助手 PlanBom 调用链路。

## 2. 当前未完成能力判断

- 现有 QA 对功率类问题仍按旧口径进入 `power_cell_requirement` C 类拒答，尚未调用 M4/M3。
- NLU 尚未抽取目标功率档比例、供应商、标板基准等功率问答槽位。
- QA presentation 尚未提供功率预测 / 供应商推荐的结构化表格与可追溯解释。
- 前端自动识别关键词尚未显式覆盖“功率预测 / 供应商推荐 / 目标功率 / 目标比例”等 PlanBom 功率问答词。

## 3. 本次任务是否与当前仓库状态一致

一致。用户已确认 M4 验收通过，本轮进入 M5：接入 PlanBom QA / 智能问答链路。

## 4. 本轮允许修改范围

- `backend/app/domains/plan_bom/services/nlu_center_service.py`
- `backend/app/domains/plan_bom/services/qa_service.py`
- `backend/app/domains/plan_bom/services/answer_presentation_service.py`（仅必要的标题/展示类型优化）
- `backend/app/domains/plan_bom/schemas/qa.py`（仅必要的展示类型兼容）
- `backend/app/api/deps.py`（注入 M3/M4 服务）
- `frontend/src/api/planBom.ts`（类型补齐）
- `frontend/src/views/business-chat/BusinessChatPage.vue`（自动路由关键词 / 示例问题 / 表格适配，不做重 UI）
- `tests/business_acceptance/test_plan_power_m5_qa_integration.py`
- `ai/tasks/running/TASK-plan-power-m5-qa-integration/*`

## 5. 本轮禁止修改范围

- 不新建数据库迁移，不改 `plan_power_*` 表结构。
- 不修改 M2/M3/M4 已验收的确定性计算规则，除非测试暴露必要兼容问题。
- 不让 LLM 计算功率预测结果；LLM 只允许理解候选与表达优化。
- 不执行 Excel VBA / 宏。
- 不 hardcode `BOM配置搭配问询：.docx` 中假订单、假版型、假项目名、假评审号或假答案。
- 不自动合并 main，不自动部署生产，不修改 `.env` / token / 密钥。

## 6. TDD 验收样例

1. 真实订单功率预测问答：
   - 从真实 BOM 动态找一条 M4 可完整解析订单。
   - 问：`订单XXXX做功率预测`。
   - 期望：NLU intent 命中功率预测，QA 返回 A 类 OK，raw_result 包含 `bom_config_resolution` 与 `power_prediction`，表格含功率档分布。
2. 目标功率比例供应商推荐问答：
   - 问：`订单XXXX目标620W 50%，625W 50%，推荐供应商`。
   - 期望：调用 M4 + M3 推荐服务，返回候选供应商、匹配度、目标比例差异。
3. 显式供应商预测：
   - 问：`订单XXXX按芜湖供应商预测功率分布`。
   - 期望：supplier 槽位被采用，预测结果 supplier_name 为对应供应商。
4. 缺订单功率问题受控追问：
   - 问：`帮我做功率预测`。
   - 期望：B 类追问，不调用计算引擎瞎算。
5. M4 partial / candidate 状态受控返回：
   - 无法唯一定位或配置未解析时，不进入 M3 计算；返回 B 类追问或 C 类空结果，并给 candidate / unresolved trace。
6. 回归：
   - M4 focused、M3 focused、M2 focused、全量 tests、compileall、frontend build、diff check 均通过。

## 7. 实施步骤

1. 扩展 NLU：新增功率预测/推荐 intent，抽取订单、供应商、标板、目标功率比例。
2. 扩展 QA：新增 `_power_prediction_response`，串联 M4 配置解析、M3 单供应商预测与推荐服务。
3. 构造确定性表格：功率档分布、配置追溯、推荐供应商行，所有数值来自 M3/M4。
4. 前端轻量适配：补类型、关键词路由、示例问题；继续渲染后端返回 table，不在前端计算业务结果。
5. 编写 M5 验收测试并跑回归。
6. reviewer 审查，失败最多返工 2 次。
7. 生成 `diff.patch`、`test.log`、`final-acceptance.md`。
