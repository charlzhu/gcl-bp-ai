# 最终验收说明：计划 BOM 功率问答直接关联 BOM 测算效率段

## 问题

用户问：`NT12R/66GDF(华阳阳泉-2025-01048) 的BOM搭配，莱茵基准，单一功率620需求，需要芜湖什么效率段投产`。

旧行为错误进入“需要补充配置”澄清；业务反馈该 BOM 单存在，应直接用功率测算关联 BOM，得到“芜湖 25.6% 可以满足”这类结果。

## 根因

1. 该 BOM 的接线盒材料描述只有线长 `+400/-200mm`，未显式写 `4mm²/6mm²` 线径。旧的 BOM→功率配置解析在缺线径时直接将 cable 标记为 unresolved，导致 QA 链路认为功率预测配置不完整，从而触发澄清，而不是继续调用功率推荐。
2. 同类功率模型问题里，“版型 + 两个配置项 + 相差多少”本质是功率模型 option 影响值对比，不依赖订单；若被普通 BOM 缺订单逻辑拦截，会错误追问订单号。

## 修复

1. 在 `power_config_resolver_service.py` 中优化接线盒 cable 解析：
   - BOM 同时提供线长和线径：继续按 BOM 原文映射；
   - BOM 只提供线长：从当前功率模型默认 cable option 中解析线径，拼出同线长 option；
   - 拼出的 option 必须存在于当前模型真实有效 option 中，否则仍返回 unresolved，避免编造或 hardcode。
2. 在 `qa_service.py` 中优化供应商推荐答案：
   - 答案正文直接给出供应商建议效率段；
   - 保留明细表中的预测比例、CTM、中心功率、落档比例预估。
3. 在 NLU / QA 链路中支持 `plan_power_factor_effect_compare`：
   - 对“NT12-66GDF，汇流条 A 和 B 相差多少”这类问题，按 active 功率模型真实 option 取影响值差异；
   - 不再要求订单号；
   - 若版型、配置项或有效 option 不完整，继续 fail-closed 追问或返回不可计算。
4. 新增/调整回归测试：
   - 覆盖“客户实例+年份+单号+莱茵基准+单一功率620+芜湖效率段”直接回答；
   - 覆盖缺线径但线长可映射时使用模型默认线径，并验证仍是模型真实 option；
   - 覆盖无订单配置影响值对比不被订单澄清拦截；
   - 保留未知线长 fail-closed 回归。

## 验证结果

- 业务原问题直接复测：PASS，返回 A/OK，答案包含“芜湖建议从 25.6% 效率段投产”。
- focused regression：`test_nt12_busbar_power_factor_difference_uses_model_options_without_order`，1 passed。
- Plan BOM / Plan Power 相关全量回归：93 passed，2 个 openpyxl 读取 xlsm 扩展 warning，无失败。
- py_compile：通过。
- git diff --check：通过。
- 独立只读 review：通过，无阻塞问题。

## 真实问题复测输出

系统现在返回 A/OK：

`已按订单 GCL-XXJC-JSPS-2025-01048 的 BOM 配置和目标功率比例完成供应商推荐，芜湖建议从 25.6% 效率段投产；可重点关注效率段：25.6%、25.7%。`

明细首行：

- 供应商：芜湖
- 目标功率档：620W
- 目标比例：100.0
- 预测比例：34.2829
- CTM 值：96.29%
- 中心功率：616.36
- 建议效率段：25.6%、25.7%

## 影响范围

- 仅影响计划 BOM 功率问答中 BOM→功率配置解析、供应商效率段回答，以及功率模型配置影响值对比问法。
- 不修改数据库迁移、不新增接口、不修改前端。
- 不影响物流能力。
- 对未知线长/无真实模型 option/缺关键配置的场景仍保持追问或不可计算，不会硬算。

## 验收材料

- `ai/tasks/running/TASK-plan-power-bom-direct-link-efficiency/diff.patch`
- `ai/tasks/running/TASK-plan-power-bom-direct-link-efficiency/test.log`
- `ai/tasks/running/TASK-plan-power-bom-direct-link-efficiency/static-scan.log`
- `ai/tasks/running/TASK-plan-power-bom-direct-link-efficiency/review-result.md`
