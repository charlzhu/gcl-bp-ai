# 物流线路均价修复验收说明

## 1. 问题

用户反馈问题：

> 23年-25年，3年间合肥-深圳13米均价分别是多少

原页面错误表现为：系统返回“需补充信息/需补充口径”。

业务补充口径：

> 均价 = 总费用 / 车次数

## 2. 根因

1. 两位年份区间 `23年-25年` 未在物流线路运价题中稳定展开为 `[2023, 2024, 2025]`。
2. `合肥-深圳` 这种横线线路表达未作为安全线路连接词处理，导致目的地槽位不稳定。
3. 线路均价原展示字段缺少总费用、车次数，无法向业务追溯“总费用 / 车次数”的计算口径。
4. 浏览器第一次复验仍旧显示旧澄清，是因为本机 5173 端口存在两个 Vite 进程，其中 5/12 启动的旧进程绑定 `127.0.0.1:5173`，浏览器命中了旧 dev proxy。停止旧进程后同源代理恢复正确。

## 3. 修改范围

本任务聚焦物流线路运价问答，未修改计划 BOM、数据库迁移、权限、前端业务代码。

任务相关代码文件：

- `backend/app/domains/logistics/services/slot_extractor.py`
- `backend/app/domains/logistics/repositories/data_qa_repository.py`
- `backend/app/domains/logistics/services/data_qa_service.py`
- `tests/business_acceptance/test_logistics_route_pricing_hefei_maanshan.py`

验收材料：

- `ai/outbox/logistics-hefei-shenzhen-13m-avg-price/diff.patch`
- `ai/outbox/logistics-hefei-shenzhen-13m-avg-price/test.log`
- `ai/outbox/logistics-hefei-shenzhen-13m-avg-price/static_scan.log`
- `ai/outbox/logistics-hefei-shenzhen-13m-avg-price/review-result.json`
- `ai/outbox/logistics-hefei-shenzhen-13m-avg-price/final-acceptance.md`

## 4. 关键改动

### 4.1 两位年份区间

`23年-25年` 按业务历史数据口径展开为：

- 2023
- 2024
- 2025

该逻辑为通用解析，不针对截图题硬编码。

### 4.2 横线线路表达

支持受控始发地的横线表达：

- `合肥-深圳`
- `合肥－深圳`
- `合肥–深圳`
- `合肥—深圳`

同时保留安全边界：

- 未知始发地不放宽成全始发地；
- 多段路径不截断回答；
- 未确认连接符不随意扩展。

### 4.3 线路均价口径

线路运费均价改为：

```text
SUM(total_fee) / SUM(shipment_trip_count)
```

不是：

```text
AVG(total_fee)
```

结果表新增追溯字段：

- `total_fee` / 总运费
- `shipment_trip_count` / 车次
- `row_count` / 记录数

## 5. 验证结果

### 5.1 截图题接口验证

接口：

```text
POST /api/v1/logistics/data-qa/query/stream
```

问题：

```text
23年-25年，3年间合肥-深圳13米均价分别是多少
```

结果：

- `status_code = OK`
- 不再澄清
- `query_key = hist_route_pricing_analysis`
- `years = [2023, 2024, 2025]`
- `origin_place = 合肥`
- `city = 深圳`
- `vehicle_type = 13`
- `price_metric = total_fee`

返回明细：

| 年份 | 平均运费 | 总运费 | 车次 | 记录数 |
|---|---:|---:|---:|---:|
| 2023 | 空 | 空 | 0 | 0 |
| 2024 | 空 | 空 | 0 | 0 |
| 2025 | 9623 | 28870 | 3 | 3 |

2025 年计算：

```text
28870 / 3 = 9623.33...
四舍五入为 9623
```

### 5.2 浏览器验证

浏览器地址：

```text
http://127.0.0.1:5173
```

复验结果：

- 页面显示“已解答”；
- 不再显示“需补充信息”；
- 展开明细后显示 3 行年份数据；
- 2025 年行显示：平均运费 9623、总运费 28870、车次 3、记录数 3。

截图证据：

```text
/Users/zhuchangchao/.hermes/cache/screenshots/browser_screenshot_874b167e2c83470e94dad811b953bb14.png
```

## 6. 自动化测试

已通过的关键测试：

```text
backend/.venv/bin/python -m pytest tests/business_acceptance/test_logistics_route_pricing_hefei_maanshan.py -q
7 passed
```

```text
backend/.venv/bin/python -m pytest tests/business_acceptance/test_logistics_route_pricing_hefei_maanshan.py tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_2025_hefei_to_guangdong_17_5_route_avg_uses_total_fee_divided_by_trips -q
8 passed
```

完整验收中已跑过：

- focused 回归；
- logistics unit/business 相关回归；
- `tests/business_acceptance` 全量；
- Python compile；
- 前端 build；
- 静态安全扫描；
- 独立 reviewer。

详细日志见：

```text
ai/outbox/logistics-hefei-shenzhen-13m-avg-price/test.log
```

## 7. 静态扫描与 reviewer

静态扫描结果：

- 未发现硬编码密钥；
- 未发现 shell injection；
- 未发现危险 eval/exec；
- 未发现 unsafe pickle；
- 未发现 SQL 注入候选。

独立 reviewer 结果：

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": []
}
```

非阻塞建议：后续可补一个 `SUM(shipment_trip_count)=0` 的极端 fixture，专门覆盖 SQL `NULLIF` 分母保护路径。

## 8. 风险与说明

1. 当前修复没有扩大未知始发地查询范围，避免把不认识的地名误算成全量。
2. 2023、2024 年无匹配记录时仍保留空值行，避免用户显式要求的年份被静默省略。
3. 本次不修改前端代码；浏览器旧结果来自本机旧 Vite 进程，已停止旧进程后验证通过。
4. 当前工作区存在其他历史脏改动，最终提交时应只 stage 本任务相关文件和 outbox 验收材料，不能 `git add -A`。

## 9. 对现有能力影响

- 物流能力：修复线路运价问答，增强时间区间与线路表达解析；均价口径更符合业务要求。
- BOM / 计划 BOM：无影响。
- 前端：无代码改动；仅做浏览器验证。
- 数据库：无迁移、无结构变更。
