# 物流域 B-长期澄清池 Round1

## 1. 本轮目标

本轮不是继续把 B 类题强推成 A，而是先把最适合“缺口径识别 + 业务化追问生成”的一批长期澄清题，纳入正式治理。

当前原则保持不变：

1. 规则层先判定是否必须澄清。
2. LLM 只能做两件事：
   - 识别当前问题缺少哪些关键口径；
   - 生成更业务化的追问候选。
3. LLM 不能改写最终边界，不能把 clarification 改成 success 或 unsupported。

## 2. Round1 选择范围

Round1 只覆盖当前 `B-长期澄清池` 里，规则层已经稳定识别且适合做 LLM 辅助的 7 个澄清题型：

1. `transport_record_scope`
2. `quarter_trip_metric_scope`
3. `route_loading_scope`
4. `rate_distribution_scope`
5. `system_status_ratio_scope`
6. `parse_status_scope`
7. `vague_status`

本轮共选中 `34` 条题，覆盖 `230` 条 B-长期澄清池中的第一批治理对象，剩余 `196` 条留待后续波次继续处理。

## 3. Round1 覆盖结果

### 3.1 题型分布

- `vague_status`: 9
- `quarter_trip_metric_scope`: 5
- `route_loading_scope`: 5
- `transport_record_scope`: 4
- `system_status_ratio_scope`: 4
- `parse_status_scope`: 4
- `rate_distribution_scope`: 3

### 3.2 题族分布

- 综合统计类：16
- 2026系统状态与数据质量类：8
- 线路/城市运价类：5
- 运输方式分析类：4
- 承运商经营与排名类：1

## 4. LLM 在本轮的实际作用

### 4.1 接入方式

本轮接入位置在：

- `question_bank_response_policy`
- `data_qa_planner`
- `data_qa_service`
- `llm_clarification_assist_service`

执行顺序是：

1. 规则层先稳定判定为 `clarification`
2. 规则层给出澄清类别、缺口径和规则模板
3. LLM 只对 allowlist 题型补充：
   - `missing_slots`
   - `suggested_questions`
   - `business_summary`
4. 最终结果仍保持 `clarification`

### 4.2 本轮 live 样本

本轮为了避免把外部模型调用变成新的阻塞，只对每个题型抽取代表样本做 live 验证，共 `7` 条：

- live sample：`7`
- 实际调用：`7`
- 采用增强结果：`7`
- 边界保持 clarification：`34/34`

### 4.3 结果判断

本轮 live 样本里，LLM 能稳定把规则模板进一步业务化：

- 运输方式记录数：把“记录数”展开成“明细行 / 任务单 / 车次”
- 季度车次/车辆数：把“车次 vs 去重车辆数”问得更业务化
- 装载托数：把“平均口径”和“空值处理”问得更清楚
- 达标率分布：把“达标率定义”和“统计颗粒度”问得更具体
- 系统状态占比：把“分母口径”和“有效任务范围”问得更清楚
- 解析状态：把“状态码含义”和“正式系统范围”问得更清楚
- 模糊异常：把“时间窗口 + 指标标准”转换成可执行追问

## 5. 本轮没有做的事

本轮没有：

1. 把这 34 条 B 题改判成 A
2. 扩新 query_key
3. 放开 LLM 去裁决 B/C
4. 进入 C-边界观察池治理

## 6. 当前结论

Round1 的正式结论是：

1. `B-长期澄清池` 已经可以开始按题型工厂化治理，不再只能依赖通用追问。
2. 规则层负责边界，LLM 负责“缺什么 + 怎么问”，这条分工当前是成立的。
3. 当前最适合继续推进的是：
   - 先按同样模式做 `B-长期澄清池 Round2`
   - 再决定是否进入 `C-边界观察池`

## 7. 关联产物

- 配置与代码：
  - `backend/app/domains/logistics/services/question_bank_response_policy.py`
  - `backend/app/domains/logistics/services/llm_clarification_assist_service.py`
  - `backend/app/domains/logistics/services/data_qa_service.py`
- 脚本：
  - `scripts/logistics_b_long_clarification_round1.py`
- 报告：
  - `tmp/logistics_question_bank/logistics_b_long_clarification_round1_report.json`
