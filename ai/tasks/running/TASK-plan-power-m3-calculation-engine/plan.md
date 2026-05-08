# TASK-plan-power-m3-calculation-engine 实施计划

## 1. 当前仓库已完成能力判断

1. M1/M1.5 已完成新版 TOPCon Excel 审计、业务口径确认和后续路线设计。
2. M2 已通过用户验收，当前分支基线已包含：
   - `plan_power_*` ORM 与 Alembic 迁移；
   - `PowerExcelParserService`；
   - `PowerModelService`；
   - `PowerModelRepository`；
   - 功率模型上传 / 查询 / 激活管理 API；
   - 新版 `GCL功率测试基准（V2.1）TOPCon 26.04.13.xlsm` 在本地 `logistics_ai` 中已有 active 版本。
3. 当前 M2 解析结果已保存：模型页、配置选项、供应商效率分布、功率档、标板基准、parse issues、`formula_policy=semantic_fixed_mode`。

## 2. 当前未完成能力判断

1. 尚无 `PowerPredictionEngine`：不能脱离 Excel 执行确定性功率预测。
2. 尚无 `PowerRecommendationService`：不能按目标功率档 / 目标比例做供应商推荐与匹配度排序。
3. 尚无 M3 校验用例：`plan_power_model_validation_case` 表仍为空。
4. 尚未把 M3 接入 PlanBom QA / 智能助手；这属于 M5，不在本轮执行。
5. 尚未实现 BOM 材料到功率模型配置的自动映射；这属于 M4，不在本轮执行。

## 3. 本次任务与当前仓库状态一致性

一致。用户已确认 M2 验收通过，并明确进入 M3。当前仓库已经具备 M3 所需的 active 模型版本与结构化模型数据，下一步应实现后端确定性计算引擎与推荐服务。

## 4. 本轮允许修改范围

允许：

1. 新增 / 修改 `backend/app/domains/plan_bom/services/power_prediction_engine.py`。
2. 新增 / 修改 `backend/app/domains/plan_bom/services/power_recommendation_service.py`。
3. 必要时新增 `backend/app/domains/plan_bom/schemas/power_prediction.py` 或等价 schema / dataclass。
4. 必要时在 `PowerModelRepository` 中新增只读查询方法，读取 active 版本、版型、配置选项、供应商效率分布、功率档、标板基准。
5. 使用既有 `plan_power_model_validation_case` 记录 M3 校验用例结果，但不新增迁移。
6. 新增 M3 后端测试，例如 `tests/business_acceptance/test_plan_power_m3_prediction_engine.py`。
7. 更新本任务目录下的 `diff.patch`、`test.log`、`final-acceptance.md`。

## 5. 本轮禁止修改范围

禁止：

1. 不修改前端。
2. 不接入 `/smart-chat`。
3. 不修改 `PlanBomQaService` 可答逻辑。
4. 不实现 M4 BOM 配置自动映射。
5. 不 hardcode `BOM配置搭配问询：.docx` 假订单 / 假版型 / 假项目 / 假答案。
6. 不让 LLM 计算功率预测结果。
7. 不执行 Excel VBA；只能按 M1/M1.5 固化语义翻译宏和公式。
8. 不新增数据库迁移，除非发现 M2 表无法支撑 M3 且必须先报告。

## 6. M3 TDD 验收样例设计

1. 无 active 模型版本时应明确失败。
2. 版型不存在时应明确失败。
3. 配置选项不存在或无效时应明确列出 unresolved items，不得编造。
4. 指定供应商无有效效率分布时不能参与推荐。
5. `normal_cdf` 与 `NORMSDIST` 等价实现需通过固定数学断言。
6. 对至少 10 组可追溯配置执行计算，输出中心功率、效率段功率、功率档概率、加权分布。
7. 计算结果需与从 Excel 公式链 / 当前缓存值抽取的 parity baseline 比较；超过阈值必须失败并记录原因。
8. 推荐服务需覆盖：指定供应商、遍历供应商、目标档不存在、其他档泄漏、覆盖率、排序。

## 7. M3 实施拆解

1. 先补失败测试，定义 M3 输入 / 输出结构和错误边界。
2. 实现 `PowerPredictionEngine`：
   - active 版本读取；
   - 版型定位；
   - 配置项归一匹配；
   - 中心功率计算；
   - 逐效率段计算 actual power；
   - 按功率档计算正态区间概率；
   - 按供应商效率分布加权汇总；
   - 输出完整 trace。
3. 实现 `PowerRecommendationService`：
   - 指定或遍历供应商；
   - 过滤无有效分布供应商；
   - 按目标比例计算 score；
   - 输出推荐排序、目标档占比、差异、泄漏、覆盖率、风险。
4. 生成 / 写入至少 10 组 M3 validation case，确保 baseline 可追溯到 active 模型版本与配置。
5. 运行测试、静态检查、独立 reviewer，必要时返工。
