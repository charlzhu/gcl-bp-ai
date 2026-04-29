# 物流 data-qa 前后端联调闭环检查

生成时间：2026-04-27T09:00:05

## 一、检查结论

- 检查项：`9`
- 通过：`9`
- 失败：`0`
- 是否存在阻断问题：`False`

## 二、检查明细

| 场景 | 是否通过 | 证据 |
| --- | --- | --- |
| 成功态 | True | 成功态展示 answer_summary、结果表格、数据范围和 query_plan。 |
| 追问态 | True | 追问态展示后端 clarification_questions，不在前端硬编码追问。 |
| 拒答态 | True | 拒答态展示 unsupported_reason/status.message/answer_summary 和可改问方向。 |
| 空结果态 | True | OK 但 rows 为空时展示空结果说明。 |
| 错误态 | True | 接口异常写入消息流并展示友好提示，不暴露堆栈。 |
| 加载态 | True | 请求过程中展示 loading 气泡。 |
| 边界输入态 | True | 空输入会提示补充问题，输入框限制 200 字并保留换行说明。 |
| 接口契约 | True | 前端 API 类型保留 status、query_plan 和 unsupported_reason。 |
| 底部输入固定与对话滚动 | True | 对话区滚动、输入区在页面底部随主容器固定。 |
