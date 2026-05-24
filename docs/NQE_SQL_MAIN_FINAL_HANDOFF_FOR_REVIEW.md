# NQE 统一 SQL Agent — 最终人工 Review 交接

更新时间：2026-05-24 19:30 CST

---

## 1. 当前完成了什么

### NQE-SQL-MAIN 全部 43 张卡完成

| 类别 | 内容 |
|---|---|
| 后端主体链路 | unified SQL Agent Graph + domain route + 4域 auto-context |
| 安全/质量 | SQL safety precheck + EXPLAIN validate + correct loop + trace/replay |
| 元数据 | nqe_metadata_sync.py + catalog (3 domain) |
| 灰度 | 4域独立 off/shadow/assist/on 配置，全部默认 off |
| adapter | BOM candidate + compare/replay, PowerPredictionEngine fallback, logistics shadow compare |
| 前端 | NqeChatPage.vue 原型 + /nqe-chat 路由, vue-tsc typecheck 通过 |
| 评测 | 物流 50题 + BOM 30题 |
| 报告 | Go/No-Go 评审 + 审计 + 旧链路下线评估 + 运营指标 |

### 28 个 NQE commits on agent/bp-main

---

## 2. 当前没有完成什么

- 物流 903 题全量评测
- BOM 129 题全量评测
- 产销存评测集 / 功率预测评测集
- quick chips 后端化
- SSE 流式消费器
- npm run build 完整前端构建（仅 vue-tsc）
- 任何域的 shadow/assist/on 开启

---

## 3. 人工 review 必看风险

| 风险 | 说明 |
|---|---|
| 🔴 business_qa_graph 全目录 51 历史失败 | test_nqe_s1(5) + s2(2) + s3(2) + s4(11) + test_zg_nodes(~31)。非 NQE 改造引入，但测试体系需清理隔离 |
| 🟡 quick chips 未后端化 | NqeChatPage.vue 硬编码 4 个示例问题 |
| 🟡 流式非 SSE | 当前 fetch 一次性调用，非 EventSource |
| 🟡 npm build 未确认 | 仅 vue-tsc typecheck 通过，完整构建未执行 |
| 🟡 NQE-29/30 验证型 | 仅新增测试确认已有 catalog 覆盖，未新增功率实现 |
| 🟡 NQE-41 非完整看板 | 仅为 metrics-report.md 报告，非运营看板系统 |
| 🔴 无生产运营数据 | 评测仅 80 题，无 shadow 模式运营积累 |

---

## 4. 当前不能上线的原因

- 全目录 51 个历史测试失败
- 全量评测覆盖率不足 (80/903+129)
- 前端非完整产品化
- quick chips 未后端化 / SSE 未实现
- shadow 模式无生产运营数据

---

## 5. 测试口径

| 范围 | 通过 | 失败 | 状态 |
|---|---|---|---|
| NQE-SQL-MAIN focused | 136 | 0 | ✅ |
| business_qa_graph 全目录 | 253 | 51 | ⚠️ |
| 失败来源 | S1-S4 + ZG | — | 旧测试，非 NQE 引入 |

---

## 6. 可 review commit 范围

`5b802bb2` (NQE-0~13) → `HEAD` (NQE-43)

15 commits ahead of origin/agent/bp-main

---

## 7. push 建议

推送到备份分支，不直接 push agent/bp-main：

```bash
git push origin agent/bp-main:nqe-sql-main-final-20260524
```

---

## 8. 安全边界

| 检查项 | 状态 |
|---|---|
| 域默认 off | ✅ |
| 旧链路删除 | ❌ |
| PowerPredictionEngine | ✅ 未修改 |
| 物管状态文件 | ✅ 未触碰 |
| 外部名称 | ✅ 0 |
| 密钥 | ✅ 0 |
