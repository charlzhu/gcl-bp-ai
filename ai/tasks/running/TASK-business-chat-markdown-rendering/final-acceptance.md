# TASK-business-chat-markdown-rendering 最终验收报告

## 1. 任务目标

修复智能问答前端对后端 Markdown 答案渲染不佳的问题。后端返回的内容包含 `**加粗**`、空行段落、`-` 列表等 Markdown 标记，前端应渲染为生产级业务正文，而不是原样展示 Markdown 符号。

## 2. 根因

`BusinessChatPage.vue` 此前使用 Vue 文本插值直接展示：

```vue
{{ message.presentation.answer }}
```

文本插值会转义并原样显示 Markdown，因此截图中的 `**供应商**`、`- 列表` 不会变成加粗和列表。

## 3. 本轮改动

### 新增安全 Markdown 渲染工具

文件：

```text
frontend/src/utils/businessMarkdown.ts
```

能力：

1. 支持业务答案常用 Markdown：
   - 段落；
   - 空行分段；
   - `**加粗**` / `__加粗__`；
   - `-` / `*` 无序列表；
   - `1.` / `1)` 有序列表；
   - `###` / `####` 标题；
   - 行内代码。
2. 所有原始文本先做 HTML 转义，再转换受控 Markdown 标签。
3. 不支持原始 HTML、图片、链接、复杂表格等高风险能力。
4. 结构化业务表格仍由后端确定性 payload 和前端表格组件展示，不走 Markdown。

### 智能问答页面接入

文件：

```text
frontend/src/views/business-chat/BusinessChatPage.vue
```

改动：

1. 助手流式内容 `message.content` 使用 `renderBusinessMarkdown` 渲染；
2. 最终答案 `message.presentation.answer` 使用 `renderBusinessMarkdown` 渲染；
3. 用户消息仍然使用 `{{ message.content }}` 纯文本插值，不做 Markdown 渲染；
4. 新增 `.assistant-markdown` 样式，使段落、加粗、列表、代码在企业后台风格中更清晰；
5. 流式光标改为挂在最后一个段落/列表项后，避免 markdown block 渲染后光标位置生硬。

### 新增验收测试

文件：

```text
tests/business_acceptance/test_business_chat_markdown_rendering.py
```

覆盖：

1. Markdown 中的 `**加粗**` 正确渲染为 `<strong>`；
2. `-` 列表正确渲染为 `<ul><li>`；
3. 原始 `<script>` 被转义，不会执行；
4. 页面模板中助手答案走 `v-html="renderBusinessMarkdown(...)"`；
5. 用户消息仍保留 Vue 文本插值。

## 4. 验证结果

### RED

```text
2 failed
```

确认原问题存在：工具文件不存在，页面未接入 markdown 渲染。

### GREEN

```text
2 passed in 0.24s
```

### Focused 智能问答回归

```text
9 passed in 1.59s
```

### 前端构建

```text
npm run build
```

通过。仅有既有 Vite chunk size warning。

### 全量业务验收

```text
161 passed, 2 warnings in 22.39s
```

warnings 为 openpyxl 读取 xlsm 扩展/条件格式的既有提示。

### 浏览器验证

已通过 `/smart-chat` 页面验证：

1. 后端 mock 返回截图同类 Markdown；
2. 页面不再显示 `**`；
3. `<strong>` 数量正常；
4. `<li>` 列表正常；
5. 未渲染 `<script>`；
6. 无横向溢出；
7. console 无 JS error。

### 安全扫描

```text
markdown rendering focused security scan ok
```

未发现硬编码密钥或废弃功率管理 token 回归。

## 5. Reviewer 结论

```text
PASS
```

阻塞问题：none。

## 6. 风险与后续建议

当前实现是“受控轻量 Markdown”，覆盖业务答案正文的高频格式。后续如果确实需要完整 Markdown 能力，例如表格、链接、引用块，可再引入成熟 Markdown parser + sanitizer，但本轮不建议直接开放完整 Markdown/HTML，以免增加 XSS 风险和展示不可控性。

## 7. 是否影响现有 BOM / 物流能力

不影响业务查询、计算、表格事实和后端接口；本轮只改变助手答案正文的前端展示方式。
