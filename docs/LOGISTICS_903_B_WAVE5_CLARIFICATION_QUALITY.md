# 903 剩余 B Wave5 追问质量复检

生成时间：2026-04-26T21:24:20

## 一、追问质量统计

- B 题总数：`178`
- 可接受业务化追问：`124`
- 需要优化追问：`0`
- 需业务/数据确认后再追问：`54`
- 缺失槽位分布：`{'metric_definition': 79, 'time_range': 173, 'business_definition': 32, 'business_owner_confirmation': 29, 'evaluation_standard': 32, 'comparison_baseline': 7, 'transport_scope': 17, 'data_owner_confirmation': 25, 'data_scope': 22, 'ranking_metric': 3, 'sort_order': 3, 'top_n': 3}`

## 二、追问生成原则

- 追问基于缺失槽位和业务口径生成，不按题号 exact match。
- 对缺数据或缺业务定义的题，优先给业务确认问题，而不是伪装成可答。
- LLM 后续只能改写追问表达，不能改变最终 B/C 裁决。

