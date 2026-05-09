# TASK-plan-power-frontend-upload-entry Codex Final

## 用户问题

用户追问：

1. 功率模型管理 token 的作用是什么？
2. 用户怎么使用、填什么值？
3. 两个上传功能都需要显示上传进度，并且上传成功/上传失败都要能提示。

## Token 口径

后端代码确认：

- 配置项：`plan_power_admin_token`
- 请求头：`X-Plan-Power-Admin-Token`
- 保护接口：
  - `POST /plan-bom/power-model/import`
  - `POST /plan-bom/power-model/versions/{version_id}/activate`
- 作用：防止普通用户误导入或误激活功率模型版本，因为这些操作会影响后续功率预测结果。
- local/test 环境：如果后端没有配置 token，可以不填，便于本地联调。
- dev/prod 环境：必须由管理员在后端环境变量或 `.env` 配置同一个 token，前端输入同值才允许上传。
- 用户不能随便填写；真实值应由系统管理员线下告知或通过权限系统注入。
- 本轮没有输出、保存或生成任何真实 token。

## 本轮实现

### API

`frontend/src/api/planBom.ts`：

- `uploadPlanBomExcel()` 新增 `onUploadProgress` 回调。
- `uploadPlanPowerModel()` 新增 `onUploadProgress` 回调。
- 通过 Axios `onUploadProgress` 将浏览器上传进度转换为百分比。
- 请求真正完成后由页面置为 `100%`，避免 HTTP 响应处理阶段误判已完成。

### 页面

`frontend/src/views/plan-bom/BomDataManagementPage.vue`：

- 普通 BOM Excel 上传新增：
  - `bomUploadProgress`
  - 进度条 `<el-progress>`
  - `uploadSuccessMessage`
  - `uploadError`
- 功率模型上传新增：
  - `powerModelUploadProgress`
  - 进度条 `<el-progress>`
  - `powerModelUploadSuccessMessage`
  - `powerModelUploadError`
- 两个入口分别维护状态，避免串扰。
- 上传成功显示 success alert。
- 上传失败显示 error alert。
- 功率模型 token 仍不持久化、不日志输出、不展示真实值，请求结束后清空。

## TDD

新增/扩展：

`tests/business_acceptance/test_plan_power_frontend_upload_entry.py`

覆盖：

- 独立功率模型上传入口；
- API 独立封装；
- 进度条存在；
- BOM 与功率模型进度状态隔离；
- 成功/失败提示存在；
- token 不 reveal、请求后清空。

## 验证

详见 `test.log`。

关键结果：

- Focused：`3 passed`
- Related QA regression：`11 passed`
- Full tests：`60 passed, 2 warnings`
- Frontend build：通过
- compileall：通过
- diff check：通过
- static scan：0
- reviewer：`passed=true`

## 结论

上传进度和成功/失败提示已完成，reviewer 终审通过。
