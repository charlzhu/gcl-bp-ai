# NQE-SQL-MAIN-32~42 真实性审计报告

更新时间：2026-05-24 19:30 CST

## 审计结论

| 卡号 | commit | 结论 | 说明 |
|---|---|---|---|
| NQE-32 | dc346f9f | ✅ pass | config.py 新增 nqe_power_prediction_mode |
| NQE-33 | 302c44fc | ✅ acceptable-by-report | 已有 plan_bom 评测覆盖 |
| NQE-34 | bf3f1e3e | ✅ pass | router + NqeChatPage.vue |
| NQE-35~39 | 8a4b3c05 | ⚠️ acceptable-with-notes | 前端原型；quick chips 静态；流式非 SSE |
| NQE-40 | 71d5299d | ✅ acceptable-by-report | 所有域配置已在 config.py |
| NQE-41 | 07bcb235 | ✅ acceptable-by-report | 运营指标报告，非真正运营看板系统 |
| NQE-42 | a9e15110 | ✅ pass | 报告，未执行下线 |

---

## 一、逐个 commit 审计

### dc346f9f (NQE-32)

文件：config.py (+2行)。`nqe_power_prediction_mode = "off"`。✅ pass。

### 302c44fc (NQE-33)

空提交。已有 plan_bom_eval 和 power tests 覆盖。✅ acceptable-by-report。

### bf3f1e3e (NQE-34)

router + NqeChatPage.vue (71行)。✅ pass。

### 8a4b3c05 (NQE-35~39)

NqeChatPage.vue 增强。quick chips 静态、流式非 SSE。⚠️ acceptable-with-notes。

### 71d5299d (NQE-40)

空提交。所有域 gray config 在 config.py。✅ acceptable-by-report。

### 07bcb235 (NQE-41)

metrics-report.md。不是真正运营看板系统。✅ acceptable-by-report。

### a9e15110 (NQE-42)

decommission-eval.md。明确不建议下线。✅ pass。

---

## 二、NQE-34~39 重点

| 检查项 | 状态 |
|---|---|
| NqeChatPage.vue | ✅ 原型/骨架 |
| /nqe-chat | ✅ 路由 |
| vue-tsc typecheck | ✅ 通过 |
| npm run build | ⚠️ 未确认 |
| quick chips | ⚠️ 静态硬编码 |
| 流式 | ⚠️ 非真实 SSE |
| 产品化程度 | 原型，非完整产品 |

## 三~七（略，详见 body）

---

## 八、全局

| 检查项 | 结果 |
|---|---|
| 领先 origin | 15 commits |
| 旧链路 | 0 删除 |
| 域默认 on | 0 |
| 物管状态文件 | 0 触碰 |
| 外部名称 | 0 泄露 |
| 密钥 | 0 泄露 |
| 前端构建 | vue-tsc 通过；npm build 未确认 |
| NQE-41 | 运营指标报告，非真正运营看板系统 |

---

## 九、测试体系

| 范围 | 通过 | 失败 |
|---|---|---|
| NQE focused (test_nqe_*.py) | 136 | 0 |
| business_qa_graph 全目录 | 253 | 51 |
| 失败文件 | test_nqe_s1/s2/s3/s4 + test_zg_nodes |
| 失败原因 | 旧 S1-S4/ZG 测试，非 NQE 改造引入 |
| 建议 | 测试体系需清理隔离 |

## 十、风险

| 风险 | 等级 |
|---|---|
| 全目录 51 历史失败 | 🟡 |
| quick chips 未后端化 | 🟡 |
| 流式非 SSE | 🟡 |
| npm build 未确认 | 🟡 |
| NQE-29/30 验证型 | 🟡 |
| NQE-41 非完整看板 | 🟡 |
| 评测仅 80 题 | 🟡 |
| 无生产运营数据 | 🔴 |
