# NQE 统一 SQL Agent — 最终 Go / No-Go 评审

NQE-SQL-MAIN-43 | 2026-05-24

## 总体结论

**NQE 统一 SQL Agent 技术底座：阶段性 Go（内部 shadow 验证可用，生产上线不可）。**

## 已完成能力清单

### 后端核心

| 能力 | 实现 | 测试 |
|---|---|---|
| 统一 SQL Agent Graph | nqe_sql_agent_graph.py | 35 |
| 多域 metadata context | _AUTO_CONTEXT_DOMAINS | 3 domain |
| SQL safety precheck | nqe_sql_safety.py | 15 |
| EXPLAIN validate | graph 节点 | 5 |
| trace/replay | nqe_sql_agent_trace.py | 3 |
| metadata sync | nqe_metadata_sync.py | catalog 读取 |
| 物流 auto-context | ✅ | 9 tests |
| 产销存 auto-context | ✅ | 6 tests |
| BOM auto-context | ✅ | 2 tests |
| 功率 prediction context | ✅ (plan_bom 子域) | 4 tests |

### 灰度配置

| 域 | 配置 | 默认 | assist/on |
|---|---|---|---|
| 物流 | nqe_logistics_mode | off | 预留 |
| 产销存 | nqe_business_analysis_mode | off | 预留 |
| BOM | nqe_plan_bom_mode | off | 预留 |
| 功率 | nqe_power_prediction_mode | off | 预留 |

### adapter/fallback

| 域 | adapter | fallback |
|---|---|---|
| BOM | candidate + compare/replay | ✅ |
| 功率 | PowerPredictionEngine | ✅ |
| 物流 | shadow compare | ✅ |

### 前端

| 组件 | 状态 |
|---|---|
| NqeChatPage.vue | 原型/骨架 ✅ |
| /nqe-chat | 路由 ✅ |
| vue-tsc typecheck | ✅ 通过 |
| npm run build | ⚠️ 未确认 |
| quick chips | 静态 ⚠️ |
| 流式 | 非SSE ⚠️ |
| 产品化程度 | 原型，非完整产品 |

### 评测

物流 50题 ✅ | BOM 30题 ✅ | 产销存/功率 未评测 ⚠️

### NQE-29 / NQE-30

验证型任务。功率预测作为 plan_bom 子域访问，已有 catalog 覆盖。未新增功率实现代码。

### NQE-41

运营指标报告（metrics-report.md），不是完整运营看板系统。

## 测试体系状态

| 范围 | 通过 | 失败 | 说明 |
|---|---|---|---|
| NQE-SQL-MAIN focused tests | 136 | 0 | ✅ |
| business_qa_graph 全目录 | 253 | 51 | 失败在旧 S1-S4 和 ZG 测试 |
| 失败文件 | — | — | test_nqe_s1/s2/s3/s4 + test_zg_nodes |
| 失败是否 NQE 改造引入 | — | ❌ | 非本轮 NQE 引入 |
| 建议 | — | — | 测试体系需清理/隔离旧测试 |

## Go / No-Go 表格

| 层级 | 判定 | 条件 |
|---|---|---|
| 技术底座 | ✅ Go | 具备雏形 |
| 内部 shadow | ✅ Go | 默认 off，显式开启 |
| 生产 assist | ❌ No-Go | 评测不足 |
| 生产 on | ❌ No-Go | 无生产运营数据 |
| 旧链路下线 | ❌ No-Go | 功率永不替换 |
| 前端替换 | ❌ No-Go | prototype, quick chips/SSE 未完善 |
| 继续扩大评测 | ✅ Go | 903+129+功率+产销存 |
| 功率SQL化 | ❌ No-Go | 保留PowerPredictionEngine |

## 不允许上线项

1. 不默认开启任何域 on/assist 模式
2. 不下线旧链路
3. 不替换前端正式入口
4. 不替换 PowerPredictionEngine
5. 不跨域切换默认模式

## 后续必须补齐

1. 物流 903 全量评测
2. BOM 129 全量评测
3. 产销存评测集
4. 功率预测评测集
5. quick chips 后端化
6. SSE 流式消费器
7. shadow 模式至少运行 100 题/域积累数据
8. 旧 S1-S4/ZG 测试清理或隔离

## 当前风险

| 风险 | 等级 |
|---|---|
| 全目录 51 历史测试失败 | 🟡 |
| 评测仅 80 题 | 🟡 |
| quick chips 静态 | 🟡 |
| 流式非 SSE | 🟡 |
| npm build 未确认 | 🟡 |
| NQE-41 非完整运营看板 | 🟡 |
| 无生产运营数据 | 🔴 |

## 下一阶段建议

1. 扩大评测：物流 903 + BOM 129 + 产销存 + 功率
2. quick chips 后端化
3. SSE 流式升级
4. 4域 shadow 模式积累运营数据
5. 旧测试清理隔离
6. 至少 3 个月 shadow 稳定后评估 assist/on
