# Postman 试运行调用说明

## 环境准备

建议在 Postman 中配置变量：

- `base_url`：`http://localhost:8000`

当前本地试运行默认不需要鉴权。不要在 Postman 集合中写真实 API Key。

## BOM Excel 上传

1. Method 选择 `POST`。
2. URL 填写 `{{base_url}}/api/v1/plan-bom/upload`。
3. Body 选择 `form-data`。
4. 增加字段：
   - `file`：类型切换为 `File`，选择 BOM Excel。
   - `business_type`：`plan_bom`
   - `source`：`trial_import`
   - `overwrite`：`true`
   - `remark`：按需填写，例如 `试运行上传`
5. 发送后查看 `data.success`、`parsed_orders_count`、`parsed_materials_count`、`warning_count`、`error_count`。

## BOM QA 接口

1. Method 选择 `POST`。
2. URL 填写 `{{base_url}}/api/v1/plan-bom/qa/ask`。
3. Body 选择 `raw` -> `JSON`。
4. 请求体示例：

```json
{"question":"订单00104的玻璃、间隙贴膜、焊带、汇流条、接线盒的规格描述？"}
```

## 物流 QA 接口

1. Method 选择 `POST`。
2. URL 填写 `{{base_url}}/api/v1/logistics/data-qa/query`。
3. Body 选择 `raw` -> `JSON`。
4. 请求体示例：

```json
{"question":"2026年1月份总发运量是多少MW？总共发了多少车次？"}
```

## 可直接复制的请求样例

### 1. 物流 A 类

```json
POST {{base_url}}/api/v1/logistics/data-qa/query
{"question":"2026年1月份总发运量是多少MW？总共发了多少车次？"}
```

### 2. 物流 B 类

```json
POST {{base_url}}/api/v1/logistics/data-qa/query
{"question":"最近物流成本是不是变高了？"}
```

### 3. 物流 C 类

```json
POST {{base_url}}/api/v1/logistics/data-qa/query
{"question":"预测下个月物流费用会是多少？"}
```

### 4. BOM 上传

```text
POST {{base_url}}/api/v1/plan-bom/upload
Body: form-data
file: 选择 File
business_type: plan_bom
source: trial_import
overwrite: true
remark: 试运行上传
```

### 5. BOM 单订单查询

```json
POST {{base_url}}/api/v1/plan-bom/qa/ask
{"question":"订单00104的玻璃、间隙贴膜、焊带、汇流条、接线盒的规格描述？"}
```

### 6. BOM 多订单对比

```json
POST {{base_url}}/api/v1/plan-bom/qa/ask
{"question":"订单00067和订单00106玻璃、间隙贴膜、焊带、汇流条、接线盒有什么不一样，并用表格统计出来。"}
```

### 7. BOM 指定材料查询

```json
POST {{base_url}}/api/v1/plan-bom/qa/ask
{"question":"哥伦比亚COEXITO-2026-00067，NT10/78GDF的线盒物料描述。"}
```

### 8. BOM B 类追问

```json
POST {{base_url}}/api/v1/plan-bom/qa/ask
{"question":"多个订单的玻璃、间隙贴膜、焊带、汇流条、接线盒规格并用 Excel 表格形式展现。"}
```

### 9. BOM C 类拒答

```json
POST {{base_url}}/api/v1/plan-bom/qa/ask
{"question":"使用功率预测来问询 BOM 配置的情况下需要什么样的电池可以满足订单需求功率。"}
```

### 10. BOM 非核心材料受控处理

```json
POST {{base_url}}/api/v1/plan-bom/qa/ask
{"question":"订单00104的电池片规格是什么？"}
```

## 结果判断

- `classification=A`：系统可直接回答。
- `classification=B`：系统需要你补充条件。
- `classification=C`：当前数据或规则无法支撑回答。
- HTTP 200 不代表一定是 A 类答案，必须查看 `classification` 和 `status.code`。
