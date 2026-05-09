# TASK-plan-power-m4-bom-config-resolver 实施计划

## 1. 当前仓库已完成能力判断

- M1 / M1.5：功率预测 Excel 审计、业务口径确认、实施方案已完成。
- M2：功率模型版本化入库、8 张 `plan_power_*` 表、管理 API、导入/激活链路已完成并由用户验收通过。
- M3：`PowerPredictionEngine` 与 `PowerRecommendationService` 已完成并由用户验收通过。
- 当前可复用数据源：`plan_bom_header`、`plan_bom_material_line`、当前 active `plan_power_model_version`、`plan_power_model_sheet`、`plan_power_factor_option`。

## 2. 当前未完成能力判断

- 尚无 `PlanBomPowerConfigResolverService`。
- 尚无 `power_bom_mapping.yaml`。
- 尚无 `power_aliases.json`。
- 尚不能根据真实 BOM 自动把玻璃、间隙膜、互联条、汇流条、接线盒等材料映射为 M3 `configuration`。
- 尚未给无法映射项返回结构化追问 / 人工确认提示。

## 3. 本次任务是否与当前仓库状态一致

一致。用户已明确认可 M3 验收通过，当前进入：

```text
M4：BOM 配置自动映射
```

M4 应在 M3 service 层基础上新增 BOM → 功率模型配置映射能力，但不接入 QA/NLU/前端。

## 4. 本轮允许修改范围

允许新增 / 修改：

```text
backend/app/domains/plan_bom/config/power_aliases.json
backend/app/domains/plan_bom/config/power_bom_mapping.yaml
backend/app/domains/plan_bom/services/power_config_resolver_service.py
tests/business_acceptance/test_plan_power_m4_config_resolver.py
ai/tasks/running/TASK-plan-power-m4-bom-config-resolver/*
```

如确需补充导出，可小范围修改 `backend/app/domains/plan_bom/services/__init__.py`。

## 5. 本轮禁止修改范围

- 不接入 PlanBom QA / NLU / smart-chat。
- 不修改前端。
- 不实现 M5 智能问答链路。
- 不新增数据库迁移。
- 不执行 Excel VBA / 宏。
- 不让 LLM 参与数值计算或配置猜测。
- 不使用 `BOM配置搭配问询：.docx` 中假订单、假版型、假项目名、假评审号作为测试数据。
- 不 hardcode 样例题答案。
- 不破坏现有 BOM 查询、BOM compare、物流问答能力。

## 6. 实施步骤

1. 新增 `power_aliases.json`：维护版型、标板、供应商、材料规格等别名。
2. 新增 `power_bom_mapping.yaml`：维护 BOM 类别到功率模型配置项的映射规则和追问策略。
3. 新增 `PlanBomPowerConfigResolverService`：
   - 定位真实 BOM header。
   - 提取核心材料行。
   - 解析版型、玻璃、间隙膜、焊带、汇流条、接线盒 / 线缆。
   - 映射到 active 功率模型的有效 option。
   - 输出 resolved_config、source_lines、unresolved_items、confidence、candidate options。
4. 新增 M4 测试：
   - 从当前真实 `plan_bom_header` / `plan_bom_material_line` 中动态选择可映射订单。
   - 校验输出包含版型、玻璃、焊带、汇流条、线缆、原始 BOM 描述和置信度。
   - 校验无法映射时返回 unresolved，不瞎猜。
   - 校验映射后的 configuration 可调用 M3 `PowerPredictionEngine`。
5. 运行 focused / M2 / M3 / 全量测试、compileall、diff check。
6. 执行独立 reviewer。
7. 生成 `diff.patch`、`test.log`、`final-acceptance.md`。

## 7. TDD 验收样例

- `test_resolves_real_order_to_power_configuration`：真实订单 → model_code + configuration + source trace。
- `test_resolved_configuration_can_drive_m3_prediction`：M4 输出 configuration 可喂给 M3 预测。
- `test_ambiguous_or_unknown_material_returns_unresolved_item`：未知/冲突材料不能猜测。
- `test_model_aliases_normalize_bom_order_name`：`NT12R/66GDF` → `NT12R-66GDF`。
- `test_missing_or_multiple_order_returns_controlled_status`：未命中/多候选受控返回。
