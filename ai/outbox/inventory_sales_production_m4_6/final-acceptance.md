# 产销存经营分析 M4-6 验收记录

完成时间：2026-05-19 17:27:08 CST

## 1. 当前仓库已完成能力判断

1. 当前新 worktree：`/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/isp-m4-6-business-acceptance`。
2. 当前分支：`feature/isp-m4-6-business-acceptance`。
3. 当前基线：从 `c66ca93` 新建。
4. 产销存 M2/M3/M4 基础能力已存在：Excel 解析、事实导入、确定性查询执行、QA 服务、API 注册、前端 business_analysis domain 入口均已有测试覆盖。
5. M4-4 focused、M2/M3 回归、编译、静态扫描和前端 build 已有历史验收记录。

## 2. 当前未完成能力判断

1. M4-6 已固化真实业务问法回归样例，但仍不是完整经营分析、完整 NL2SQL 或完整多 Agent 能力。
2. 同比、环比、任意月份区间和库存周转率本轮按业务化 fail-closed/澄清处理；后续如业务确认口径，需要另开阶段扩展。
3. 本轮未做真实浏览器 E2E 截图；前端 production build 和前端单元入口测试已通过。

## 3. 本次任务与当前仓库状态一致性

用户明确要求启动：`M4-6：产销存业务验收与真实问法回归样例固化`。

当前仓库已具备产销存 M2/M3/M4 基础链路，适合进入 M4-6。本轮未处理 SAP 物管、物流 NL2SQL、计划 BOM 或功率预测专项。

## 4. 本轮允许修改范围

1. 产销存真实问法回归测试。
2. 产销存临时自然语言规划器中的问法归一和 fail-closed 边界。
3. 产销存 M4-6 验收样例文档。
4. outbox 验收日志、补丁、审查结果和验收说明。

## 5. 本轮禁止修改范围

1. 不处理 SAP Oracle MID / 物管任务。
2. 不推进物流 NL2SQL 后续阶段。
3. 不修改物流、计划 BOM、功率预测主链路。
4. 不修改 `.env`、真实密钥、连接串。
5. 不 push、deploy、merge、commit。

## 6. TDD 过程

### 6.1 RED

新增 M4-6 真实问法回归测试后，首次执行：

```text
5 failed, 10 passed in 0.58s
```

暴露缺口：

1. `2025年一季度销售量是多少？` 没识别中文季度，期间标签仍按年度。
2. `2026年截至4月累计销量是多少？` 被误识别为 4 月单月，而不是 1-4 月累计。
3. `2025年各版型产量排名` 没切到标准版型产量指标，返回空结果。
4. `2025年销量同比增长率是多少？` 被误答成普通销量。
5. `2025年销量环比趋势如何？` 被误答成普通趋势。

### 6.2 GREEN 与 reviewer 返修

首轮修复后新增 M4-6 focused：

```text
15 passed in 0.57s
```

独立 reviewer 发现阻断问题：累计截止月份识别过宽，会把 `2月至4月`、`4月至6月` 这类普通月份区间误规划成年初累计。

返修内容：

1. 将“截至/截止/前 N 个月/累计到 N 月”作为累计问法。
2. 对 `N 月至 M 月 / N 月到 M 月` 等任意月份区间业务化阻断，避免误答成年初累计。
3. 将用户可见文案里的阶段术语改成“当前版本”。
4. 补充 `截止4月` 正向样例。

返修后 M4-6 focused 已扩展为 19 条真实问法样例，组合回归为 40 条。

## 7. 最终验证结果

### 7.1 M4-6 + M2/M3/M4 组合回归

执行命令：

```bash
/opt/anaconda3/bin/python -m pytest \
  tests/business_acceptance/test_inventory_sales_production_m4_6_real_question_regression.py \
  tests/frontend/test_business_chat_business_analysis_domain.py \
  tests/business_acceptance/test_inventory_sales_production_m2_fact_import.py \
  tests/unit/business_analysis/test_inventory_sales_production_m3_query_executor.py \
  tests/unit/business_analysis/test_inventory_sales_production_m4_qa_service.py \
  tests/unit/business_analysis/test_inventory_sales_production_m4_api_registration.py \
  -q
```

最终结果：

```text
40 passed in 1.80s
```

### 7.2 后端编译

```bash
/opt/anaconda3/bin/python -m compileall -q \
  backend/app \
  tests/business_acceptance/test_inventory_sales_production_m4_6_real_question_regression.py \
  tests/unit/business_analysis \
  tests/business_acceptance/test_inventory_sales_production_m2_fact_import.py
```

结果：通过，无编译错误。

### 7.3 前端 build

首次在新 worktree 执行 `npm run build` 时失败：

```text
sh: vue-tsc: command not found
```

根因：新 worktree 缺少前端 `node_modules`，不是代码缺陷。

处理：

```bash
cd frontend
npm ci
npm run build
```

最终结果：通过，严格退出码 `frontend_build_exit_code=0`。

构建缓存 `frontend/tsconfig.tsbuildinfo` 已还原，不纳入本轮变更。

### 7.4 静态扫描

```bash
/opt/anaconda3/bin/python tmp/hermes/inventory_sales_production_m4_6_static_scan.py
```

结果：

```text
status=PASS
no hardcoded secret patterns found in inventory sales production M4-6 scoped files
```

### 7.5 独立 review

二次只读审查结果：通过。

审查结论：

1. `2月至4月/4月至6月` 不再误识别成年初累计。
2. `截至4月/截止4月/前4个月/累计到4月` 仍按累计处理。
3. 同比、环比和任意月份区间用户可见文案无内部技术术语。
4. 修改范围仍限于产销存 M4-6。
5. 未发现安全问题。

## 8. 修改文件清单

1. `backend/app/domains/business_analysis/services/inventory_sales_production/nl_query_planner.py`
   - 增加中文季度识别。
   - 增加截至/截止/前 N 个月/累计到 N 月的累计期间识别。
   - 增加任意月份区间的业务化 fail-closed。
   - 增加按版型产量问法的标准指标切换。
   - 增加同比/环比类问题 fail-closed，避免误答。
2. `tests/business_acceptance/test_inventory_sales_production_m4_6_real_question_regression.py`
   - 新增 19 条真实问法回归样例。
   - 覆盖 A 类可答样例与 B/C 类边界样例。
3. `docs/INVENTORY_SALES_PRODUCTION_M4_6_REAL_QUESTION_REGRESSION.md`
   - 固化 M4-6 业务验收问法清单、口径和验证入口。
4. `ai/outbox/inventory_sales_production_m4_6/`
   - 保存测试、编译、前端 build、静态扫描、review 和 diff 验收材料。

## 9. 验收材料

1. 测试日志：`ai/outbox/inventory_sales_production_m4_6/test.log`
2. 编译日志：`ai/outbox/inventory_sales_production_m4_6/compile.log`
3. 前端依赖恢复日志：`ai/outbox/inventory_sales_production_m4_6/frontend-npm-ci.log`
4. 前端 build 日志：`ai/outbox/inventory_sales_production_m4_6/frontend-build.log`
5. 静态扫描日志：`ai/outbox/inventory_sales_production_m4_6/static-scan.log`
6. 独立 review 结果：`ai/outbox/inventory_sales_production_m4_6/review-result.json`
7. 补丁：`ai/outbox/inventory_sales_production_m4_6/diff.patch`
8. 本文件：`ai/outbox/inventory_sales_production_m4_6/final-acceptance.md`

## 10. 风险点

1. 当前产销存问答仍是受控 QueryPlan 桥接，不是完整 NL2SQL。
2. 同比、环比、任意月份区间和库存周转率本轮选择 fail-closed/澄清，后续若业务确认计算口径，需要另开 M5 或后续阶段扩展。
3. 前端 build 在新 worktree 需要先 `npm ci` 恢复依赖。
4. 本轮未做真实浏览器页面 E2E 截图；如果需要最终业务演示，可另起浏览器联调验证。

## 11. 对既有能力影响

1. 物流问答：未修改。
2. 计划 BOM：未修改。
3. 功率预测：未修改。
4. SAP 物管：未修改。
5. 前端入口：未改前端代码，production build 已通过。

## 12. 阶段边界与操作声明

1. 已遵守 M4-6 阶段边界。
2. 未自动 commit。
3. 未自动 push。
4. 未 deploy。
5. 未修改 `.env`、密钥或连接串。
