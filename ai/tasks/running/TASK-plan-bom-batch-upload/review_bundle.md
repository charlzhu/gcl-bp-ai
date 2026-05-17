# TASK-plan-bom-batch-upload Review Bundle

## Scope

- `backend/app/domains/plan_bom/api/endpoints/import_excel.py`
- `frontend/src/api/planBom.ts`
- `frontend/src/views/plan-bom/BomDataManagementPage.vue`
- `frontend/src/views/plan-bom/PlanBomDetailQueryPage.vue`
- `tests/business_acceptance/test_plan_bom_batch_upload_endpoint.py`
- `tests/business_acceptance/test_plan_power_frontend_upload_entry.py`

## Requirement

上传 BOM Excel 需要支持批量上传。

## Intended behavior

1. `/plan-bom/upload` 继续兼容旧 `file` 单文件字段。
2. 新增 `files` 多文件字段；后端逐文件校验、逐文件调用真实 BOM Excel 导入服务。
3. 批量中单个文件失败不阻断其它合法文件入库。
4. 批量响应返回 `total_files`、`success_count`、`failed_count`、汇总解析数量和逐文件 `items`。
5. BOM 数据管理页支持多选上传，并展示逐文件结果。
6. BOM 明细/问答页的快捷上传入口也支持多选上传。
7. 前端不解析 Excel 内容，事实解析仍完全由后端确定性导入服务完成。

## Test summary

- RED front contract: `1 failed`，原页面 input 缺少 `multiple`。
- RED backend endpoint: `2 failed`，原 endpoint 不接受 `files` 参数。
- GREEN focused: `3 passed`。
- Related tests: `20 passed`。
- Full tests: `138 passed, 2 warnings`。
- Frontend build: `vue-tsc -b && vite build` passed，保留既有 chunk size warning。
- Compileall: passed。
- Diff whitespace check: passed。
- Static/secret scan: no credential/secret/token findings。

## Review questions

1. 批量接口是否保持旧单文件上传兼容性？
2. 批量中单个无效文件是否不会阻断其它文件？
3. 前端是否只负责上传与展示，不在浏览器解析 BOM Excel？
4. 响应结构是否足够业务用户理解总结果与逐文件结果？
5. 是否存在 token/secret/权限回退风险？
