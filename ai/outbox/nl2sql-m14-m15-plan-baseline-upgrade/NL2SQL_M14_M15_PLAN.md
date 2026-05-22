# M14–M15 + 基线提升 开发计划

## 前置确认

- 当前分支：`feature/nl2sql-m11`（基于 agent/bp-main）
- 全量测试：325 NL2SQL + 物流 QA + query planning = 431 passed
- 文档依据：`docs/NL2SQL_LOGISTICS_QA_SIDECAR_DESIGN.md`

---

## M14：Shadow 结果对比与告警

### 目标

在 `LogisticsNl2SqlLiveShadowAdapter` 基础上，建立 formal QA 结果与 NL2SQL shadow 结果的**结构化对比**。

### 范围

1. **对比字段**：formal_status ↔ shadow.status，result_table.rows count ↔ shadow.row_count，error_codes 差异
2. **差异阈值**：定义 row_count 差异允许范围（±10% 或差 ≤5 行），超出标记为 diff
3. **告警机制**：对比发现差异时通过 logger.warning 输出结构化告警（trace_id+差异字段）
4. **差异率统计**：累积统计一段时间内的 total_shadow、diff_count、diff_ratio

### 新增/修改文件

| 文件 | 动作 | 说明 |
|------|------|------|
| `nl2sql/m14_shadow_comparator.py` | 新增 | Shadow 对比器：对比 formal vs shadow，输出差异报告 |
| `nl2sql/m14_shadow_alerter.py` | 新增 | 差异告警器：logger.warning + 累计统计 |
| `tests/unit/logistics/nl2sql/test_m14_shadow_comparator.py` | 新增 | RED-GREEN-REFACTOR 测试 |
| `tests/unit/logistics/nl2sql/test_m14_shadow_alerter.py` | 新增 | 告警器测试 |
| `nl2sql/__init__.py` | 修改 | 导出 M14 模块 |
| `data_qa_service.py` | 修改 | 在 `_build_nl2sql_live_shadow_audit` 后串联对比+告警 |

### 不做

- 不接入外部监控平台（PagerDuty/Slack 等）
- 不改变前端展示
- 不影响正式 QA 主链路
- 不改物流/BOM/功率预测基线

---

## M15：灰度接管

### 目标

在 shadow 稳定后，对低风险问题类型逐步灰度切换。

### 范围

1. **风险分类**：简单 aggregate / 按维度拆分 / 多指标汇总
2. **灰度开关**：每类问题独立开关
3. **旧链路兜底**：灰度启用时先检查 shadow 结果质量，有差异时回退
4. **A/B 对比报表**：统计灰度期间两类问题的对比数据

### 新增/修改文件

| 文件 | 动作 | 说明 |
|------|------|------|
| `nl2sql/m15_grayscale_gate.py` | 新增 | 灰度门禁：风险分类 + 开关 + 回退 |
| `tests/unit/logistics/nl2sql/test_m15_grayscale_gate.py` | 新增 | 灰度门禁测试 |
| `nl2sql/__init__.py` | 修改 | 导出 M15 模块 |
| `data_qa_service.py` | 修改 | 灰度 gate 串联 |

### 不做

- 不全面替代正式 QA 主链路
- 不改变前端展示
- 不做全量灰度

---

## 基线提升：扩样例 + SQLPlan 生成质量

### 目标

在 M14/M15 完成基础上，扩展物流 NL2SQL 评估样例集，提升 SQLPlan 生成质量。

### 范围

1. **扩样例**：从现有物流样例题中提取更多 NL2SQL 覆盖场景
2. **瓶颈分析**：分析当前 shadow gate 失败样例的根因
3. **SQLPlan 质量提升**：针对常见失败模式改进 catalog recall / SQLPlan generation / repair
4. **回归通过**：所有新样例通过后全量回归

### 新增/修改文件

| 文件 | 动作 | 说明 |
|------|------|------|
| `m10_shadow_gate_runner.py` | 修改 | 新增样例 |
| 多个 NL2SQL 模块 | 修改 | 按瓶颈分析结果改进 |
