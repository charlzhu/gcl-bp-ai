# AI Answer Experience V2 实施报告

## 目标

把当前智能助手的一问一答体验升级为“AI Answer Experience V2”：

1. 后端确定性查询结果仍是唯一事实来源。
2. LLM 只做表达优化，不改事实、数字、状态和结构化数据。
3. 普通问题默认以自然语言叙事回答为主。
4. 表格、指标卡、图表、明细、导出改为按意图或用户点击展示。
5. 口径和风险提示分级，普通口径默认折叠。
6. 保留结构化数据用于审计、导出、回溯。

## 修改文件

### backend/app/services/business_answer_stream_service.py

- 新增流式 LLM 文本安全校验。
- 在流式输出前校验：
  - 是否新增确定性结果之外的数字；
  - 是否暴露 SQL、query_key、planner、guardrail、数仓表名、内部字段等技术信息。
- 校验失败时降级为确定性答案。
- `apply_streamed_answer()` 深拷贝确定性 payload，仅允许写入 `presentation.answer` 和 `presentation.debug` 中的 stream 来源/降级原因。
- 不允许 stream 结果改 status、result_table、table_spec、cards、chart_spec 等结构化事实。

### backend/app/domains/logistics/services/llm_answer_presentation_service.py

- 普通 OK 查询默认 `display_type = narrative`。
- 只有用户明确要求表格/指标卡/图表时才返回 `table` / `summary_cards` / `chart`。
- 对 LLM presentation payload 做 display_type、数字、技术字段泄露校验。
- 新增 `caveat_items`，将口径和风险提示分为 `info` / `warning` / `danger`。
- 避免“异常值归入其他”这类普通口径兜底被误判为 danger。
- 补充 debug：presentation source、requested display、final display type、fallback reason、model name 等。

### backend/app/domains/logistics/schemas/data_qa.py

- presentation schema 增加 `caveat_items` 等兼容字段，保留旧 `caveats`。

### frontend/src/api/logistics.ts / frontend/src/api/planBom.ts

- 补充前端 API 类型字段，兼容后端返回的分级 caveat_items。

### frontend/src/views/business-chat/BusinessChatPage.vue

- 以 `presentation.answer` 为主回答，不再在 done 后强行回到固定报表面板。
- narrative 默认不展示指标卡、明细表、图表。
- 结构化数据改为二级操作：
  - 查看数据依据
  - 展开明细 / 收起明细
  - 导出 Excel
- `数据口径` 默认折叠。
- `warning` 级风险轻量展示，`danger` 级才突出展示。
- 加入流式阶段感：正在理解问题 / 正在查询数据 / 正在组织回答 / 正在生成回答。
- 兼容旧 payload：`caveatItems` 缺失时回落到旧 `caveats`。

### frontend/src/utils/businessChatSessions.ts

- 会话持久化不再丢弃审计明细所需的 `result_table`。
- 也不再保存完整 `rawResponse`，只白名单保留：
  - `rawResponse.result_table.columns`
  - `rawResponse.result_table.rows`
- presentation 持久化改为白名单字段，递归剔除 `debug`、trace、planner、guardrail、sql 等内部信息。
- 解决“展开明细 / 导出 Excel”按钮在 narrative 回答中 disabled 的问题，同时避免内部字段进入浏览器历史。

### tests/business_acceptance/test_business_chat_answer_format_preference.py

新增/更新测试覆盖：

- 普通物流问题默认 narrative。
- 没有明确要求时不显示 cards/table/chart。
- 明确要求表格/指标卡/图表时才返回对应 display。
- stream LLM 新增非法数字自动降级。
- stream LLM 暴露 SQL/query_key/planner/数仓表名自动降级。
- 前端不固定渲染所有模块。
- caveat 分级和流式阶段文案。
- 会话持久化只保留安全 result_table。
- 旧 payload 缺失 caveatItems 不报错。

## 自动修复记录

1. 浏览器 E2E 发现 `展开明细` / `导出 Excel` disabled。
   - 根因：会话归一化时固定 `rawResponse: null`，导致 result_table 丢失。
   - 修复：只白名单持久化安全 result_table。

2. Codex review 发现 `presentation.debug` 可能被持久化。
   - 根因：会话历史保存 presentation 时未做白名单归一化。
   - 修复：新增 `normalizeMessagePresentation()`，只保留展示字段并剔除内部字段。

3. Codex review 发现旧 payload 缺失 `caveatItems` 时可能读取 `.length` 报错。
   - 根因：前端兼容逻辑假设 `presentation.caveatItems` 必定存在。
   - 修复：使用 `Array.isArray()` 防御，并回落到旧 `caveats`。

## 非目标范围

本次未修改：

- 物流确定性查询口径。
- 物流/BOM 数据计算结果。
- 数据库结构或生产数据。
- 生产配置、密钥、部署流程。
- main 分支合并或 commit/push。
