# 试运行接口清单

## 基础说明

- 默认后端地址：`http://localhost:8000`
- API 前缀：`/api/v1`
- 当前本地试运行环境未启用登录鉴权；如后续接入网关或统一登录，需要由部署侧补充鉴权头。
- 不要在请求、文档或 Postman 中写入真实 API Key。

## 物流问答接口

- 方法：`POST`
- URL：`/api/v1/logistics/data-qa/query`
- Content-Type：`application/json`

请求参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| question | string | 是 | 自然语言物流问题 |

curl 示例：

```bash
curl -X POST "http://localhost:8000/api/v1/logistics/data-qa/query" \
  -H "Content-Type: application/json" \
  -d '{"question":"2026年1月份总发运量是多少MW？总共发了多少车次？"}'
```

成功响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "answer_summary": "按当前数据口径返回统计结果。",
    "status": {"code": "OK", "success": true},
    "query_plan": {"domain": "logistics", "intent": "aggregate"},
    "presentation": {"display_type": "table"}
  }
}
```

错误响应示例：

```json
{
  "code": 500,
  "message": "服务器内部错误",
  "data": null
}
```

## BOM 上传接口

- 方法：`POST`
- URL：`/api/v1/plan-bom/upload`
- 兼容旧地址：`/api/v1/plan-bom/import/excel`
- Content-Type：`multipart/form-data`

请求参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| file | File | 是 | BOM Excel 文件，支持 `.xls` / `.xlsx` / `.xlsm` |
| business_type | string | 否 | 默认 `plan_bom`，当前仅支持该值 |
| source | string | 否 | 上传来源，例如 `manual_upload` / `trial_import` |
| overwrite | boolean | 否 | 是否覆盖同文件实例，默认 `true` |
| remark | string | 否 | 备注 |

curl 示例：

```bash
curl -X POST "http://localhost:8000/api/v1/plan-bom/upload" \
  -F "file=@tmp/plan_bom/input/sample.xlsx" \
  -F "business_type=plan_bom" \
  -F "source=trial_import" \
  -F "overwrite=true" \
  -F "remark=试运行上传"
```

成功响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "success": true,
    "message": "BOM Excel 上传解析成功。",
    "import_batch_id": "plan-bom-20260427145003-3e3dc915",
    "file_name": "sample.xlsx",
    "file_size": 80896,
    "parsed_orders_count": 1,
    "parsed_materials_count": 144,
    "warning_count": 0,
    "error_count": 0,
    "data_quality_summary": {"persisted_business_data": true},
    "report_path": "tmp/plan_bom/import_reports/plan-bom-xxx.json",
    "next_action": "可以进入 /api/v1/plan-bom/qa/ask 查询。"
  }
}
```

错误响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "success": false,
    "message": "仅支持 .xls / .xlsx / .xlsm 格式的 BOM Excel 文件。",
    "error_count": 0,
    "next_action": "请上传有效的 BOM Excel 文件。"
  }
}
```

## BOM 问答接口

- 方法：`POST`
- URL：`/api/v1/plan-bom/qa/ask`
- Content-Type：`application/json`

请求参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| question | string | 是 | 自然语言 BOM 问题 |

curl 示例：

```bash
curl -X POST "http://localhost:8000/api/v1/plan-bom/qa/ask" \
  -H "Content-Type: application/json" \
  -d '{"question":"订单00104的玻璃、间隙贴膜、焊带、汇流条、接线盒的规格描述？"}'
```

成功响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "classification": "A",
    "status": {"code": "OK", "success": true},
    "answer_summary": "已按真实 BOM 数据返回关键材料规格。",
    "presentation": {"display_type": "table"}
  }
}
```

B 类追问响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "classification": "B",
    "status": {"code": "CLARIFICATION_REQUIRED", "success": false},
    "presentation": {"display_type": "clarification"}
  }
}
```

C 类拒答响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "classification": "C",
    "status": {"code": "UNSUPPORTED_QUESTION", "success": false},
    "presentation": {"display_type": "unsupported"}
  }
}
```

## Postman 调用方式

1. 物流/BOM 问答：选择 `POST`，Body 选择 `raw` 和 `JSON`。
2. BOM 上传：选择 `POST`，Body 选择 `form-data`，`file` 字段类型必须切换为 `File`。
3. 本地试运行默认不需要鉴权 Header。
4. 如果部署环境增加鉴权，由部署同事统一提供 Header，不要把真实密钥写入集合文件。

## 注意事项

- BOM 上传失败也会返回稳定结构，前端和 Postman 应查看 `data.success`。
- B/C 是业务边界，不是系统故障。
- 物流和 BOM 的 LLM 表达层不会替代数据查询结果。
