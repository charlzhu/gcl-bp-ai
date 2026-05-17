# 物流问答答案表达层 / 展示编排层

## 一、设计目标

本轮新增的是物流 data-qa 的答案表达层和展示编排层。

它只在后端确定性 data-qa 结果已经生成之后介入，目标是把已经算好的结果组织成更自然、更专业、更适合业务用户阅读的展示结构。

当前正式总账分布保持不变：

- `A = 656`
- `B = 178`
- `C = 69`
- `D = 0`

## 二、为什么需要答案表达层

原有后端已经能确定性返回 `answer_summary`、`result_table`、`calculation_logic`、`data_scope`、`status` 和 `query_plan`。

但直接把这些字段展示给业务用户，会出现几个问题：

- 成功态容易像技术结果堆叠。
- B 类追问容易显得机械。
- C 类拒答容易被误认为系统错误。
- 用户要求“折线图”“表格”“汇总”时，前端缺少统一展示编排结构。
- 技术字段容易抢占主展示注意力。

答案表达层解决的是“怎么展示”，不是“怎么查数”。

## 三、与主链路边界

答案表达层的位置：

1. `data_qa_planner` 生成受控计划。
2. `repository / service` 执行确定性查询。
3. 后端生成确定性 `LogisticsDataQaResult`。
4. `LogisticsLlmAnswerPresentationService` 生成 `presentation`。
5. 前端按 `presentation.display_type` 动态渲染。

边界：

- 不替代 planner。
- 不新增 query_key。
- 不生成 SQL。
- 不查数据库。
- 不改变 `status.code`。
- 不改变 A/B/C 边界。
- 不修改后端已经计算出的数值。
- 不把 B/C 包装成 A 类可答结果。

## 四、LLM 能做什么

当配置可用时，LLM 只允许做：

- 优化主回答文案。
- 提炼关键结论。
- 根据后端 rows 选择表格、指标卡、折线图、柱状图或组合展示。
- 生成更自然的 B 类追问表达。
- 生成更业务化的 C 类拒答解释和可改问方向。
- 生成口径提醒和注意事项表达。

## 五、LLM 不能做什么

LLM 不允许：

- 查数。
- 生成 SQL。
- 修改后端数值。
- 新增不存在的数据点。
- 新增不存在的月份、客户、区域、承运商、运输方式。
- 改写 planner、query_key、status 或 A/B/C 边界。
- 把澄清态改成成功态。
- 把不支持态改成成功态。

## 六、后端结构化输出

新增 `presentation` 字段，结构包含：

- `display_type`：展示类型。
- `title`：业务标题。
- `answer`：主回答。
- `highlights`：关键结论。
- `chart_spec`：图表配置。
- `table_spec`：表格配置。
- `cards`：指标卡。
- `follow_up`：B 类追问。
- `unsupported_explanation`：C 类拒答解释。
- `caveats`：数据范围和口径提醒。
- `debug`：降级原因、模型名、query_key 等折叠调试信息。

支持的 `display_type`：

- `narrative`
- `summary_cards`
- `table`
- `line_chart`
- `bar_chart`
- `mixed`
- `clarification`
- `unsupported`
- `empty_result`
- `error`

## 七、前端渲染说明

物流 data-qa 页面已按 `presentation` 动态渲染：

- `narrative`：自然语言回答。
- `summary_cards`：指标卡。
- `table`：表格。
- `line_chart`：轻量 SVG 折线图。
- `bar_chart`：轻量 SVG 柱状图。
- `mixed`：结论、指标卡、图表和表格组合。
- `clarification`：业务化追问和补充示例。
- `unsupported`：拒答原因和可改问方向。
- `empty_result`：空结果解释。
- `error`：友好错误提示。

前端仍兼容旧接口：没有 `presentation` 时，继续使用 `answer_summary`、`result_table`、`clarification_questions` 和 `query_plan.unsupported_reason` 展示。

## 八、图表展示说明

图表数据只来自后端 `result_table.rows`。

用户要求“折线图”“趋势图”“看趋势”时，如果 rows 至少两行且存在可用数值字段，输出 `line_chart`。

用户要求“柱状图”“柱形图”“条形图”时，如果 rows 支持，输出 `bar_chart`。

如果 rows 不支持图表，系统自动降级为表格或自然回答，不画假图。

## 九、降级策略

以下情况会自动降级到确定性展示：

- 表达层开关关闭。
- LLM 配置缺失。
- LLM 调用失败。
- LLM 返回非 JSON。
- LLM 返回空 payload。
- LLM 改写 status。
- LLM 把 B/C 跨界成 success。
- LLM 修改或新增数值。
- LLM 输出的表格、图表、指标卡数据不来自后端 rows。

表达层降级不会导致 data-qa 主链路失败。

## 十、防幻觉校验

后端已实现以下校验：

- `status_code` 必须和后端原状态一致。
- `display_type` 必须符合当前状态边界。
- 主文案、标题、关键结论中的数字必须来自后端结果。
- 表格 columns / rows 必须来自后端表格。
- 图表 x/y 数据必须来自后端 rows。
- 指标卡数值必须来自后端 rows。
- 校验失败时写入 `debug.fallback_reason`，并采用确定性 fallback。

补充安全策略：

- 年份、月份、日期等筛选条件数字允许出现在主文案中，例如 `2026年1月到3月`。
- 指标数值仍必须来自 `result_table.rows`、`answer_summary` 或已锁定计算口径。
- `chart_spec.x_axis`、`chart_spec.y_axis` 和 `series.field` 必须使用后端原始字段名，例如 `biz_month`、`shipment_mw`，不能改成“月份”“发运量”等中文字段。
- 如果用户明确要求折线图 / 柱状图 / 表格，但 LLM 输出忽略该展示要求，表达层会降级到确定性展示编排。

## 十一、配置项

新增配置：

- `LLM_ANSWER_PRESENTATION_ENABLED`
- `LLM_ANSWER_PRESENTATION_MODEL`
- `LLM_ANSWER_PRESENTATION_TIMEOUT`
- `LLM_ANSWER_PRESENTATION_MAX_RETRIES`

配置复核结论：

- `backend/app/core/config.py` 已存在通用 `LLM_BASE_URL / LLM_API_KEY / LLM_MODEL`。
- `llm_understanding_service.py` 使用通用 LLM 配置。
- 答案表达层上一版只读取 `LLM_ANSWER_PRESENTATION_MODEL`，因此即使通用 `LLM_MODEL` 已存在，也会判定 `live_llm_configured=false`。
- 本轮已修正为专用模型优先、通用模型兜底，避免“项目已有 LLM 配置但表达层不调用”的问题。

配置策略：

- 表达层 live LLM 只有在 `LLM_ANSWER_PRESENTATION_ENABLED=true` 时才允许调用。
- 模型名优先使用专用 `LLM_ANSWER_PRESENTATION_MODEL`。
- 如果专用模型未配置，但通用 `LLM_MODEL` 已配置，则表达层允许兜底使用 `LLM_MODEL`。
- `base_url` 和 `api_key` 统一使用通用 `LLM_BASE_URL` / `LLM_API_KEY`。
- `LLM_API_KEY` 只能来自环境变量或 `.env`，不允许写入代码、文档或报告。
- 如果缺少 `LLM_BASE_URL`、`LLM_API_KEY` 或可用模型名，则不真实调用 LLM，自动降级到确定性展示编排。

本地 OpenAI 兼容 LLM 配置示例：

```bash
export LLM_BASE_URL="<your_openai_compatible_base_url>"
export LLM_API_KEY=""  # 填入实际供应商 API Key；不要提交真实密钥
export LLM_MODEL="deepseek-v4-flash"
export LLM_ANSWER_PRESENTATION_ENABLED="true"
export LLM_ANSWER_PRESENTATION_MODEL="deepseek-v4-flash"
export LLM_ANSWER_PRESENTATION_TIMEOUT="30"
export LLM_ANSWER_PRESENTATION_MAX_RETRIES="1"

python scripts/logistics_answer_presentation_live_shadow_eval.py
```

如果不单独设置 `LLM_ANSWER_PRESENTATION_MODEL`，但 `LLM_MODEL=deepseek-v4-flash` 已配置，表达层会在启用状态下使用通用模型兜底。

## 十二、live shadow 验收

已新增并执行：

- `scripts/logistics_answer_presentation_live_shadow_eval.py`
- `docs/LOGISTICS_ANSWER_PRESENTATION_LIVE_SHADOW_EVAL.md`
- `docs/LOGISTICS_ANSWER_PRESENTATION_LIVE_LLM_ACCEPTANCE.md`
- `tmp/logistics_question_bank/logistics_answer_presentation_live_shadow_eval_report.json`
- `tmp/logistics_question_bank/logistics_answer_presentation_live_llm_acceptance_report.json`

验收方法：

- 未配置 live LLM 时，脚本仍执行 deterministic fallback 与安全边界验收。
- 配置 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_ANSWER_PRESENTATION_ENABLED=true` 和专用或通用模型后，脚本执行 live LLM shadow 验收。
- 报告输出 `base_url` 和 `model`，不输出 API Key。
- 代表样例 `请将 2026 年 1 月到三月，这三个月的运量综合用折线图统计出来` 必须通过：确定性链路返回 `sys_mw_and_trip_count`、`2026-01/02/03` 三个月 rows，表达层输出 `line_chart` 或 `mixed`，图表数据来自后端 rows。

当前最新验收结果以以下报告为准：

- `docs/LOGISTICS_ANSWER_PRESENTATION_LIVE_LLM_ACCEPTANCE.md`
- `tmp/logistics_question_bank/logistics_answer_presentation_live_llm_acceptance_report.json`

最新结果摘要：

- live LLM 配置：已具备 `LLM_BASE_URL / LLM_API_KEY / LLM_MODEL`。
- 模型来源：优先 `LLM_ANSWER_PRESENTATION_MODEL`，未单独设置时兜底 `LLM_MODEL`；具体模型值以运行时报告为准。
- 是否真实发起 live 调用：以最新验收报告为准。
- live LLM 成功编排数以 `LOGISTICS_ANSWER_PRESENTATION_LIVE_LLM_ACCEPTANCE.md` 最新报告为准。
- deterministic fallback 与安全降级仍保持可用。
- 代表折线图样例仍通过：后端返回 2026 年 1–3 月 rows，前端可按确定性 `line_chart` 渲染。

## 十三、真实业务链路端到端验收

已新增并执行：

- `scripts/logistics_data_qa_real_e2e_acceptance.py`
- `docs/LOGISTICS_DATA_QA_REAL_E2E_ACCEPTANCE.md`
- `tmp/logistics_question_bank/logistics_data_qa_real_e2e_acceptance_report.json`

验收边界：

- 不是 demo，不新建独立演示页。
- 不使用 mock 数据，不 hardcode 样例结果。
- 调用真实 `LogisticsDataQaService.query()`，经过 planner / repository / data_qa_service 主链路。
- `deepseek-v4-flash` 只在确定性结果之后做表达优化和展示编排。
- LLM 不查数、不生成 SQL、不改写 planner / query_key / A/B/C 边界、不修改后端数值。
- 前端真实页面使用 `response.presentation` 动态渲染，同时保留旧响应无 `presentation` 时的降级展示。

最新端到端结果：

- 样例总数：`13`
- 通过：`13`
- 失败：`0`
- 真实 data-qa 主链路样例：`11`
- 前端静态兼容检查：`2`
- 是否真实调用 LLM：以最新验收报告为准
- 模型来源：`LLM_MODEL`
- fallback 数：`4`，原因均为 `llm_text_number_hallucination`，已安全降级到确定性展示。
- 代表样例“请将 2026 年 1 月到三月，这三个月的运量综合用折线图统计出来”通过：真实 planner 命中 `sys_mw_and_trip_count`，真实 repository 返回 2026 年 1–3 月 rows，前端可按 `line_chart` 渲染。
- 当前正式分布仍为 `A=656 / B=178 / C=69 / D=0`。

## 十四、已执行测试

已新增并执行：

- `scripts/logistics_answer_presentation_layer_regression.py`

覆盖 `14/14`：

- A 类成功答案表达优化。
- B 类追问表达优化。
- C 类拒答解释表达优化。
- 空结果表达优化。
- 用户要求折线图。
- 用户要求表格。
- 用户要求汇总。
- LLM 失败降级。
- LLM JSON 解析失败降级。
- LLM 越权改状态时降级。
- LLM 修改数值时降级。
- 年/月筛选数字不误判为指标幻觉。
- 用户明确要求图表但 LLM 忽略展示类型时降级。
- LLM 使用中文图表字段时降级。

已执行前端构建：

- `npm run build --prefix frontend`

## 十五、已知限制

- 当前没有强依赖 live LLM；无配置时会走 deterministic fallback。
- 图表当前使用轻量 SVG，适合演示和试运行，不做复杂交互。
- 表达层只优化展示，不解决 B 类业务口径缺口和 C 类能力边界。
- 技术详情仍保留在折叠区，默认不作为业务主展示。
