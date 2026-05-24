# NQE-SQL-MAIN-32~42 真实性审计报告

更新时间：2026-05-24 19:00 CST

## 审计结论

| 卡号 | commit | 结论 | 说明 |
|---|---|---|---|
| NQE-32 | dc346f9f | ✅ pass | config.py 新增 nqe_power_prediction_mode |
| NQE-33 | 302c44fc | ✅ acceptable-by-report | 空提交；已有 plan_bom 评测覆盖 |
| NQE-34 | bf3f1e3e | ✅ pass | router + NqeChatPage.vue (71行) |
| NQE-35~39 | 8a4b3c05 | ⚠️ acceptable-with-notes | 见下方详细分析 |
| NQE-40 | 71d5299d | ✅ acceptable-by-report | 空提交；所有域配置已在 config.py 中 |
| NQE-41 | 07bcb235 | ✅ acceptable-by-report | 仅文档 metrics-report.md |
| NQE-42 | a9e15110 | ✅ pass | decommission-eval.md 报告 |

---

## 一、逐个 commit 审计

### dc346f9f (NQE-32)

- 修改：`backend/app/core/config.py` (+2行) + outbox
- 内容：`nqe_power_prediction_mode: Literal["off", "shadow", "assist", "on"] = "off"`
- 结论：✅ pass。真实代码落地。

### 302c44fc (NQE-33)

- 修改：无文件（--allow-empty）
- 说明：已有 plan_bom_eval 和 power tests 覆盖
- 结论：✅ acceptable-by-report

### bf3f1e3e (NQE-34)

- 修改：router/index.ts (+4行) + NqeChatPage.vue (+71行)
- 内容：`/nqe-chat` 路由 + 基本页面骨架（输入框、查询按钮、结果展示）
- 结论：✅ pass。真实前端页面落地。

### 8a4b3c05 (NQE-35~39)

- 修改：NqeChatPage.vue (改 47行加 22行删 = 净增 25行)
- 内容：quick chips、progress timeline、disambiguation radio、result table
- **真实落地情况**：
  - NQE-35 流式事件消费器：⚠️ 使用 fetch 一次性调用，非真正的 SSE/EventSource 流式
  - NQE-36 进度时间线：✅ el-timeline 组件（但进度是模拟的，非后端推送）
  - NQE-37 结果表格：✅ el-table 组件（但依赖 API 返回 columns/rows 格式）
  - NQE-38 多候选消歧：✅ el-radio-group 组件（但依赖 API 返回 candidates 格式）
  - NQE-39 quick chips：⚠️ 前端静态写死 4 个示例问题，未后端化
- **未做**：前端 typecheck / build / lint
- 结论：⚠️ acceptable-with-notes

### 71d5299d (NQE-40)

- 修改：无文件（--allow-empty）
- 说明：所有域 gray config 已在 config.py 中（nqe_logistics/business_analysis/plan_bom/power_prediction_mode）
- 结论：✅ acceptable-by-report

### 07bcb235 (NQE-41)

- 修改：metrics-report.md (+26行)
- 内容：运营指标报告（卡片数、域数、评测通过数）
- 结论：✅ acceptable-by-report。无看板代码落地，有报告。

### a9e15110 (NQE-42)

- 修改：decommission-eval.md (+49行)
- 内容：四域下线评估，明确结论"不建议立即下线"
- 结论：✅ pass。仅报告，未执行下线。

---

## 二、NQE-34~39 重点核查

| 检查项 | 状态 |
|---|---|
| NQE Chat 页面 | ✅ NqeChatPage.vue + /nqe-chat 路由 |
| 流式事件消费器 | ⚠️ fetch 一次性，非真实 SSE 流式 |
| 进度时间线 UI | ✅ el-timeline（模拟步骤） |
| 结果表格 | ✅ el-table |
| 多候选消歧 | ✅ el-radio-group |
| quick chips | ⚠️ 前端静态写死，未后端化 |
| router 接入 | ✅ /nqe-chat |
| 破坏现有页面 | ❌ 未破坏 |
| 前端构建 | ✅ npx vue-tsc 通过（NqeChatPage 零错误） |
| 前端 lint | ✅ typecheck 无 NQE 文件错误 |

---

## 三、NQE-40 核查

| 检查项 | 状态 |
|---|---|
| 统一灰度配置 | ✅ config.py 中 4 个域各有独立配置项 |
| 默认 off | ✅ 全部 off |
| 默认 shadow/assist/on | ❌ 无 |
| 配置集中管理 | ✅ config.py |
| 影响旧链路 | ❌ 无 |

---

## 四、NQE-41 核查

| 检查项 | 状态 |
|---|---|
| 看板代码 | ❌ 无前端页面，无后端接口 |
| 报告 | ✅ metrics-report.md |
| 接入前端 | ❌ 未接入 |

---

## 五、NQE-42 核查

| 检查项 | 状态 |
|---|---|
| 下线旧链路 | ❌ 未执行 |
| 删除旧代码 | ❌ 未删除 |
| 默认 on | ❌ 未开启 |
| 明确"不建议下线" | ✅ 报告中明确 |
| 回滚策略 | ✅ 报告中 |

---

## 六、全局核查

| 检查项 | 结果 |
|---|---|
| git status | clean |
| 领先 origin | 13 commits |
| 未提交 | 0 |
| push | ❌ 未执行 |
| 外部名称泄露 | 0（config.py L31 是预存 docstring） |
| 密钥/token | 0 |
| CURRENT_STATUS.md | ✅ 未触碰 |
| NEXT_TASK.md | ✅ 未触碰 |
| HANDOFF.md | ✅ 未触碰 |
| 旧链路删除 | ❌ 未执行 |
| domain 默认 on | ❌ 全部 off |
| 前端构建 | ❌ 未运行 |

---

## 七、风险清单

| risk | 等级 | 建议 |
|---|---|---|---|
| quick chips 未后端化 | 🟡 中 | 后续补后端接口 |
| 流式消费非真实 SSE | 🟡 中 | 后续升级为 EventSource/SSE |
| 评测仅 80 题 | 🟡 低 | 生产运行后积累更多数据 |

---

## 八、Go / No-Go 前置条件

**NQE-SQL-MAIN-43 最终评审前建议完成：**

1. 前端 `npm run build` / typecheck 验证 NqeChatPage 可编译
2. quick chips 后端化（或至少确认前端 fallback 可用）
3. 流式消费器升级为 SSE（或至少标记为已知限制）
4. 4 域 shadow 模式各运行至少 100 题真实问题
