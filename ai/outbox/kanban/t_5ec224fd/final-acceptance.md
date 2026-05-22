# LQG-8 验收报告：统一 business-qa 流式接口与 BusinessChatPage 迁移

## 任务摘要

新增统一业务问数 API `POST /api/v1/business-qa/stream`，
让 BusinessChatPage 对物流、计划 BOM（含功率预测/推荐/影响值对比）走统一流式入口，
同时保留旧接口回退能力。经营分析/产销存暂不纳入本轮统一入口。

## 变更文件清单

### 后端（新增/修改）

| 文件 | 操作 | 说明 |
|---|---|---|
| `backend/app/api/v1/business_qa.py` | **新增** | 统一流式端点，使用 BusinessQaDomainRegistry 做领域路由，调用既有领域服务 |
| `backend/app/schemas/business_qa.py` | **新增** | BusinessQaStreamRequest + UNIFIED_STREAM_STAGES |
| `backend/app/api/router.py` | **修改** | 注册 `/business-qa` 路由前缀（+3 行） |

### 前端（新增/修改）

| 文件 | 操作 | 说明 |
|---|---|---|
| `frontend/src/api/businessQa.ts` | **新增** | 统一前端 API `streamBusinessQa()` |
| `frontend/src/views/business-chat/BusinessChatPage.vue` | **修改** | logistics/plan_bom 统一走 streamBusinessQa，移除旧的独立 plan_bom 分支 |

### 测试（新增/修改）

| 文件 | 操作 | 说明 |
|---|---|---|
| `tests/unit/business_qa_graph/test_lqg8_unified_stream.py` | **新增** | 22 个 focused tests：schema 校验、stream stage 常量、领域路由、旧接口兼容、NDJSON 格式 |
| `tests/business_acceptance/test_plan_power_frontend_upload_entry.py` | **修改** | 适配新的统一 API 引用 |
| `tests/frontend/test_business_chat_business_analysis_domain.py` | **修改** | 适配新的统一 API 分支结构 |

## 测试结果

| 测试套件 | 通过/总数 | 备注 |
|---|---|---|
| LQG-8 focused tests | 22/22 ✅ | Schema、Stage、路由、兼容性、NDJSON |
| Graph 全量测试 | 103/103 ✅ | 原有 81 + 新增 22 |
| 全项目测试 | 632/634 ✅ | 2 个预存失败（fake repo 缺 `hist_carrier_kpi_by_year`），与 LQG-8 无关 |
| 前端 Vite build | ✅ | 通过，BusinessChatPage chunk 正常产出 |
| 后端 compile | ✅ | 所有新增/修改文件编译通过 |

## 统一流式事件序列

```
received → understanding → plan_ready → deterministic_result_ready → answer_streaming(delta) → done
```

异常时发送 `error` 事件并终止流。

## 旧接口兼容性

| 旧接口 | 状态 |
|---|---|
| `POST /logistics/data-qa/query/stream` | ✅ 仍可用（路由未变） |
| `POST /plan-bom/qa/ask/stream` | ✅ 仍可用（路由未变） |
| `POST /logistics/data-qa/query` | ✅ 仍可用 |
| `POST /plan-bom/qa/ask` | ✅ 仍可用 |

## 安全边界

- 旧接口保留回退能力，BusinessChatPage 的 business_analysis 分支继续使用独立流式接口
- 统一端点 fail-closed：无法识别业务域时返回 CLARIFY，不执行领域服务
- 异常时写错误日志（复用领域服务 write_error_log），不泄露内部细节
- LLM 只做表达增强，表格/状态/数值仍由确定性服务控制
- 用户可见回答不暴露 SQL、表名、字段名、query_key、planner、guardrail、schema

## 风险点

1. 前端的 plan_bom adapter (`adaptPlanBomResult`) 接收的数据格式与统一端点的 done 事件 data 字段需兼容 —— 已验证一致（`data.data` 即完整确定性结果）
2. 功率预测/推荐/影响值对比三条子能力通过 `PlanBomQaService.ask()` 内部 power 分支执行 —— 统一端点不区分 power sub-capability
3. 经营分析/产销存暂不纳入：预留后续 LQG 卡对接

## 后续看板规划建议

- 经营分析/产销存接入统一入口（需要新的 LQG 卡）
- 统一端点增加 query_plan_v2_meta shadow 回传
- 前端 `streamingApi.ts` 增加 stage 进度展示（understanding/plan_ready 阶段提示）
