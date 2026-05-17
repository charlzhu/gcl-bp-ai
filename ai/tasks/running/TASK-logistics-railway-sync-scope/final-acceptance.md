# TASK-logistics-railway-sync-scope 最终验收报告

## 一、任务结论

本次问题不是自然语言解析错误，也不是 `sys_mw_and_trip_count` 接口 SQL 对 `transport_mode='铁路'` 的过滤错误；根因是正式物流系统同步源任务时，使用了 `create_time >= start_date` 作为 2026 正式数据范围，导致“2025 年创建、2026 年提货”的铁路任务没有同步进 ODS/DWD。

## 二、证据

- 源库口径：2026 年 1、2 月，运输方式=铁路，按 pickup_date 统计共有 8 个任务、8 行产品，合计 23.789 MW。
- 中间库口径：ODS/DWD 当前只有 4 个铁路任务，产品 power 均为空，合计 0 MW。
- 漏同步关键任务：11147、11148、11149、11150，均为 `create_time=2025-12-31`、`pickup_date=2026-01-03~2026-01-06`，源库合计 23.789 MW。
- RED 测试复现：修复前 `fetch_ship_tasks(start_date='2026-01-01')` 漏掉 11147。

## 三、修改文件

1. `backend/app/domains/logistics/repositories/sync_repository.py`
   - `fetch_ship_tasks()` 正式范围过滤由 `DATE(create_time)` 改为 `DATE(COALESCE(pickup_date, create_time))`。
   - `biz_date` 同步改用同一业务日期表达式。
   - 排序改为 `业务日期 + create_time + task_id`，保证分页稳定。

2. `tests/business_acceptance/test_logistics_system_sync_normalization.py`
   - 新增回归测试 `test_fetch_ship_tasks_uses_pickup_date_as_formal_scope`，覆盖跨年创建、2026 提货任务必须被同步纳入。
   - 补充 `pickup_date IS NULL` 且 `create_time >= start_date` 的兜底用例，锁定 `COALESCE(..., create_time)` 兼容行为。

3. `ai/tasks/running/TASK-logistics-railway-sync-scope/test.log`
   - 记录源库/中间库核对、RED/GREEN、回归测试结果。

4. `ai/tasks/running/TASK-logistics-railway-sync-scope/diff.patch`
   - 本轮相关代码 diff。

5. `ai/tasks/running/TASK-logistics-railway-sync-scope/review-result.json`
   - 独立 review 结果。

## 四、测试结果

- `test_fetch_ship_tasks_uses_pickup_date_as_formal_scope`：1 passed
- `test_logistics_system_sync_normalization.py`：3 passed
- 编译 + 同步归一化 + 物流 E2E round1：31 passed
- 全量 `tests/business_acceptance/test_logistics*.py`：当前分支存在 3 个复合问题拆分用例失败（`test_logistics_llm_led_composite_decomposition.py`），单跑仍失败；失败文件不在本轮修改范围，判断为当前分支既有非本任务问题。本轮同步口径相关测试均通过。

## 五、Review 与安全

- 独立 review：passed=true，无 blocking findings。
- Review 非阻塞建议 `pickup_date IS NULL` fallback 用例已补。
- 静态泄密扫描：PASS，未发现硬编码凭据或连接信息。

## 六、风险与后续处理

代码已修复同步口径，但当前 ODS/DWD 存量仍缺少漏同步数据。需要在用户确认后执行一次正式补同步/全量同步：`start_date=2026-01-01`、`updated_since=None`，并同步 ship_task + ship_product + DWD upsert/rebuild，才能让前台问题返回源库一致的 23.789 MW。

未在本轮自动写真实中间库，避免未经确认改动生产/共享数据。

## 七、是否影响现有能力

- 影响范围：仅正式物流系统同步的 ship_task 拉取范围。
- 对历史 2023–2025 Excel 台账问答无影响。
- 对接口查询逻辑无破坏性变更。
- 对 2026 正式数据是修正业务口径：按 pickup_date 纳入正式月份，而不是按 create_time。
