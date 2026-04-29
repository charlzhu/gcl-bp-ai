# 物流数据问答 MVP：2026 数据回补准备清单

## 一、文档目的

本清单用于固定当前物流数据问答 MVP 的 2026 数据回补准备事项。

当前原则：

- 只做 2026 关键字段回补准备；
- 不扩前端；
- 不扩 RAG；
- 不扩 Agent；
- 不碰 BOM 主链路；
- 不使用 mock 数据冒充真实回补。

---

## 二、当前需要回补的字段

当前代码链路已接入，但主库仍无真实值的字段如下：

- `project_name`
- `pickup_date`
- `expand_dept`
- `entrusted_person`
- `ship_product.price`

这些字段直接影响：

- 2026 业务月份统计
- 2026 总运费口径
- 2026 客户 / 项目问答
- 2026 特殊业务口径问答

---

## 三、当前阻塞

当前源库 `xst_cloud` 已可连接，但以下源表为空：

- `logistic_ship_task`
- `logistic_ship_product`
- `logistic_assign_task`
- `logistic_assign_detail`

因此当前无法通过系统同步接口自动回补 2026 关键字段真实值。

---

## 四、建议提供的导出文件清单

### 1. 发货任务主表导出

建议文件名：

- `2026_logistic_ship_task.xlsx`
- 或 `2026_logistic_ship_task.csv`

推荐格式：

- 优先 `xlsx`
- 备选 `csv (UTF-8)`

必需字段：

- `task_id`
- `project_name`
- `pickup_date`
- `expand_dept`
- `entrusted_person`
- `delivery_area`
- `delivery_province`
- `delivery_city`
- `ship_type`
- `status`
- `company_id`
- `create_time`

字段用途：

- `project_name`
  - 用于按 `-` 分隔后取第 3 段解析总车数
- `pickup_date`
  - 用于 2026 业务月份统计
- `expand_dept`
  - 用于“经营计划用车”筛选
- `entrusted_person`
  - 用于“刘娟用车”筛选
- `delivery_area / delivery_province`
  - 用于区域归一和覆盖率说明

### 2. 发货产品明细导出

建议文件名：

- `2026_logistic_ship_product.xlsx`
- 或 `2026_logistic_ship_product.csv`

推荐格式：

- 优先 `xlsx`
- 备选 `csv (UTF-8)`

必需字段：

- `task_id`
- `power`
- `quantity`
- `price`

字段用途：

- `power × quantity`
  - 用于 2026 发运量 MW
- `price`
  - 用于 2026 总运费口径

### 3. 派车任务导出

建议文件名：

- `2026_logistic_assign_task.xlsx`
- 或 `2026_logistic_assign_task.csv`

推荐格式：

- 优先 `xlsx`
- 备选 `csv (UTF-8)`

必需字段：

- `task_id`
- `ship_task_id`
- `status`

字段用途：

- `COUNT(assign_task.task_id)`
  - 用于 2026 车次统计
- `status`
  - 仅统计 `ENTER / LEAVE`

### 4. 派车明细导出

建议文件名：

- `2026_logistic_assign_detail.xlsx`
- 或 `2026_logistic_assign_detail.csv`

推荐格式：

- 优先 `xlsx`
- 备选 `csv (UTF-8)`

必需字段：

- `assign_task_id`
- `ship_task_id`
- `supplier_price`
- `extra_cost`

说明：

- 这份文件对当前锁定的 2026 总运费口径不是主必需项；
- 但如果后续还要复核基础运费或额外费用链路，建议一起提供。

---

## 五、建议提供的最小回补组合

如果只想最快解除 2026 主阻塞，最小需要：

1. `logistic_ship_task`
2. `logistic_ship_product`
3. `logistic_assign_task`

这三份足以先复核：

- 2026 发运量 MW
- 2026 车次
- 2026 总运费
- 2026 区域
- 2026 客户 / 项目
- 特殊业务口径

---

## 六、当前不建议的做法

- 不建议手工在主库直接补单字段值
- 不建议用样例 Excel 或 mock 数据冒充正式回补
- 不建议跳过 `pickup_date` 继续用 `biz_date` 代替 2026 业务时间口径
- 不建议跳过 `project_name` 解析总车数后改用其他口径近似代替

