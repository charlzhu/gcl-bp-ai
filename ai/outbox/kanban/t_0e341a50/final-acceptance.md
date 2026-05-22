# LQG-5 最终验收报告

## 任务概要

**任务**: LQG-5：物流 execute_node 接入现有 LogisticsDataQaService
**分支**: feature/qa-langgraph-unified-runtime
**工作区**: /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai-langgraph-01

## 实现内容

### 新增文件
1. `backend/app/domains/business_qa_graph/nodes/execute_node.py` — 领域服务执行节点
2. `tests/unit/business_qa_graph/test_lqg5_execute_node.py` — 10 个 focused 测试

### 修改文件
1. `backend/app/domains/business_qa_graph/builder.py` — 新增 execute 节点和路由
2. `backend/app/domains/business_qa_graph/schemas/state.py` — 新增 EXECUTED 状态、execution_result 字段
3. `backend/app/domains/business_qa_graph/schemas/response.py` — 新增 EXECUTED 状态、execution_result 透传
4. `backend/app/domains/business_qa_graph/nodes/__init__.py` — 导出 execute_node
5. `tests/unit/business_qa_graph/test_business_qa_graph_skeleton.py` — 更新 trace 节点列表断言

## 验收结果

### 测试结果
- **LQG-5 focused tests**: 10/10 PASSED
- **全部 business_qa_graph 测试**: 61/61 PASSED（含 LQG-1/2/3/4 回归）
- **物流 E2E**: 34/34 PASSED（无回归）

### 静态扫描
- 无硬编码密钥
- 无 shell 注入
- 无 eval/exec
- 编译通过

### 独立 Review
- **结果**: PASSED
- **安全问题**: 0
- **逻辑错误**: 0
- **建议**: 1（DB session 管理，非阻塞，已记录）

### 验收标准验证
| 标准 | 状态 | 说明 |
|------|------|------|
| 物流问题经 Graph 返回一致结果 | PASS | execute_node 调用 LogisticsDataQaService.query，与旧链路走同一服务 |
| 非物流域不触发执行 | PASS | domain != "logistics" 时跳过，写入 execution_skipped trace |
| 显式承运商无数据不放宽 | PASS | 结果由 LogisticsDataQaService 保证，execute_node 不透传/修改 |
| 多年份不静默省略空年份 | PASS | 同上 |
| 旧 /logistics/data-qa/query 和 /stream 保持可用 | PASS | 未修改物流 API 端点代码 |
| 是否走 graph 由配置控制 | PASS | business_qa_langgraph_enabled 控制 graph 启用 |
| 不直接 SQL、不绕过 service/repository | PASS | execute_node 通过 LogisticsDataQaService.query 执行 |
| 用户可见回答不泄露技术细节 | PASS | _sanitize_result 剔除 SQL/表名/字段名/query_key/raw/debug |
| 新增代码有中文注释 | PASS | 所有函数和关键逻辑均有中文注释 |

### 已知限制
1. **DB session 管理**: `_default_logistics_service()` fallback 路径创建的 DB session 未显式关闭。生产环境应通过 builder 参数注入 service 实例。
2. **仅物流域**: execute_node 当前仅支持 logistics 域。plan_bom 域执行留待 LQG-6 或后续卡。

### 影响范围
- 不改变物流 API 端点或 LogisticsDataQaService 接口
- 不改变物流/计划 BOM/功率预测既有能力
- graph 默认关闭（business_qa_langgraph_enabled=False），不影响旧链路

### 提交材料
- `tmp/hermes/diff_lqg5.patch` — 完整 diff（2248 行）
- `tmp/hermes/test_lqg5.log` — 测试日志（61 passed）
- 本文件 — 验收报告
