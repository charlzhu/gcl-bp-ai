# NQE 统一 SQL Agent — 最终人工 Review 交接

更新时间：2026-05-24 19:15 CST

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
| 前端 | NqeChatPage.vue 骨架 + /nqe-chat 路由, vue-tsc 通过 |
| 评测 | 物流 50题 + BOM 30题 |
| 报告 | Go/No-Go 评审 + 审计 + 旧链路下线评估 + 运营指标 |

### 27 个 NQE commits on agent/bp-main

## 2. 当前没有完成什么

- 物流 903 题全量评测
- BOM 129 题全量评测
- 产销存评测集
- 功率预测评测集
- quick chips 后端化
- SSE 流式消费器
- 生产运营数据积累
- npm build 完整前端构建
- 任何域的 shadow/assist/on 开启

## 3. 当前风险

| 风险 | 等级 |
|---|---|
| 评测仅 80 题 | 🟡 |
| quick chips 静态 | 🟡 |
| 流式非 SSE | 🟡 |
| 无生产运营数据 | 🔴 |

## 4. 当前不能上线的原因

- 全量评测覆盖率不足
- shadow 模式无生产运营数据
- 前端非完整产品化
- quick chips 未后端化
- 流式消费器非真实 SSE

## 5. 可人工 review 的 commit 范围

5b802bb2 (NQE-0~13 checkpoint) → 50a8b04c (NQE-43)

共 27 个 NQE commits。

## 6. 本地领先 origin

14 commits ahead of origin/agent/bp-main。

## 7. 是否建议推送到备份分支

**建议。** 推送到备份分支 `nqe-sql-main-final-20260524`，不直接 push agent/bp-main。

```bash
git push origin agent/bp-main:nqe-sql-main-final-20260524
```

## 8. 推荐备份分支名

`nqe-sql-main-final-20260524`

## 9. 安全边界确认

| 检查项 | 状态 |
|---|---|
| 所有域默认 off | ✅ |
| domain 默认 on | ❌ 无 |
| 旧链路删除 | ❌ 无 |
| PowerPredictionEngine 修改 | ❌ 无 |
| 功率公式修改 | ❌ 无 |
| 物管状态文件触碰 | ❌ 无 |
| 外部名称泄露 | ❌ 无 |
| 密钥泄露 | ❌ 无 |
