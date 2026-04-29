# 物流答案表达层 live LLM 验收报告

## 结论
- live LLM 是否配置：True
- 是否真实调用 live LLM：True
- base_url：https://dashscope.aliyuncs.com/compatible-mode/v1
- model：qwen-plus
- model 来源：LLM_MODEL
- API Key：已脱敏，报告不输出密钥。
- 样例总数：33
- 通过：33
- 失败：0
- fallback 数量：14
- 前端静态展示检查：通过
- live LLM 表达效果是否通过：是
- deterministic fallback 展示是否可用于试运行：是

## 代表性折线图样例
- 问题：请将 2026 年 1 月到三月，这三个月的运量综合用折线图统计出来
- 状态：OK
- query_key：sys_mw_and_trip_count
- 展示类型：line_chart
- 图表类型：line
- 是否通过：True
- 失败项：[]

## fallback 原因分布
```json
{
  "llm_text_number_hallucination": 7,
  "none": 19,
  "llm_status_changed": 1,
  "llm_error:provider_error": 2,
  "llm_chart_data_not_from_backend": 1,
  "llm_display_type_ignores_user_request": 1,
  "llm_not_configured": 2
}
```

## display_type 分布
```json
{
  "line_chart": 9,
  "summary_cards": 5,
  "table": 2,
  "bar_chart": 2,
  "mixed": 2,
  "clarification": 6,
  "unsupported": 5,
  "empty_result": 1,
  "error": 1
}
```

## 安全拦截
- 状态越权拦截：1
- 数值幻觉拦截：7
- 图表字段/数据非法拦截：1

## 说明
- 本轮仅验证答案表达层 shadow 展示效果，不改变 planner、query_key、repository、A/B/C 边界或 903 总账。
- 专用模型配置优先使用 `LLM_ANSWER_PRESENTATION_MODEL`；未配置时，在表达层启用且通用 `LLM_MODEL` 存在时兜底使用通用模型。
- 未配置 live LLM 或 provider 调用失败时，脚本仍执行 deterministic fallback 与安全边界验收，并输出可复跑报告。

## 真实业务链路补充验收

已补充执行 `scripts/logistics_data_qa_real_e2e_acceptance.py`：

- 不是 demo，不使用 mock 数据，不新建独立演示页。
- 调用真实 `LogisticsDataQaService.query()`，经过 planner / repository / data_qa_service 主链路。
- qwen-plus 已真实调用，模型来源为 `LLM_MODEL` fallback。
- 样例总数 `13`，通过 `13`，失败 `0`。
- 覆盖 A 类直接回答、自然总结、表格、折线图、柱状图、mixed 展示，B 类追问和补槽建议，C 类拒答解释，空/零结果解释，错误态和旧响应无 `presentation` 的前端兼容检查。
- 代表样例“请将 2026 年 1 月到三月，这三个月的运量综合用折线图统计出来”通过：后端真实返回 2026 年 1–3 月 rows，前端可按 `line_chart` 渲染。该样例的 live LLM 文本触发数值安全拦截，系统按设计降级到确定性展示，未使用 LLM 编造图表数据。
- 当前正式分布仍为 `A=656 / B=178 / C=69 / D=0`。
