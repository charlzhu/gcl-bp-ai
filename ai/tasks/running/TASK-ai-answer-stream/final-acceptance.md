# TASK-ai-answer-stream 最终验收报告

## 1. 任务目标

用户要求优化智能问答链路：后端返回给前端的内容先经过大模型表达处理，并把用户原始提问也发给大模型；前端以流式方式展示更准确、更生动、更有 AI 感的答案，同时保留确定性业务结果和结构化表格。

## 2. 实现结论

已完成。

本轮实现遵循以下边界：

1. BOM / 物流 / 功率等业务事实仍由后端确定性服务查询和计算。
2. LLM 只处理答案表达，不改写订单、供应商、金额、数量、比例、规格、功率、表格行等确定性事实。
3. 后端流式接口会把“用户原问题 + 确定性结果快照”送入 LLM。
4. LLM 未配置、调用失败或空流时自动降级为确定性答案，并仍按 NDJSON 流式协议返回。
5. 前端使用 fetch + ReadableStream 增量消费 delta 事件，done 事件到达后渲染完整结构化 payload。

## 3. 本轮修改文件

### 后端

- `backend/app/services/business_answer_stream_service.py`
  - 新增统一业务答案流式表达服务。
  - 支持 OpenAI 兼容 LLM 流式输出。
  - 支持未配置 / 异常 / 空流降级。
  - 仅覆盖 `presentation.answer`，保留结构化结果。

- `backend/app/domains/logistics/api/endpoints/data_qa.py`
  - 新增 `POST /api/v1/logistics/data-qa/query/stream`。
  - 先执行原物流确定性 QA，再输出 `meta / delta / done / error` NDJSON 事件。

- `backend/app/domains/plan_bom/api/endpoints/qa.py`
  - 新增 `POST /api/v1/plan-bom/qa/ask/stream`。
  - 先执行原计划 BOM QA，再流式输出 LLM 表达或确定性降级答案。

- `backend/app/domains/logistics/services/data_qa_planner.py`
  - 为通过全量验收，补充 TopN 解析对“前五集中在哪里 / 前五在哪 / 前五哪里”的通用识别。

### 前端

- `frontend/src/utils/http.ts`
  - 新增 `buildApiUrl`，让 fetch 流式接口复用现有 API base URL 规则。

- `frontend/src/utils/streamingApi.ts`
  - 新增 NDJSON 流式消费工具。
  - 支持跨 chunk 缓冲、`meta / delta / done / error` 分发。

- `frontend/src/api/logistics.ts`
  - 新增 `streamLogisticsDataQaQuery`。

- `frontend/src/api/planBom.ts`
  - 新增 `streamPlanBomQuestion`。

- `frontend/src/views/business-chat/BusinessChatPage.vue`
  - 改为按业务域调用后端 stream endpoint。
  - delta 到达时增量更新助手消息。
  - done 到达时用完整结构化 payload 完成消息。
  - loading 文案优化为“AI 正在生成回答”。
  - 修复细节：只有助手 streaming 状态显示打字光标，用户消息和最终答案不残留光标样式。

### 测试

- `tests/business_acceptance/test_ai_streaming_answer.py`
  - 新增流式服务和 endpoint 契约测试。
  - 覆盖：用户问题进入 prompt、确定性结果进入 prompt、未配置 LLM 降级、NDJSON 格式、两个 stream endpoint 事件顺序和结构化 payload 保持。

- `tests/business_acceptance/test_plan_power_frontend_upload_entry.py`
  - 新增前端静态验收：业务聊天页必须使用后端 LLM 流式答案管道。

## 4. 验证结果

### Focused tests

```bash
PYTHONPATH=. python -m pytest tests/business_acceptance/test_ai_streaming_answer.py tests/business_acceptance/test_plan_power_frontend_upload_entry.py::test_business_chat_uses_backend_llm_streaming_answer_pipeline tests/business_acceptance/test_business_chat_session_lifecycle.py tests/business_acceptance/test_plan_power_m5_qa_integration.py -q
```

结果：

```text
16 passed in 4.98s
```

### Endpoint stream contract tests

```bash
PYTHONPATH=. python -m pytest tests/business_acceptance/test_ai_streaming_answer.py -q
```

结果：

```text
5 passed in 1.17s
```

### Python compile

```bash
python -m py_compile backend/app/services/business_answer_stream_service.py backend/app/domains/logistics/api/endpoints/data_qa.py backend/app/domains/plan_bom/api/endpoints/qa.py backend/app/domains/logistics/services/data_qa_planner.py
```

结果：通过。

### Frontend build

```bash
npm run build
```

结果：通过。仅有既有 Vite chunk-size warning。

### Full business acceptance

```bash
set -o pipefail; PYTHONPATH=. python -m pytest tests/business_acceptance -q
```

结果：

```text
159 passed, 2 warnings in 31.14s
```

warning 为既有 openpyxl 读取 xlsm 扩展 / 条件格式提示。

### 静态检查

```bash
git diff --check -- <focused files>
```

结果：通过。

### 安全扫描

focused added-line security scan：通过。

结论：未发现生产代码新增硬编码密钥；未恢复废弃的功率模型临时 admin token / `X-Plan-Power-Admin-Token` / `adminToken` 等机制。

### 浏览器验证

路由：

```text
/smart-chat?verify=ai-stream-final
```

方法：浏览器 mock fetch 返回 NDJSON `meta / delta / done` 事件。

结果：

- 前端调用 `/api/v1/plan-bom/qa/ask/stream`。
- 请求体包含用户问题。
- 流式答案最终展示在助手结果中。
- done payload 的结构化表格正常渲染。
- 无横向溢出。
- 用户消息不带 streaming 光标样式。
- 助手最终答案不残留 streaming 光标样式。
- console messages / JS errors：0。

## 5. Reviewer 结果

快速独立 reviewer：PASS。

Blocking issues：none。

Non-blocking suggestion：后续可为 `postJsonLineStream` 增加 `AbortSignal` / 取消能力，避免用户切换或关闭会话后长流继续占用连接。

## 6. 验收材料

- `ai/tasks/running/TASK-ai-answer-stream/diff.patch`
- `ai/tasks/running/TASK-ai-answer-stream/test.log`
- `ai/tasks/running/TASK-ai-answer-stream/final-acceptance.md`

## 7. 风险与后续建议

1. 当前流式请求没有 AbortSignal，非阻塞；建议后续在会话切换、页面卸载、用户停止生成时补取消能力。
2. LLM 输出只用于表达层，但真实线上启用后仍建议观察一段时间的 query log，确认业务员体感和降级比例。
3. 当前工作树包含多批历史未提交改动，本报告只声明本轮 AI 流式答案相关范围已验收通过。

## 8. 是否影响现有能力

- 现有同步 BOM / 物流 QA 接口保留。
- 新增 stream endpoint 不破坏原有 API。
- 结构化表格、状态、追问、口径提示仍由后端确定性结果驱动。
- 全量 business acceptance 通过，未发现现有 BOM / 物流能力回归。
