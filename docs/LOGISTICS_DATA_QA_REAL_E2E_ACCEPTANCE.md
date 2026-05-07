# 物流 data-qa 真实业务链路端到端验收报告

## 验收结论
- 是否调用真实 data-qa 主链路：True
- 是否使用 mock 数据：False
- 是否新建 demo 页面：False
- 是否真实调用 qwen-plus：True
- 模型来源：LLM_MODEL
- 使用模型：qwen-plus
- API Key：只来自环境变量，报告不输出密钥。
- 样例总数：14
- 通过：14
- 失败：0
- fallback 数：12
- 前端真实页面展示检查：通过
- 当前是否可进入真实业务试运行：是

## qwen-plus 配置
- base_url：https://dashscope.aliyuncs.com/compatible-mode/v1
- model：qwen-plus
- model 来源：LLM_MODEL
- live LLM 是否配置：True
- `LLM_ANSWER_PRESENTATION_MODEL` 优先；未配置时在表达层启用状态下 fallback 到 `LLM_MODEL`。
- `qwen3-plus` 当前环境不可用，不作为默认 live 验收模型。

## 代表性折线图样例
- 问题：请将 2026 年 1 月到三月，这三个月的运量综合用折线图统计出来
- 状态：OK
- query_key：sys_mw_and_trip_count
- filters：`{"year": 2026, "months": [1, 2, 3], "transport_mode": null, "base_code": null, "base_name": null, "monthly_breakdown": true}`
- rows：3
- 展示类型：line_chart
- 图表类型：line
- presentation 来源：deterministic
- fallback 原因：llm_error:provider_error
- 是否通过：True
- 失败项：[]

## 展示类型分布
```json
{
  "line_chart": 2,
  "summary_cards": 3,
  "table": 1,
  "bar_chart": 1,
  "pie_chart": 1,
  "mixed": 1,
  "clarification": 2,
  "unsupported": 1
}
```

## fallback 原因分布
```json
{
  "llm_error:provider_error": 12
}
```

## 安全校验
- 状态越权拦截数：0
- 数值幻觉拦截数：0
- 图表数据非法拦截数：0

## 业务链路边界
- 本报告调用真实 `LogisticsDataQaService.query()`，经过 planner / repository / data_qa_service 主链路。
- 表达层只在确定性结果之后生成 `presentation`，不查数、不生成 SQL、不改 query_key、不改 A/B/C 边界、不改后端数值。
- 没有新增独立 demo 页面，没有使用 mock 数据冒充真实链路。
- 当前正式分布保持 `A=656 / B=178 / C=69 / D=0`。
