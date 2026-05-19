# 产销存经营分析 M4 验收记录

## 1. 当前仓库能力判断

### 已完成能力

1. 产销存 M2/M3 基础能力已在当前 worktree 中存在：
   - 产销存 Excel 解析与事实导入测试可执行。
   - 产销存 QueryExecutor 已可基于中间库受控查询计划执行。
2. M4 后端问答入口已存在：
   - 经营分析 / 产销存 QA service 已接入。
   - 后端 API 路由已注册。
   - 流式问答链路可复用统一 BusinessAnswerStreamService。
3. M4 前端入口已存在：
   - BusinessChat domain 已包含 `business_analysis`。
   - 前端已有 `frontend/src/api/inventorySalesProduction.ts`。
   - BusinessChatPage 已按物流 / 经营分析产销存 / 计划 BOM 三路分发。

### 未完成或未覆盖能力

1. 当前验收只覆盖产销存 M4 focused 范围，不包含 SAP 物管任务。
2. 当前验收不推进物流 NL2SQL 后续阶段。
3. 当前验收未做真实浏览器 E2E 截图，只做前端静态契约测试与 production build。
4. 当前环境没有 `backend/.venv/bin/python`，测试使用 `/opt/anaconda3/bin/python` 执行。

## 2. 本次任务与当前仓库状态一致性

用户明确要求本任务线只处理产供销 / 产销存相关任务，不处理 SAP 物管和 NL2SQL。当前检查确认：

- 看板 `t_2c15aff8` 实际是 SAP MID Oracle 只读 smoke test，状态 blocked，和本轮产销存 M4 不同域，因此本轮未更新该看板。
- 当前 worktree 分支为 `hermes/hermes-1af52d1d`，工作区已保持干净。
- 当前产销存 M4 代码已存在并通过 focused 验证。

## 3. 本轮允许修改范围

本轮只允许处理：

1. 产销存 M4 前端入口与流式 API 验证。
2. 产销存 M2/M3/M4 focused 回归。
3. 前端 build、后端 compile、静态安全扫描。
4. 本地验收日志与验收说明。

## 4. 本轮禁止修改范围

1. 不处理 SAP 物管 / Oracle MID 任务。
2. 不推进物流 NL2SQL M9/M10。
3. 不修改 `.env`、密钥、连接串。
4. 不 push / deploy。
5. 不改动物流、计划 BOM 主链路行为。

## 5. 验证命令与结果

### 5.1 Focused 回归

命令：

```bash
/opt/anaconda3/bin/python -m pytest \
  tests/frontend/test_business_chat_business_analysis_domain.py \
  tests/business_acceptance/test_inventory_sales_production_m2_fact_import.py \
  tests/unit/business_analysis/test_inventory_sales_production_m3_query_executor.py \
  tests/unit/business_analysis/test_inventory_sales_production_m4_qa_service.py \
  tests/unit/business_analysis/test_inventory_sales_production_m4_api_registration.py \
  -q
```

结果：

```text
21 passed in 1.74s
```

日志：`ai/outbox/inventory_sales_production_m4/test.log`

### 5.2 后端编译

命令：

```bash
/opt/anaconda3/bin/python -m compileall -q \
  backend/app \
  tests/unit/business_analysis \
  tests/business_acceptance/test_inventory_sales_production_m2_fact_import.py
```

结果：通过，无编译错误。

日志：`ai/outbox/inventory_sales_production_m4/compile.log`

### 5.3 前端 build

命令：

```bash
cd frontend
npm run build
```

结果：通过。

说明：Vite 输出存在 chunk size warning，属于当前前端构建体积提示，不阻塞本轮产销存 M4 验收。

日志：`ai/outbox/inventory_sales_production_m4/frontend-build.log`

### 5.4 静态扫描

命令：

```bash
/opt/anaconda3/bin/python tmp/hermes/inventory_sales_production_static_scan.py
```

结果：

```text
status=PASS
no hardcoded secret patterns or obvious visible technical-leak strings found in scoped files
```

日志：`ai/outbox/inventory_sales_production_m4/static-scan.log`

## 6. 风险点

1. `backend/.venv/bin/python` 在当前 worktree 不存在，后续若 CI 或人工验收要求固定使用该解释器，需要先恢复 backend venv 或更新验收命令。
2. 前端 build 通过但有 Vite 大 chunk 提示，当前不影响功能；后续如做体验优化可单独拆包。
3. 本轮未做真实浏览器 E2E 截图；如果用户需要最终网页验收，应另起一次浏览器联调验证。
4. 产销存问答仍是受控 QueryPlan 桥接，不是完整 NL2SQL，自然语言覆盖范围需按后续样例继续扩展。

## 7. 是否影响既有能力

1. 物流问答：本轮未修改物流主链路，前端三路分发保留物流独立分支。
2. 计划 BOM：本轮未修改计划 BOM 主链路，前端三路分发保留 BOM 独立分支。
3. 功率预测：本轮未涉及功率预测。
4. SAP 物管：本轮未处理 SAP 物管。
5. NL2SQL：本轮未推进 NL2SQL。

## 8. 当前结论

产销存经营分析 M4-4 已完成：

- 前端 business_analysis domain 已可用。
- 产销存流式 API 封装存在。
- BusinessChatPage 已按物流 / 产销存 / BOM 三路分发。
- 产销存 M2/M3/M4 focused 回归通过。
- 前端 build 通过。
- 后端编译通过。
- 静态扫描通过。

当前 worktree 已保持干净；本轮未自动 push、未 deploy。
