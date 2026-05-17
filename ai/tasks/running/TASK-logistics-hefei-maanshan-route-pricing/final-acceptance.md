# TASK-logistics-hefei-maanshan-route-pricing 最终验收

## 1. 问题结论

用户反馈题：`23年-25年，3年间合肥-深圳13米均价分别是多少` 已修复。

当前确定性问答链路返回：

- 不再要求补充口径：`needs_clarification=False`
- 时间区间识别为：`2023, 2024, 2025`
- 始发地识别为：`合肥`
- 目的地识别为：`深圳`
- 车型识别为：`13`
- 指标口径识别为：线路均价，按 `总费用 / 总车次` 计算
- 结果表：
  - 2023 年：无匹配记录，保留空值行
  - 2024 年：无匹配记录，保留空值行
  - 2025 年：均价 `9,623` 元，总费用 `28,870` 元，车次 `3`，明细行 `3`

## 2. 根因

原链路不是数据无法计算，而是自然语言槽位抽取不完整：

1. `23年-25年` 两位年份区间没有先展开为 `[2023, 2024, 2025]`，容易漏掉中间年份。
2. `合肥-深圳13米均价` 中横线形式的线路表达没有稳定抽取目的城市 `深圳`。
3. `均价` 没有作为目的城市右边界参与该线路模板，导致 planner 可能无法进入历史线路运价分析。

## 3. 修复内容

### 生产代码

- `backend/app/domains/logistics/services/slot_extractor.py`
  - 增加两位年份区间解析：支持 `23年-25年`、`23年至25年`、`23年到25年`、`23年~25年` 等写法，展开中间年份。
  - 扩展受控线路连接词：在既有 `至/到` 基础上支持普通横线/破折号连接的线路表达。
  - 将 `均价` 纳入线路目的城市右边界。
  - 保留安全边界：未知始发地、多段路径仍要求澄清，不静默放大为全始发/错误线路。

### 回归测试

- `tests/business_acceptance/test_logistics_route_pricing_hefei_maanshan.py`
  - 新增截图题同类用例：`23年-25年，3年间合肥-深圳13米均价分别是多少`。
  - 锁定 planner filters、service 结果、逐年空值行和 2025 年确定性数值。
  - 增加负向保护：未知始发地、多段路径、未确认的箭头连接符不误直答。
  - 增加均价口径保护：线路均价使用 `SUM(total_fee) / SUM(shipment_trip_count)`，不是行均值。

## 4. 验证记录

完整日志：`ai/tasks/running/TASK-logistics-hefei-maanshan-route-pricing/test.log`

已通过：

1. 精确截图题 focused：`1 passed`
2. 路线定价回归文件：`7 passed`
3. 相关历史运价/路线用例：`4 passed, 30 deselected`
4. 物流相关业务验收：`81 passed`
5. Python 编译检查：`compileall OK`
6. TestClient API 精确问题验证：`status=200`、`needs_clarification=False`、2025 均价 `9623`
7. 静态安全扫描：`STATIC_SCAN_FINDINGS=0`
8. 前端构建：`npm run build OK`
9. 业务验收全量：`227 passed, 2 warnings`
10. 测试全量：`286 passed, 2 warnings`

说明：2 个 warning 均来自 `openpyxl` 对 xlsm 扩展/条件格式的读取提示，非本次修复引入。

## 5. 独立审查

审查结果文件：`ai/tasks/running/TASK-logistics-hefei-maanshan-route-pricing/review-result.json`

结论：通过。

审查摘要：生产代码未硬编码数值答案，年份区间、横线路线与均价语义修复受控，未发现安全问题或会导致未知始发地/多段路径误直答的逻辑错误。

非阻塞建议：后续可补充全角横线 `－` 用于两位年份区间的测试覆盖。

## 6. 影响范围

- 影响物流数据问答中的历史线路运价/均价类问题。
- 不修改 BOM / 计划 BOM / 功率预测代码。
- 不修改前端功能代码。
- 未改变既有数据库结构、接口结构或权限逻辑。

## 7. 当前仍需注意

工作区中存在大量非本任务的历史/并行未提交文件，本次验收只基于任务范围内的生产代码与回归测试。任务范围 diff 已生成：

- `ai/tasks/running/TASK-logistics-hefei-maanshan-route-pricing/diff.patch`
