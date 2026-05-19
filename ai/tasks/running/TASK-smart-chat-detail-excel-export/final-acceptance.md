# TASK-smart-chat-detail-excel-export 最终验收报告

## 1. 需求

智能助手回答的大内容中，如果存在明细数据，业务用户需要能够直接导出 Excel。

## 2. 实现范围

本轮只做前端展示层增强：

- 当助手回复中存在 `presentation.table` 且包含有效列/行时，在“明细数据”卡片右上角展示“导出 Excel”按钮。
- 点击后导出当前页面已归一化展示的明细数据为 `.xlsx` 文件。
- 空表或异常结构不触发下载，给出业务提示。
- 不修改后端查询、LLM/NLU、M3/M4 功率计算、BOM/物流业务数据口径。

## 3. 修改文件

```text
frontend/src/views/business-chat/BusinessChatPage.vue
tests/business_acceptance/test_plan_power_frontend_upload_entry.py
```

验收材料：

```text
ai/tasks/running/TASK-smart-chat-detail-excel-export/test.log
ai/tasks/running/TASK-smart-chat-detail-excel-export/diff.patch
ai/tasks/running/TASK-smart-chat-detail-excel-export/review_bundle.md
ai/tasks/running/TASK-smart-chat-detail-excel-export/review.md
ai/tasks/running/TASK-smart-chat-detail-excel-export/final-acceptance.md
```

## 4. TDD 过程

### RED

新增验收测试：

```text
tests/business_acceptance/test_plan_power_frontend_upload_entry.py::test_business_chat_detail_table_can_export_excel_when_rows_exist
```

初始结果：

```text
FAILED ... assert "import * as XLSX from 'xlsx'" in chat
1 failed
```

证明当前智能助手明细表尚未具备 Excel 导出入口和导出函数。

### GREEN

实现后结果：

```text
1 passed
```

随后 focused 文件级回归：

```text
13 passed
```

## 5. 关键实现

### 5.1 明细表导出按钮

在 `BusinessChatPage.vue` 的明细表卡片头部新增：

```text
导出 Excel
```

仅在 `shouldShowResultTable(message)` 为真时展示，即后端返回有效 table columns/rows。

### 5.2 Excel 导出函数

新增：

```text
exportAssistantTableToExcel
buildAssistantTableExportRows
buildAssistantTableExportFileName
sanitizeAssistantTableExportFileName
formatAssistantTableExportTimestamp
normalizeAssistantTableExportCell
```

导出逻辑：

1. 从 `message.presentation.table` 读取当前页面展示表格。
2. 用 `table.columns` 保持列顺序。
3. 用 `table.rows` 生成导出行。
4. 对对象/数组/null 做安全归一，避免 `[object Object]`。
5. 使用 `XLSX.utils.json_to_sheet` 生成 worksheet。
6. 使用 `XLSX.writeFile` 触发 `.xlsx` 下载。

### 5.3 文件名

文件名基于回答标题或业务域生成，并清理：

```text
\ / : * ? " < > | 换行 tab
```

同时追加时间戳，避免重复导出覆盖。

### 5.4 空数据保护

如果当前回答没有可导出的明细数据：

```text
ElMessage.warning('当前回答没有可导出的明细数据')
```

不触发下载。

## 6. 验证结果

本轮执行：

```text
focused frontend acceptance:
13 passed

full tests:
127 passed, 2 warnings

python compileall:
passed

frontend build:
passed

static scan:
No findings in added lines of focused task diff.

reviewer:
passed=true
```

Reviewer 另行复跑结果：

```text
focused frontend acceptance: 13 passed
frontend build: passed
full tests: 130 passed, 2 warnings
git diff --check: 无输出
```

说明：`openpyxl` 的 2 个 warning 为既有 xlsm/条件格式读取提示，不是本轮新增失败。`vite` chunk size warning 为既有前端构建体积提示，不影响构建通过。

## 7. 安全与边界

- 未新增后端接口。
- 未修改 BOM/物流查询逻辑。
- 未修改 LLM/NLU/M3/M4。
- 未新增 token、secret、password、API key、connection string。
- 未恢复废弃的 `X-Plan-Power-Admin-Token` / `plan_power_admin_token` / `require_plan_power_admin`。
- 导出数据仅来自当前助手回复中已经展示给用户的 `presentation.table`，不导出隐藏 raw response 或内部字段。

## 8. Reviewer 结论

```text
passed=true
阻塞问题：无
```

非阻塞建议：

1. 后续可补前端组件/单元测试，stub `XLSX.writeFile` 与 `ElMessage`。
2. 后续可把 Excel 导出 helper 抽成独立 util，并按需动态 import `xlsx`，降低初始 chunk。
3. 可在 `XLSX.writeFile` 外增加 try/catch，下载失败时给 `ElMessage.error`。

## 9. 当前结论

本轮“智能助手明细数据导出 Excel”功能已完成，并通过 focused/full/build/static scan/reviewer 验收。
