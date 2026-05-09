# TASK-plan-power-docx-question-regression 最终验收报告

## 1. 任务结论

本轮已完成“从 `BOM配置搭配问询：.docx` 的 12 道功率题抽象测试模板，并接入真实 BOM / 显式配置 QA 链路”的实现与验收。

完成结果：

- 已新增 `tests/business_acceptance/test_plan_power_docx_question_regression.py`。
- 已确认附件第二部分功率题数量为 `12/12`，并把 12 道题全部纳入回归基线。
- 订单类问题不使用 docx 假订单/假评审号，改为从当前真实 BOM 数据中动态选择可解析订单。
- 显式配置类问题已支持不依赖订单进入 QA/NLU：自然语言配置 -> NLU 槽位 -> M4 确定性配置解析 -> M3 确定性功率推荐。
- 已修复目标功率比例解析：`620:625 1:1`、`715和720 2:8`、`各占一半`、`620W 50%，625W 50%`。
- 已补充“各家供应商”与“指定单供应商”区分，避免 `通威、爱旭、时创等各家` 被误当成只查单个供应商。
- 已补充推荐结果中的“建议效率段”列，用于回答“哪个效率段/效率段在哪里”。

## 2. 覆盖范围

### 2.1 docx 第一部分 BOM 配置问询

新增测试覆盖：

1. 真实订单之间五类核心材料差异对比：2 个业务变体。
2. 真实单订单五类核心材料规格查询：2 个业务变体。
3. 多个真实订单生成五类核心材料表格：2 个业务变体。

### 2.2 docx 第二部分 12 道功率题

新增测试覆盖：

1. NT12/66GDF 订单类供应商推荐：3 个业务变体。
2. NT12R/66GDF 订单类指定芜湖效率段：3 个业务变体。
3. 显式配置 + 各家供应商效率段：例题 3-8，每题 2 个业务变体，共 12 个。
4. 显式配置 + 指定芜湖效率段：例题 9-12，每题 2 个业务变体，共 8 个。
5. 附件完整性检查：确认 docx 中功率例题 `12/12` 被加载。

合计新增 docx regression：`33` 个测试。

## 3. 修改文件

本轮核心修改/新增：

- `tests/business_acceptance/test_plan_power_docx_question_regression.py`
  - 新增 docx 派生验收测试。
  - 从附件读取 12 道功率题数量作为基线。
  - 真实 BOM 订单动态选择；显式配置题不 hardcode 假订单/答案。

- `backend/app/domains/plan_bom/services/nlu_center_service.py`
  - 扩展计划 BOM 功率类 intent 识别。
  - 新增目标功率比例解析：`A:B x:y`、`A和B x:y`、百分比、各占一半。
  - 新增显式功率配置槽位抽取：焊带、玻璃、汇流条、接线盒、标板。
  - 新增供应商识别安全逻辑：区分“各家/哪些家”与指定单供应商。
  - 型号支持 `/` 与 `-` 归一，如 `NT12R/66GDF -> NT12R-66GDF`。

- `backend/app/domains/plan_bom/services/power_config_resolver_service.py`
  - 新增显式配置解析入口 `resolve_explicit_configuration()`。
  - 显式配置使用 active 功率模型真实 option 做确定性映射。
  - 对混合焊带、只写双镀/单镀玻璃、只写接线盒长度等业务口语写法进行可追溯降级映射并输出 warning。

- `backend/app/domains/plan_bom/services/qa_service.py`
  - 订单类问题仍走 BOM -> M4 -> M3。
  - 无订单但有显式配置的问题走 M4 显式配置解析。
  - unresolved/candidate/partial 状态仍 fail-closed，不调用 M3。
  - 推荐表新增“建议效率段”。

## 4. 根因说明

本轮开始前，核心 M3/M4/M5 链路已能跑通基础问题，但 docx 12 道功率题直接回放时不能证明全部支持，主要根因是：

1. docx 原题中订单/评审号/项目名多为示例，不能直接作为真实验收数据。
2. 旧 NLU 对功率目标比例只覆盖 `620W 50%` 这类明确写法，无法正确解析 `620:625 1:1`、`715和720 2:8`。
3. QA 旧功率分支默认依赖订单号，显式配置类问题没有独立进入 M4/M3 的路径。
4. `通威、爱旭、时创等各家` 这类枚举示例容易被误识别成指定某一个供应商。
5. “哪个效率段/效率段在哪里”需要在推荐表里输出可解释效率段，而不是只返回供应商匹配度。

## 5. TDD / 验证结果

### RED

新增 `test_plan_power_docx_question_regression.py` 后首次 focused 失败，符合预期，暴露：

- 原链路返回 `B/CLARIFICATION_REQUIRED`。
- 显式配置未接入 QA。
- 目标比例解析不足。
- 全供应商问法被误识别为单供应商。

### GREEN / 回归

已运行并通过：

```text
PYTHONPATH=. pytest tests/business_acceptance/test_plan_power_docx_question_regression.py -q
33 passed in 10.12s
```

```text
PYTHONPATH=. pytest tests/business_acceptance/test_plan_power_docx_question_regression.py tests/business_acceptance/test_plan_power_m3_prediction_engine.py tests/business_acceptance/test_plan_power_m4_config_resolver.py tests/business_acceptance/test_plan_power_m5_qa_integration.py -q
59 passed, 2 warnings in 25.94s
```

```text
PYTHONPATH=. pytest -q
107 passed, 2 warnings in 32.96s
```

```text
python -m compileall -q backend/app tests
exit 0
```

```text
npm run build
exit 0；仅 Vite chunk-size warning
```

```text
git diff --check
exit 0
```

静态扫描：

- 新增行 secret/shell/eval/pickle/SQL-format scan：无发现。
- 旧功率模型 admin token 字符串精确扫描：无发现。

说明：pytest 中 2 个 warning 为 openpyxl 读取 xlsm 扩展/条件格式提示，属于既有非阻塞 warning。

## 6. Reviewer 结果

第一次 reviewer 因大工作区/上下文过大超时，已按 review skill 生成精简 `review_bundle.md` 后重跑。

独立 reviewer 结论：`passed=true`。

Reviewer JSON：

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": [],
  "suggestions": [
    "Move or expose the efficiency-segment selection now implemented in QA _suggest_efficiency_segment as an M3 recommendation output to make the M3/M5 ownership boundary more explicit.",
    "Derive the implicit cable gauge for explicit接线盒 length-only inputs from the active model default option rather than hardcoding 4mm² before checking defaults, so future model changes remain safe.",
    "Broaden all-supplier markers to include phrases such as 所有电池供应商/全部电池供应商 when named suppliers are present, and add targeted tests for that wording.",
    "Add focused guardrail tests with use_llm=True/mocked LLM to ensure power intents cannot be downgraded or rerouted when deterministic rule extraction already found order/supplier/benchmark/ratio slots."
  ],
  "summary": "Review passed: the changed flow keeps NLU to slot extraction, routes explicit/order configurations through M4, gates unresolved states before M3, and covers the required docx ratio and supplier cases, with only hardening suggestions."
}
```

Reviewer 建议均为后续 hardening，不阻塞本轮验收。

## 7. 验收材料

- `ai/tasks/running/TASK-plan-power-docx-question-regression/diff.patch`
- `ai/tasks/running/TASK-plan-power-docx-question-regression/test.log`
- `ai/tasks/running/TASK-plan-power-docx-question-regression/review_bundle.md`
- `ai/tasks/running/TASK-plan-power-docx-question-regression/final-acceptance.md`

## 8. 影响范围

- 影响：计划 BOM QA 的功率预测/供应商推荐问法、显式配置解析、目标比例解析、推荐表展示字段。
- 不影响：物流问答、BOM 上传入口、功率模型上传/激活入口、旧 token 设计未恢复。
- 安全边界：LLM/NLU 不参与功率数值计算；M3/M4 仍为确定性服务；配置未解析完全时仍停止计算并要求补充信息。

## 9. 后续建议

1. 将“建议效率段”从 QA 层 helper 下沉或暴露到 M3 推荐结果中，使 M3/M5 职责边界更清晰。
2. 显式接线盒只写长度时，进一步从 active 默认 option 解析线径，而不是固定优先尝试 `4mm²`。
3. 继续扩充“所有电池供应商/全部电池供应商”等全供应商同义词测试。
4. 增加 mock LLM guardrail 测试，验证 LLM 候选不能覆盖规则层已抽取的功率关键槽位。
