# 后端问答链路明细日志说明

## 目标

本轮在不改变物流问答和计划 BOM 问答业务边界的前提下，补充后端关键节点日志，便于查看用户问题从输入到返回的处理过程。

## 已接入范围

- 物流数据问答：`POST /api/v1/logistics/data-qa/query`
- 计划 BOM 问答：`POST /api/v1/plan-bom/qa/ask`

## 记录节点

通用节点如下：

- `input_received`：收到用户原始问题。
- `rule_plan_built`：物流规则 planner 生成受控查询计划。
- `nlu_completed`：BOM NLU Center 完成意图和槽位理解。
- `guardrail_checked`：物流 LLM 候选理解与 Guardrail 校验完成。
- `branch_selected`：进入 A 类确定性查询、B 类追问或 C 类拒答分支。
- `query_result_ready` / `qa_result_ready`：确定性查询结果或受控问答结果已生成。
- `presentation_ready`：答案表达层已生成展示内容。
- `history_snapshot_writing`：物流准备写入统一查询历史快照。
- `history_snapshot_written`：物流统一查询历史写入完成。

## 查看方式

### 1. 通过接口响应查看

两个问答接口响应的 `data.trace_events` 会返回本次请求的明细节点。

示例结构：

```json
{
  "seq": 1,
  "time": "2026-04-27T10:20:30.123",
  "domain": "plan_bom",
  "trace_id": "xxx",
  "stage": "input_received",
  "message": "收到计划 BOM 问答用户问题。",
  "payload": {
    "question": "订单00104的接线盒规格是什么？"
  }
}
```

### 2. 通过后端日志查看

后端日志会输出结构化记录：

```text
qa_trace_event={...}
```

可以按 `trace_id` 检索一次请求的完整链路。

### 3. 通过查询历史查看物流快照

物流问答仍复用现有 `sys_query_log` 查询历史。历史详情中的 `request_payload_json.query_result.trace_events` 会保存写历史前的节点快照，便于回放排查。

## 安全边界

- 日志只记录受控查询计划、槽位、结果摘要、行数、状态和展示类型。
- 不记录真实密钥、数据库连接串或 API Key。
- 日志 payload 自动截断，避免大表结果完整写入日志。
- LLM 仍只做候选理解和表达优化，不作为事实来源。
- 本次改动不改变物流和 BOM 的 A/B/C/D 分类规则。

## 主要代码位置

- `backend/app/services/qa_trace.py`
- `backend/app/domains/logistics/services/data_qa_service.py`
- `backend/app/domains/plan_bom/services/qa_service.py`
- `backend/app/domains/logistics/schemas/data_qa.py`
- `backend/app/domains/plan_bom/schemas/qa.py`
