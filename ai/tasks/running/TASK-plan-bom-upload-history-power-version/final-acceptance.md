# TASK-plan-bom-upload-history-power-version 最终验收

## 任务范围

本轮处理用户提出的补充需求：

1. 移除功率模型管理 token 输入与请求头。
2. BOM 数据管理页增加历史查看，可查看以往上传的 BOM 文件与功率模型文件。
3. 功率模型 `.xlsm` 支持版本列表与手动选择生效版本。
4. 最新成功上传的有效功率模型版本默认生效。
5. 两个上传入口继续独立，并保留上传进度与成功/失败提示。

## 重复上传同文件的结论

- 功率模型 `.xlsm`：不会重复创建模型版本。后端按文件 SHA256 `file_hash` 查重；同 hash 已存在时返回 `existing`，不会再插入一套 `plan_power_*` 模型数据。若业务重复上传同一个有效文件，该已有版本会被重新设为 active；若已有版本解析失败，则保留历史但不会覆盖当前 active 版本。
- BOM Excel：会新增一条上传批次历史用于审计追踪，但不会让同一业务版本的 BOM 明细无限叠加。导入保存前会按 `order_identity_key + file_instance_key + version_no + source_type` 删除旧的 BOM header/material/revision，再写入本批次解析结果。因此“上传历史”会记录两次上传，业务查询使用的 BOM 版本数据不会因同文件重复上传而重复累加。

## 后端改动

- 删除旧临时管理 token：
  - `plan_power_admin_token`
  - `require_plan_power_admin`
  - `X-Plan-Power-Admin-Token` 依赖
- 新增 BOM 上传历史：
  - `GET /api/v1/plan-bom/upload/history`
- 功率模型导入逻辑：
  - 新有效版本导入后默认 active。
  - 重复上传同 hash 文件不新增版本，但可重新 active 该已有版本。
  - 解析失败版本保留历史，不会设为 active。
- 功率模型版本激活继续由后端保证最多一个 active 版本，失败版本不允许激活。

## 前端改动

- `BOM 数据管理` 页面：
  - 移除功率模型管理 Token 输入框与相关状态。
  - BOM Excel 上传与功率模型 xlsm 上传保持独立。
  - 两个上传入口均有独立进度条、成功提示、失败提示。
  - 新增 BOM 上传历史表。
  - 新增功率模型版本历史表。
  - 显示当前 active 功率模型版本。
  - 支持点击“设为生效”手动切换功率模型版本。
- 修复 reviewer 阻塞：
  - `ApiResponse(code != 0)` 不再被误判成功。
  - `data=null` 不再被误判成功。
  - `parse_status=failed` / `error_count>0` 不再提示功率模型上传成功。
  - 激活失败不再提示“已设为当前生效”。
  - 解析状态展示 `parse_status`，不再混用 `import_status`。

## 测试结果

- Focused：`26 passed in 6.56s`
- Full：`66 passed, 2 warnings in 14.11s`
- Python compile：通过
- Frontend build：通过
- Diff check：通过
- Static scan：无 hardcoded secrets / shell injection / eval / pickle / SQL string formatting 发现
- Reviewer：`passed=true`

## 修改文件

- `backend/app/api/deps.py`
- `backend/app/core/config.py`
- `backend/app/domains/plan_bom/api/endpoints/import_excel.py`
- `backend/app/domains/plan_bom/api/endpoints/power_model.py`
- `backend/app/domains/plan_bom/repositories/import_repository.py`
- `backend/app/domains/plan_bom/schemas/import_excel.py`
- `backend/app/domains/plan_bom/services/excel_import_service.py`
- `backend/app/domains/plan_bom/services/power_model_service.py`
- `frontend/src/api/planBom.ts`
- `frontend/src/views/plan-bom/BomDataManagementPage.vue`
- `tests/business_acceptance/test_plan_bom_upload_history_power_activation.py`
- `tests/business_acceptance/test_plan_power_frontend_upload_entry.py`
- `tests/business_acceptance/test_plan_power_m2_model_versioning.py`

## 是否影响既有 BOM / 物流能力

- BOM：新增历史接口和页面展示；重复上传同业务版本仍覆盖旧业务数据，不做累加。既有 BOM 查询链路不改变。
- 功率预测：只调整模型版本管理与 active 选择；不改变 M3 计算引擎、M4 配置映射、M5 QA 数值计算逻辑。
- 物流：未修改物流域代码。

## 风险与后续建议

- 本轮按用户要求移除临时 token，当前上传/激活权限后续应由正式用户与权限模块接管。
- reviewer 的非阻塞建议：后续可进一步细化失败解析版本的结果卡文案，以及在 ApiResponse helper 中对 malformed success envelope 做更严格处理。
- 未自动合并 main、未提交、未部署生产；合并和上线仍需用户确认。
