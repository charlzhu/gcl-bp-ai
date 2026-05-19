# Final Acceptance - TASK-smart-chat-new-session-button

## 需求
把“新建会话”按钮移动到“智能问答”菜单后边，不再作为智能问答下方会话列表里的第一个二级菜单项。

## 根因
原布局把新建入口实现为 `<el-menu-item index="chat-new">`，位于 `智能问答` 子菜单内部、会话列表之前，因此视觉上像一个二级会话项，而不是跟随“智能问答”一级菜单标题的快捷按钮。

## 本轮修改
1. `frontend/src/layouts/AppLayout.vue`
   - 将 `data-testid="nav-new-chat"` 的入口从二级 `<el-menu-item>` 移入 `智能问答` 的 `#title` 区域。
   - 按钮文案调整为“新建会话”，显示在“智能问答”文字后边。
   - 使用 `@click.stop="createNewChatFromMenuTitle"`，避免点击新建按钮时触发子菜单折叠/展开。
   - 抽取 `createNewChatFromMenuTitle()`，复用原新建/聚焦空白会话并跳转 `/smart-chat` 的逻辑。
   - 新增按钮样式，保留蓝色辅助色并避免与展开箭头重叠。
2. `tests/business_acceptance/test_plan_power_frontend_upload_entry.py`
   - 新增静态契约测试，确保新建入口位于“智能问答”标题后、在会话列表前，并且不再是二级菜单项。

## TDD 记录
- RED：新增测试后先运行，按预期失败：找不到 `chat-title-new-button`。
- GREEN：完成布局与逻辑修改后，focused 测试通过。

## 验证结果
- `python -m pytest tests/business_acceptance/test_plan_power_frontend_upload_entry.py::test_app_layout_places_new_chat_button_after_smart_chat_title -q`：通过，1 passed。
- `python -m pytest tests/business_acceptance/test_plan_power_frontend_upload_entry.py -q`：通过，19 passed。
- `python -m pytest tests/business_acceptance/test_business_chat_session_lifecycle.py -q`：通过，1 passed。
- `python -m pytest tests/business_acceptance -q`：通过，186 passed，2 个 openpyxl xlsm 读取 warning，无失败。
- `npm run build`（frontend）：通过，包含 `vue-tsc -b` 和 `vite build`；仅保留 Vite chunk-size warning。
- 静态安全扫描：无发现。
- 浏览器 smoke：通过，页面左侧显示 `智能问答 新建会话`；按钮在“智能问答”文字后；点击按钮无 JS 错误，子菜单保持展开；DOM 检查 `buttonAfterText=true`、`overlapsArrow=false`。
- 独立 reviewer：通过，无阻塞安全或逻辑问题。

## 影响范围
- 仅影响智能问答侧边栏新建会话入口的位置和样式。
- 不影响 BOM / 物流后端业务逻辑。
- 保留 `data-testid="nav-new-chat"`，现有 E2E 选择器可继续点击该入口。

## 已知风险
当前仓库工作区存在较多本轮无关的历史/并行脏文件。本轮只修改并验证了上述两个文件，未处理无关改动。
