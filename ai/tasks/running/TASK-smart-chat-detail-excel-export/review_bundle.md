# Review bundle: TASK-smart-chat-detail-excel-export

## Scope
- 智能助手回答中若存在 presentation.table 明细数据，前端明细卡提供“导出 Excel”按钮。
- 导出当前页面归一化后的明细列和行，生成 .xlsx 文件；空表给业务提示，不触发下载。
- 不修改后端查询、LLM/NLU、M3/M4 计算逻辑，也不引入任何 token/secret。

## Files under review
- frontend/src/views/business-chat/BusinessChatPage.vue
- tests/business_acceptance/test_plan_power_frontend_upload_entry.py

## Verification summary
- RED: test_business_chat_detail_table_can_export_excel_when_rows_exist 初始失败，缺少 xlsx import/导出按钮/导出函数。
- GREEN focused: tests/business_acceptance/test_plan_power_frontend_upload_entry.py => 13 passed。
- Full: PYTHONPATH=. python -m pytest tests -q --tb=short => 127 passed, 2 warnings。
- Frontend build: npm run build --prefix frontend => passed，只有既有 chunk size warning。
- Compile: python -m compileall tests/business_acceptance/test_plan_power_frontend_upload_entry.py => passed。
- Static scan: corrected added-lines scan => No findings。第一次全文件扫命中旧测试里的 token 禁用断言字符串，属于误报，已改为增量扫描。

## Notes for reviewer
- 当前工作区还保留上一轮 Plan BOM QA 修复未提交文件；本次 review 请聚焦上述两个文件和本任务验收材料。
- BusinessChatPage.vue 中既有 layout helper 变更来自上一轮验收，本次新增重点是 xlsx 导出按钮/函数/样式。
