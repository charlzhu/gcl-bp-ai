# PLAN_BOM_UPLOAD_API

## 接口地址

- 新接口：`POST /api/v1/plan-bom/upload`
- 兼容旧接口：`POST /api/v1/plan-bom/import/excel`

## 请求方式

`multipart/form-data`

## 请求参数

- `file`：必填，支持 `.xls`、`.xlsx`、`.xlsm`。
- `business_type`：可选，默认 `plan_bom`。
- `source`：可选，例如 `manual_upload` / `trial_import`。
- `overwrite`：可选，默认 `true`，当前复用导入仓储的同文件实例覆盖策略。
- `remark`：可选，作为报告摘要回传。

## 返回字段

- `success`
- `message`
- `import_batch_id`
- `file_name`
- `file_size`
- `parsed_orders_count`
- `parsed_materials_count`
- `warning_count`
- `error_count`
- `data_quality_summary`
- `report_path`
- `next_action`
- `errors`
- `warnings`

## 调用示例

```bash
curl -F "file=@BOM.xls" \
  -F "business_type=plan_bom" \
  -F "source=manual_upload" \
  -F "overwrite=true" \
  http://127.0.0.1:8000/api/v1/plan-bom/upload
```

## 验收结果

已执行 `scripts/plan_bom_upload_api_check.py`，报告输出：

- `tmp/plan_bom/plan_bom_upload_api_check_report.json`

该脚本使用 FastAPI `TestClient` 真实请求 multipart 接口，不再直接调用 endpoint 函数。

覆盖结果：

- `/api/v1/plan-bom/upload` 路由真实注册。
- `/api/v1/plan-bom/import/excel` 兼容旧接口真实注册。
- 使用真实 BOM Excel 文件上传成功。
- 成功响应字段 `success/message/import_batch_id/file_name/file_size/parsed_orders_count/parsed_materials_count/warning_count/error_count/data_quality_summary/report_path/next_action` 齐全。
- 已覆盖错误场景：非 Excel、空文件、超大文件、错误 `business_type`、破损 `.xlsx` 解析失败。
- 破损 `.xlsx` 不再抛出 500，而是返回可理解的失败 payload。
