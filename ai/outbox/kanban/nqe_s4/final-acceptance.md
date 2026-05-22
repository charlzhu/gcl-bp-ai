# NQE-S4 验收报告：物流 NL2SQL assist 灰度接入 Graph

## 状态：PASS — 可交付

## 修改文件清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `backend/app/core/config.py` | 修改 | 新增 `logistics_nl2sql_assist_via_graph: bool = False` |
| `backend/app/domains/business_qa_graph/nodes/question_understanding_node.py` | 修改 | 新增 `assist_mode` 参数，assist 模式下 NL2SQL shadow 路径设 PLANNED 而非 UNSUPPORTED |
| `backend/app/domains/business_qa_graph/builder.py` | 修改 | 传递 `assist_mode` 到 `question_understanding_node` |
| `backend/app/domains/business_qa_graph/runner.py` | 修改 | 读取 `logistics_nl2sql_assist_via_graph` 配置并传递到 graph |
| `backend/app/domains/logistics/api/endpoints/data_qa.py` | 修改 | 新增 `_maybe_run_assist_graph()` 函数，assist 模式下同步运行 Graph 编排 |
| `tests/unit/business_qa_graph/test_nqe_s4_assist_graph.py` | 新增 | 16 个 focused tests |

## 关键改动说明

1. **Config 灰度开关**：`logistics_nl2sql_assist_via_graph: bool = False`，默认关闭，旧接口行为完全不变
2. **question_understanding_node assist 模式**：新增 `assist_mode` 参数，当 True 且 capabilities 包含 `logistics_nl2sql_shadow` 时，设置 `understanding_status=PLANNED`（而非 UNSUPPORTED），同时通过正常物流 adapter 填充 `shadow_plan_raw`，使后续 `plan_validate → plan_build → execute` 节点正常流转
3. **端点集成**：新增 `_maybe_run_assist_graph()` 函数，在物流问答的两个端点（`/query` 和 `/query/stream`）中作为 best-effort 副效应运行 Graph 编排，Graph 异常不中断主链路
4. **Graph runner**：`BusinessQaGraphRunner` 支持从 `settings.logistics_nl2sql_assist_via_graph` 读取 assist 模式配置

## 测试结果

| 测试集 | 通过 | 失败 | 跳过 | 说明 |
|--------|------|------|------|------|
| NQE-S4 focused | 15 | 0 | 1 | assist 模式全路径覆盖 |
| NQE-S1 回归 | 12 | 0 | 0 | NL2SQL shadow 行为不变 |
| NQE-S2 回归 | 15 | 0 | 0 | 复合分解行为不变 |
| NQE-S3 回归 | 19 | 0 | 0 | shadow compare 行为不变 |
| **合计** | **61** | **0** | **1** | |

全量 business_qa_graph: 156 passed, 8 pre-existing failures (worktree config issue), 0 new regressions.

## 独立 Review

- **passed**: true
- **security_concerns**: []（无安全问题）
- **logic_errors**: []（无逻辑错误）
- **suggestions**: 3 条非阻塞建议（同步执行延迟、测试 mask 已知问题、mode 字段未消费）

## 验证清单

- [x] 默认关闭时旧接口行为完全不变（`logistics_nl2sql_assist_via_graph=False`）
- [x] assist 模式下 Graph 编排正常流转（PLANNED → plan_validate → plan_build → execute）
- [x] execute_node 仍调用 LogisticsDataQaService.query（旧服务不变）
- [x] Graph 异常 fail-closed，不中断主链路
- [x] 所有 focused tests + 相邻回归通过
- [x] compile/import check 通过
- [x] 独立 code review 通过
- [x] diff.patch、test.log 已生成

## 风险点

1. `_maybe_run_assist_graph()` 在主链路中同步运行 Graph，可能增加响应延迟（毫秒级）；建议后续改为异步/后台执行
2. 当前 Graph 内部 `question_understanding_node` 的 adapter 默认构造依赖 `LogisticsQueryPlannerV2`，在 worktree 中可能因缺少 `logistics_query_planner_v2_enabled` 配置字段失败；此问题与 NQE-S4 无关，是 worktree 环境隔离导致的已知问题
3. `business_qa_graph_mode` Literal 字段（已存在）与新增的 `logistics_nl2sql_assist_via_graph` bool 是独立开关，操作者需确认所需模式

## 是否影响现有能力

- 物流问答：不影响（assist 默认关闭，Graph 作为 best-effort 副效应运行）
- 计划 BOM：不影响
- 功率预测：不影响
- 前端：不影响

## 阶段边界

- [x] 遵守本轮 NQE-S4 边界：只做 assist 灰度开关和端点集成
- [x] 未自动 commit/push/deploy
- [x] 未进入 NQE-S5 或后续阶段
