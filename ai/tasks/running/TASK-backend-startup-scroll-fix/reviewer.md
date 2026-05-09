# TASK-backend-startup-scroll-fix Reviewer 记录

## Reviewer 结论

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": [],
  "suggestions": [
    "Document/enforce APP_ENV=prod in production deployment, since the temporary write guard intentionally allows non-prod/default-local environments until the formal user permission module is connected.",
    "Consider avoiding the small-screen margin-top override or using 100dvh/explicit parent sizing for the BOM scroll container so mobile/narrow viewports cannot clip the bottom of the internal scrollbar.",
    "deps.py also contains unrelated Plan BOM power QA service imports; ensure those companion service files are included with any commit/apply set if this scoped diff is applied independently."
  ],
  "summary": "Reviewed /tmp/startup_scroll_scope.diff plus the relevant current backend, frontend, API, schema, layout, and test files. Verified git diff --check for scoped files, targeted pytest coverage for startup warning/scroll/write guard (5 passed), frontend production build, scoped Python compilation, and explicit TestClient production overrides returning 403 for both power-model import and activation. The Pydantic protected namespace fix preserves model_sheet_count, run.py disables reload only when a debugger trace is attached, the BOM page now owns vertical scrolling under the app shell overflow constraints, and the production write guard blocks power-model writes without reintroducing legacy token/header handling. No blocking security concerns or logic errors found; no source files were modified by this review."
}
```

## 处理说明

- Reviewer 第一轮曾担心旧 token 移除后写接口无保护。
- 本轮未恢复旧 token；新增 `require_plan_power_write_access` 环境门禁：非生产环境保持本地/测试可用；`APP_ENV=prod` 时在正式用户权限模块接入前阻断功率模型导入和生效切换。
