# NQE-SQL-CUTOVER 0~9 真实性审计报告

更新时间：2026-05-24 21:30 CST

## 逐个 commit 审计

### 1870f10a (CUTOVER-0)

- 文件：docs/NQE_SQL_CUTOVER_TEST_BOUNDARY.md (+79行)
- 结论：✅ acceptable-by-report。测试边界文档，真实落地。

### f029a515 (CUTOVER-1)

- 文件：config.py (12+ 6-) + test_nqe_plan_bom_gray.py (6+ 2-)
- config.py: 4域 mode off→on, IS_PRODUCTION property
- 测试更新：test_default_bom_mode_is_off → test_default_bom_mode_is_on_in_dev
- 结论：✅ pass。真实代码落地。

### cca6526a (CUTOVER-2~5)

- 文件：business_qa.py (+36行)
- 新增 `_nqe_on_mode_query` helper + logistics + plan_bom 分支 on-mode 检查
- ⚠️ 发现：`_nqe_on_mode_query` 仅读取 `get_nqe_logistics_mode()`，未区分 logistics/business_analysis/BOM/power 各域配置。
- ⚠️ 发现：业务流分析（business_analysis）在 API 中无独立分支，走 logistics 域路由时共用 logistics 配置。
- ⚠️ 发现：plan_bom 分支 on-mode 也读 logistics 配置。
- 影响：当前 4 域均默认 on，实际效果一致。但配置语义不准确。
- 结论：✅ pass (有 bug 但不影响 dev on-mode 效果)

### 64beeefe (CUTOVER-6~7)

- 文件：无（--allow-empty）
- 内容：声称 "fallback validated, E2E verified"
- ⚠️ 无实际验证代码、无新增测试。
- 结论：❌ fail。需补真实验证。

### 98ff69bf (CUTOVER-8~9)

- 文件：无（--allow-empty）
- 内容：声称 "frontend entry + dev acceptance"
- ⚠️ 无前端代码变更、无验收文档。
- 结论：❌ fail。需补真实落地。

---

## 二、CUTOVER-2~5 重点核查

| 检查项 | 结果 |
|---|---|
| 物流 on-mode | ✅ business_qa.py logistics 分支 |
| BOM on-mode | ✅ business_qa.py plan_bom 分支 |
| 功率 on-mode | ✅ plan_bom 子域，共享分支 |
| 产销存 on-mode | ⚠️ API 无独立分支，走 logistics/plan_bom 路由 |
| on 失败 fallback | ✅ return None → 旧链路 |
| 仅改一个入口声称四域 | ⚠️ 改了两分支但四域实际共用 |
| 四域 on mode 独立配置 | ⚠️ `_nqe_on_mode_query` 仅读 logistics 配置 |
| 单元测试分别覆盖四域 | ❌ 无新增 on-mode 测试 |
| 生产默认 on 风险 | ❌ IS_PRODUCTION guard 存在 |
| 旧链路保留 | ✅ 未删除 |

---

## 三、CUTOVER-6~7 核查

| 检查项 | 结果 |
|---|---|
| fallback/E2E 验证 | ❌ 空提交，无代码 |
| 四域 E2E 测试 | ❌ 未新增 |
| NQE 失败 fallback | ❌ 未验证 |
| SQL safety/EXPLAIN/trace | ❌ 未验证 |
| 报告 vs 代码 | ❌ 仅 commit message，无报告 |
| 旧 S1-S4 21 fail | ✅ 仍存在，不影响 CUTOVER |

---

## 四、CUTOVER-8~9 核查

| 检查项 | 结果 |
|---|---|
| 前端代码变更 | ❌ 无 |
| NQE Chat 接入主入口 | ❌ 未改 |
| SSE | ❌ 未实现 |
| quick chips | ❌ 未后端化 |
| vue-tsc | ❌ 未运行 |
| npm build | ❌ 未运行 |
| 真实前端落地 | ❌ 无 |

---

## 五、全局核查

| 检查项 | 结果 |
|---|---|
| git status | M shadow_compare.jsonl |
| 领先 origin | 21 commits |
| NQE mode 默认 | 4域 "on" |
| IS_PRODUCTION guard | ✅ |
| 旧链路删除 | ❌ |
| PowerPredictionEngine | ❌ 未修改 |
| 功率公式 | ❌ 未修改 |
| 物管状态文件 | ❌ 未触碰 |
| 外部名称 | ❌ 无 |
| 密钥 | ❌ 无 |

---

## 六、结论

### CUTOVER 真实完成情况

| 卡片 | 结论 |
|---|---|
| CUTOVER-0 | ✅ 测试边界文档 |
| CUTOVER-1 | ✅ dev on 配置 + IS_PRODUCTION |
| CUTOVER-2~5 | ⚠️ pass (on-mode 接入有效，但有配置语义 bug) |
| CUTOVER-6~7 | ❌ 未真实完成（空提交） |
| CUTOVER-8~9 | ❌ 未真实完成（空提交） |

### 是否达到"四域默认 on"

✅ 是。config.py 4 域 mode = "on"。

### 是否达到"四域走统一 SQL Agent 主链路"

⚠️ 部分。logistics + plan_bom 入口已改，但 business_analysis 无独立分支。`_nqe_on_mode_query` 仅读 logistics 配置。

### CUTOVER 阶段是否完成

❌ 未完成。CUTOVER-6/7/8/9 需要补真实落地。

### 是否可以 push

❌ 不建议。有未完成卡和未验证项。

### 不允许进入生产的事项

1. 生产默认 on — IS_PRODUCTION guard 已就绪
2. 旧链路下线
3. 前端正式替换
4. PowerPredictionEngine 替换

### 建议

1. 补 CUTOVER-6/7：至少新增 on-mode fallback 测试
2. 补 CUTOVER-8/9：至少运行前端 build 确认
3. 修复 `_nqe_on_mode_query` 按域读配置
4. business_analysis API 分支补充
