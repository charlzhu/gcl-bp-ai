# 物流系统自动同步部署说明

## 一、目标

发布服务器上线后，每天北京时间 00:00 自动执行一次物流 2026+ 正式系统数据同步。

同步范围：

- `logistic_ship_task`
- `logistic_ship_product`
- `logistic_assign_task`
- `logistic_assign_detail`
- `logistic_logistic_company`
- `logistic_warehouse`

当前仍按物流一期主链路执行，不包含 allocate、delivery note、图片、打卡、轨迹等二期对象。

## 二、上线前一次性操作

### 1. 确认配置

生产环境必须在 `backend/.env` 中配置：

```bash
MYSQL_HOST=...
MYSQL_PORT=3306
MYSQL_DB=logistics_ai
MYSQL_USER=...
MYSQL_PASSWORD=...

SOURCE_MYSQL_HOST=...
SOURCE_MYSQL_PORT=...
SOURCE_MYSQL_DB=...
SOURCE_MYSQL_USER=...
SOURCE_MYSQL_PASSWORD=...
```

说明：

- `MYSQL_*` 指向本地中间库。
- `SOURCE_MYSQL_*` 指向正式物流源系统库，只读账号即可。
- 不要把真实密码提交到仓库。

### 2. 备份中间库

首次上线前必须先备份中间库物流同步表：

```bash
mysqldump -h <host> -P <port> -u <user> -p logistics_ai \
  ods_logistic_company ods_logistic_warehouse ods_logistic_ship_task \
  ods_logistic_ship_product ods_logistic_assign_task ods_logistic_assign_detail \
  dwd_logistics_company dwd_logistics_warehouse dwd_logistics_ship_task \
  dwd_logistics_ship_product dwd_logistics_assign_task dwd_logistics_assign_detail \
  > logistics_sync_backup_$(date +%Y%m%d%H%M%S).sql
```

原因：

- 首次正式同步会清理历史重复源主键数据。
- 首次正式同步会补唯一索引，保证后续同步按源系统主键覆盖更新。

### 3. 执行一次基线同步

```bash
cd /path/to/gcl-bp-ai
/path/to/venv/bin/python scripts/logistics_system_auto_sync.py --full --start-date 2026-01-01
```

如果服务器直接使用系统 Python，可简化为：

```bash
cd /path/to/gcl-bp-ai
python3 scripts/logistics_system_auto_sync.py --full --start-date 2026-01-01
```

## 三、每天 00:00 自动同步

### 1. 推荐 crontab 配置

执行：

```bash
crontab -e
```

加入：

```cron
CRON_TZ=Asia/Shanghai
0 0 * * * cd /path/to/gcl-bp-ai && PYTHON_BIN=/path/to/venv/bin/python LOGISTICS_SYNC_OVERLAP_MINUTES=60 bash scripts/run_logistics_system_daily_sync.sh
```

说明：

- `0 0 * * *` 表示每天 00:00 执行。
- `CRON_TZ=Asia/Shanghai` 明确按北京时间调度。
- `LOGISTICS_SYNC_OVERLAP_MINUTES=60` 表示自动增量时向前回看 60 分钟，覆盖源库延迟写入。
- 脚本会写日志到 `data/logs/logistics_sync/daily-sync-YYYYMMDD.log`。
- 脚本在支持 `flock` 的 Linux 服务器上会自动加锁，避免上一次同步未结束时重复启动。

### 2. 手工试跑自动增量

配置 crontab 前，先手工执行一次：

```bash
cd /path/to/gcl-bp-ai
PYTHON_BIN=/path/to/venv/bin/python bash scripts/run_logistics_system_daily_sync.sh
```

检查日志：

```bash
tail -n 100 data/logs/logistics_sync/daily-sync-$(date +%Y%m%d).log
```

## 四、重复数据控制策略

同步入口会自动执行以下保护：

- ODS 表按 `source_id` 清理历史重复行，并补唯一索引。
- DWD 系统链路表按 `source_id` 清理历史重复行，并补唯一索引。
- 后续同步使用 upsert 覆盖更新，不按同步批次继续堆重复。
- 源系统 `del_flag` 标记删除的数据，会同步清理对应 DWD 旧数据。

注意：

- 不建议每天同步前清空全部中间表。
- 增量同步依赖中间表保留现有主数据，清空后会造成未变更数据丢失。
- 如需全量重建，应先备份，再手工执行 `--full` 基线同步。

## 五、日常检查

同步后可检查最近任务：

```sql
SELECT task_id, status, total_count, success_count, fail_count, message, started_at, finished_at
FROM sys_task_log
WHERE task_type = 'SYS_SYNC'
ORDER BY id DESC
LIMIT 10;
```

检查 DWD 是否存在源主键重复：

```sql
SELECT 'dwd_logistics_ship_task' AS table_name, COUNT(*) AS duplicate_keys
FROM (
  SELECT source_id FROM dwd_logistics_ship_task GROUP BY source_id HAVING COUNT(*) > 1
) t
UNION ALL
SELECT 'dwd_logistics_ship_product', COUNT(*)
FROM (
  SELECT source_id FROM dwd_logistics_ship_product GROUP BY source_id HAVING COUNT(*) > 1
) t
UNION ALL
SELECT 'dwd_logistics_assign_task', COUNT(*)
FROM (
  SELECT source_id FROM dwd_logistics_assign_task GROUP BY source_id HAVING COUNT(*) > 1
) t
UNION ALL
SELECT 'dwd_logistics_assign_detail', COUNT(*)
FROM (
  SELECT source_id FROM dwd_logistics_assign_detail GROUP BY source_id HAVING COUNT(*) > 1
) t;
```
