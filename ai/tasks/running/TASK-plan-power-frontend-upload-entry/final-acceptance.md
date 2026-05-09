# TASK-plan-power-frontend-upload-entry Final Acceptance

## 结论

PASS。

本轮在已补齐独立“上传功率模型”入口基础上，继续完成：

1. 明确功率模型管理 token 的业务/安全口径；
2. 普通 BOM Excel 上传显示上传进度；
3. 功率模型 xlsm 上传显示上传进度；
4. 两个上传入口均显示上传成功提示；
5. 两个上传入口均显示上传失败提示；
6. reviewer 终审通过。

## 功率模型管理 token 说明

### 作用

功率模型管理 token 是后端管理写接口的保护令牌，用来限制谁可以执行会影响功率预测模型版本的操作。

当前保护：

```text
POST /plan-bom/power-model/import
POST /plan-bom/power-model/versions/{version_id}/activate
```

导入/激活功率模型会改变后续功率预测、供应商推荐、模型追溯的基础版本，因此不能让普通业务用户误操作。

### 用户怎么使用

在 `BOM 数据管理 -> 上传功率模型` 卡片中：

- 选择 GCL 功率测试基准 `.xlsm` 文件；
- 如后端要求 token，则在“功率模型管理 Token”输入框填入管理员提供的 token；
- 点击“上传功率模型”。

前端会把该值放到请求头：

```text
X-Plan-Power-Admin-Token: [REDACTED]
```

### 填什么值

- local/test 环境：如果后端没有配置 `plan_power_admin_token`，可以不填。
- dev/prod 环境：必须填写后端环境变量或 `.env` 中配置的 `plan_power_admin_token` 对应值。
- 这个值应由系统管理员提供，用户不能自己随便填。
- 本验收材料不记录、不输出任何真实 token。

### 安全处理

- token 不存 localStorage/sessionStorage；
- token 不 console 输出；
- token 不显示明文 reveal；
- 请求完成后清空；
- 仅作为本次请求头透传。

## 修改文件

```text
frontend/src/api/planBom.ts
frontend/src/views/plan-bom/BomDataManagementPage.vue
tests/business_acceptance/test_plan_power_frontend_upload_entry.py
ai/tasks/running/TASK-plan-power-frontend-upload-entry/diff.patch
ai/tasks/running/TASK-plan-power-frontend-upload-entry/static_scan.txt
ai/tasks/running/TASK-plan-power-frontend-upload-entry/test.log
ai/tasks/running/TASK-plan-power-frontend-upload-entry/codex_final.md
ai/tasks/running/TASK-plan-power-frontend-upload-entry/final-acceptance.md
```

## 上传体验

### 上传 BOM Excel

- 显示 `BOM 上传进度：xx%`；
- 显示 `<el-progress>`；
- 成功显示 success alert；
- 失败显示 error alert；
- 上传完成后保留原解析结果卡片。

### 上传功率模型

- 显示 `功率模型上传进度：xx%`；
- 显示 `<el-progress>`；
- 成功显示 success alert；
- 失败显示 error alert；
- 上传完成后保留版本/解析状态/SHEET/Issue 摘要卡片。

## 测试结果

```text
RED: 3 failed，证明缺少进度条、独立状态、成功提示、API onUploadProgress
GREEN focused: 3 passed in 0.00s
Related QA regression: 11 passed in 2.09s
Full tests: 60 passed, 2 warnings in 11.66s
Frontend build: passed
compileall: passed
diff check: passed
static scan: static_findings=0
reviewer final: passed=true
```

## Reviewer 终审

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": [],
  "suggestions": [],
  "summary": "BOM Excel and power model uploads have separate progress state, visible progress bars, and visible success/error alerts. API wrappers use Axios onUploadProgress and only send files via FormData without frontend parsing. Power model admin token is sent only as X-Plan-Power-Admin-Token, is not persisted/logged/displayed, and is cleared in finally after the request. No frontend Excel macro execution/calculation/activation or hardcoded secret was found."
}
```

## 是否影响现有能力

- 不改后端接口。
- 不改数据库。
- 不改 M5 QA 计算链路。
- 不影响物流能力。
- 前端 build 通过。

## 下一步

等待用户确认是否进入提交/打包/合并准备；合并和部署仍需人工确认。
