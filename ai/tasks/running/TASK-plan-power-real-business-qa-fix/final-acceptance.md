# TASK-plan-power-real-business-qa-fix 最终验收报告

## 1. 任务目标

基于真实业务人员后台日志，按 TDD 修复 Plan BOM 功率 QA 暴露的五类问题：

1. 真实业务口语配置抽取：`0.24焊带`、`双镀玻璃`、`300/200线长` 等不能错位。
2. `线长/线缆长度/线缆` 应映射到接线盒/线缆材料，BOM 查询不能漏接线盒行。
3. `615功率`、`单一需求720功率` 应在供应商/效率推荐语境中解析为 100% 单一目标功率。
4. 订单类功率推荐中，用户显式给出的 `300/200线长` 应由 M4 确定性解析并覆盖 BOM 缺失线径，不应误要求补充线缆长度。
5. 订单尾号命中多个 BOM 候选时，澄清提示应列出候选，并提示用户输入名称与候选名不一致。

同时根据 reviewer 阻塞问题，补充负例保护：订单尾号、年份、型号中的数字不能误抽为目标功率。

## 2. 修改文件

- `backend/app/domains/plan_bom/config/material_aliases.json`
- `backend/app/domains/plan_bom/services/nlu_center_service.py`
- `backend/app/domains/plan_bom/services/power_config_resolver_service.py`
- `backend/app/domains/plan_bom/services/qa_service.py`
- `frontend/src/views/business-chat/BusinessChatPage.vue`
- `tests/business_acceptance/test_plan_power_real_business_qa_regression.py`

## 3. 关键修复说明

### 3.1 NLU 口语配置抽取

新增/强化规则层槽位抽取：

- `0.24焊带` -> `ribbon=0.24`
- `0.24+0.26焊带` -> `ribbon=0.24+0.26`
- `双镀玻璃` -> `glass=双镀`
- `高透玻璃+间隙铝膜` -> `glass=高透+间隙铝膜`
- `300/200线长` -> `cable=300/200线长`

该层只做意图和槽位抽取，不做功率数值计算。

### 3.2 线长材料别名

将以下别名纳入 `junction_box`：

- `线长`
- `线缆长度`
- `线缆`
- `接线盒线长`
- `线长搭配`

因此真实业务问“玻璃焊带线长汇流条”时，结果包含接线盒/线缆行，不再只返回玻璃、焊带、汇流条。

### 3.3 单一目标功率解析与负例保护

支持：

- `615功率` -> `{ "615": 1.0 }`
- `单一需求720功率` -> `{ "720": 1.0 }`

并增加保护：

- `订单00104功率预测` 不抽 `104W`
- `订单2025-01073功率预测` 不抽 `1073W`
- `深圳建融-2025-00615功率预测...` 不抽 `615W`
- `项目-00615功率预测...` 不抽 `615W`
- `NT720功率预测，供应商推荐` 不抽 `720W`

### 3.4 M4 显式配置覆盖 BOM 缺口

`qa_service` 将用户显式配置传入 `PlanBomPowerConfigResolverService.resolve(...)`。

M4 在 active 模型 option 中确定性归一：

- 用户输入 `300/200线长`
- BOM 行有 `+300/-200mm` 但无线径
- active 模型默认 cable 为 `+300/-200mm（4mm²）`
- 最终 resolved cable 为 `+300/-200mm（4mm²）`

M4 未 resolved 时仍 fail-closed，不调用 M3。

### 3.5 多候选澄清

对于 `创维210N—00106...`：

- 仍识别为需要澄清，因为 `00106` 在真实库中命中多个 BOM 候选。
- 澄清文案列出候选订单名、订单号、版本。
- 提示 `创维210N` 未匹配当前候选名称，避免业务误以为系统已找到“创维”实例。

### 3.6 前端展示辅助

`BusinessChatPage.vue` 补齐既有验收要求的展示 helper：

- `resolveAssistantResultLayout`
- `shouldShowMetricCards`
- `shouldShowResultTable`
- `resolveAssistantReplyKicker`

该改动只基于后端 `presentation` 做展示布局，不参与业务计算。

## 4. TDD 验证

### RED

新增真实业务回归测试后，先观察到失败：

- 初始真实业务 5 点回归失败；
- reviewer 负例 `订单00104功率预测` / `订单2025-01073功率预测` 失败；
- reviewer 第二轮负例 `深圳建融-2025-00615...` / `项目-00615...` / `NT720...` 失败。

### GREEN

修复后 focused 通过：

```text
tests/business_acceptance/test_plan_power_real_business_qa_regression.py
10 passed
```

## 5. 完整验证结果

已执行并通过：

```text
focused: 10 passed
related: 73 passed, 2 warnings
full: 134 passed, 2 warnings
compileall: passed
frontend build: passed
static scan: No findings in targeted changed files / added lines
reviewer: passed=true
```

说明：`openpyxl` 对 xlsm 扩展和条件格式的 warning 为既有解析库提示，不影响本轮结果。

## 6. Reviewer 结果

独立 reviewer 最终结论：

```text
passed=true
阻塞问题：无
```

非阻塞建议：

1. 后续可让 M4 defaults 阶段跳过已显式解析的 `supplier/benchmark/cell_size`，避免 trace 来源被默认值覆盖。
2. 多文件实例候选澄清可进一步补充 file instance/source 标识。
3. 后续可扩展更多口语别名，例如 `超高透玻璃`、`焊带0.24`。

## 7. 安全与边界

- 未恢复 `X-Plan-Power-Admin-Token`。
- 未恢复 `plan_power_admin_token`。
- 未恢复 `require_plan_power_admin`。
- 未新增密钥、token、密码或连接串。
- LLM/NLU 仍只负责意图和槽位抽取。
- M4/M3 deterministic 服务仍负责配置解析、功率预测、供应商推荐和效率段计算。
- 前端不解析 Excel、不执行宏、不计算功率。

## 8. 验收材料

- `ai/tasks/running/TASK-plan-power-real-business-qa-fix/test.log`
- `ai/tasks/running/TASK-plan-power-real-business-qa-fix/diff.patch`
- `ai/tasks/running/TASK-plan-power-real-business-qa-fix/review_bundle.md`
- `ai/tasks/running/TASK-plan-power-real-business-qa-fix/final-acceptance.md`

## 9. 当前结论

本轮五点修复已按 TDD 完成，并通过 focused / related / full / compile / frontend build / static scan / independent reviewer。

可以进入人工验收或后续提交/合并流程。