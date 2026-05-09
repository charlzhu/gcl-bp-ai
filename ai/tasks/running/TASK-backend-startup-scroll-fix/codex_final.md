# TASK-backend-startup-scroll-fix Codex Final

已完成后端启动提示和 BOM 数据管理页面滚动条问题修复。

## 完成内容

1. 修复 Pydantic `model_sheet_count` protected namespace warning。
2. 调试器附加时关闭 uvicorn reload，避免调试态多进程导致 `Connected to:` 重复提示；普通运行仍按 `APP_DEBUG` 控制 reload。
3. BOM 数据管理页新增内部垂直滚动容器，底部上传历史和功率模型版本历史可查看。
4. 补充功率模型写接口生产环境门禁：不恢复旧 token，`APP_ENV=prod` 时在正式用户权限模块接入前阻断导入/激活写操作。
5. 增加回归测试覆盖启动、Pydantic warning、页面滚动条和生产写门禁。

## 验证

- Focused：`5 passed in 1.50s`
- Related：`19 passed in 3.86s`
- Full：`71 passed, 2 warnings in 13.69s`
- `python -m compileall backend/run.py backend/app scripts`：通过
- `npm run build`：通过
- `git diff --check`：通过
- 静态扫描：无 secrets / shell injection / eval / pickle / SQL formatting 问题
- Reviewer：`passed=true`

## 备注

- openpyxl 的 2 个 warning 为既有 Excel 扩展/条件格式提示。
- IDE 自身单次 `Connected to:` 提示不能由后端完全关闭；本轮处理的是调试 + reload 导致的重复连接提示。
