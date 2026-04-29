# 物流答案表达层 live shadow 验收报告

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
