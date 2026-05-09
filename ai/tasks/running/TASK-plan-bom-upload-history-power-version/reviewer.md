# TASK-plan-bom-upload-history-power-version Reviewer 记录

## 第一轮 reviewer

结论：`passed=false`

阻塞问题：

1. 功率模型上传失败包 `ApiResponse(code != 0, data=null)` 可能被前端误提示为成功。
2. 解析失败的功率模型版本可能被前端误提示为成功导入。
3. 激活失败包可能被前端误提示为“已设为当前生效”。

修复：

- `unwrapResponseData()` 增加 `code !== 0`、`success === false`、`data === null` 失败处理。
- `isPowerModelImportFailed()` 检查 `version.parse_status === 'failed'` 与 `version.error_count`。
- 激活版本后用 `unwrapResponseData()` 确认后端返回成功数据后才展示成功提示。
- UI 中“解析状态”改为展示 `version.parse_status`，不再把 `import_status(created/existing)` 当解析状态。
- Issue 数改为展示 `detail.issues.length` 或 `version.error_count`。

## 第二轮 reviewer

结论：`passed=true`

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": [],
  "suggestions": [
    "Consider clearing stale power-model success message at the start of activation attempts and validating returned activation payload has is_active=true and parse_status!='failed'.",
    "Consider making unwrapResponseData fail on missing/undefined data for known ApiResponse envelopes.",
    "Consider tailoring failed-parse result card text/next-action to the failed state."
  ],
  "summary": "Reviewed scoped backend/frontend source. Token dependency/header/config/UI removed; BOM upload history and power-model version history/activation controls added; failed parsed versions remain history but are not active; upload state/progress/prompts remain separated; frontend handles nonzero ApiResponse envelopes, data:null, parser-failed objects, and activation rejections."
}
```

Reviewer 建议为非阻塞项，本轮未发现安全问题或逻辑阻塞。
