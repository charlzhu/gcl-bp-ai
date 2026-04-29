# 需求任务卡

## 1. 需求目标

需求编号：`REQ-20260429-001`

优化物流 data-qa 查询失败时 `/smart-chat` 页面里的前端错误提示，让业务用户能理解“发生了什么、能否重试、是否需要把追踪编号交给技术同事”。

本需求只处理失败态展示体验：

- 物流 data-qa 接口请求失败时，消息区展示业务化中文错误。
- 错误提示不得直接暴露 `Request failed with status code xxx`、`AxiosError`、SQL、表名、堆栈、文件路径等技术细节。
- 正常 A 类成功、B 类追问、C 类拒答、空结果展示链路不改变。
- 不改变后端查询逻辑、不改变 A/B/C 分类规则。

## 2. 不做范围

- 不重构后端 `LogisticsDataQaService`、planner、repository、presentation。
- 不修改数据库结构、不新增表、不改查询日志表结构。
- 不扩展 RAG、不新增 Agent 工作流。
- 不处理历史 903 题库，不迁移 B/C 到 A。
- 不改物流业务口径，不引入新 query_key。
- 不做全站 HTTP 错误治理，本次优先收口 `/smart-chat` 中物流 data-qa 的错误消息区展示。
- 不把仓库维度作为一期可靠统计维度。
- 不把 fallback 结果包装成正式业务结论。

## 3. 当前项目事实判断

技术主管当前工作分支已确认是 `agent/bp-main`。

当前工作区不是干净状态，存在已修改/已暂存混合状态，开发和测试 Codex 必须避免误提交非本需求文件。

当前仓库已确认事实：

- 前端真实入口 `/smart-chat` 指向 `frontend/src/views/business-chat/BusinessChatPage.vue`。
- `/logistics/data-qa` 当前路由重定向到 `/smart-chat`。
- 物流 data-qa 前端请求函数为 `fetchLogisticsDataQaQuery`，调用 `/logistics/data-qa/query`。
- `/smart-chat` 当前失败路径在 `catch` 中直接使用 `error.message`，容易展示 Axios 技术错误。
- `frontend/src/utils/http.ts` 当前拦截器会弹出后端 `message/detail/error.message`。
- 后端 data-qa endpoint 异常时已调用 `service.write_error_log(...)` 记录错误日志，然后继续抛出异常。
- 后端全局异常处理当前 500 返回结构包含 `code=5000`、`message="服务内部异常"`、`trace_id`。

当前未完成能力判断：

- `/smart-chat` 失败消息没有业务化分层。
- 当前前端没有专门的物流 data-qa 友好错误消息构造函数。
- 当前错误气泡没有稳定保证隐藏 Axios/HTTP 技术字符串。
- 没有看到前端单测目录；该任务主要依赖 `npm run build` 和浏览器/E2E 验证。

本次任务与当前仓库状态一致：需求是前端失败态展示优化，当前问题点集中在 `/smart-chat` 的失败分支，不需要改后端业务查询逻辑。

## 4. 影响模块

主要影响：

- `frontend/src/views/business-chat/BusinessChatPage.vue`

可能只读参考：

- `frontend/src/api/logistics.ts`
- `frontend/src/utils/http.ts`
- `backend/app/domains/logistics/api/endpoints/data_qa.py`
- `backend/app/core/exception_handlers.py`
- `scripts/trial_sample_frontend_e2e_eval.py`

不应影响：

- 后端 data-qa 查询主链路
- 物流 A/B/C 分类
- BOM 问答正常展示
- 结构化查询页
- 查询历史接口和日志结构

## 5. 后端修改点

原则上无后端修改。

全栈开发 Codex 不得修改：

- `LogisticsDataQaService`
- `LogisticsDataQaPlanner`
- `LogisticsDataQaRepository`
- A/B/C 分类规则
- 查询日志写入结构
- 全局异常处理语义

只允许把后端现有错误响应作为前端输入来消费：

- HTTP 状态码
- `response.data.code`
- `response.data.message`
- `response.data.trace_id`

如果发现后端错误没有 `trace_id`，本任务不修后端，只在风险中记录。

## 6. 前端修改点

本次全栈开发只允许修改本需求相关文件，优先只改：

- `frontend/src/views/business-chat/BusinessChatPage.vue`

建议在该文件内做局部增量修改：

- 新增本地错误消息构造函数，例如 `buildBusinessChatErrorMessage(error, domain)`。
- 该函数负责从 Axios 错误中提取：
  - HTTP 状态码
  - 后端 `code`
  - 后端 `message`
  - 后端 `trace_id`
  - 是否为网络断连或超时
- 对物流 data-qa 失败做业务化提示。
- 如果后端返回 `trace_id`，在错误提示末尾附加 `追踪编号：xxx`。
- 对错误文本做安全过滤，不展示：
  - `Request failed`
  - `AxiosError`
  - `Network Error`
  - SQL
  - 表名
  - Python/JS 文件路径
  - 堆栈
- 修改 `catch` 分支，调用该函数后再传给 `failAssistantMessage`。
- 不改 `adaptLogisticsResult`，不改成功态展示。
- 不改 `inferDomain`，避免影响物流/BOM 路由识别。
- 不改 `/smart-chat` 的正常问答视觉结构，只替换失败态文案。

## 7. 测试验证点

全栈开发 Codex 至少执行：

- `cd frontend && npm run build`

建议用浏览器或 Playwright 做失败态验证：

- 打开 `/smart-chat`
- 选择“物流数据”
- 模拟 `/api/v1/logistics/data-qa/query` 返回 500，响应包含 `trace_id`
- 发送物流问题
- 验证最后一条助手消息：
  - `data-status="error"`
  - 存在 `data-testid="message-error"`
  - 展示业务化中文错误
  - 包含 trace_id
  - 不包含 `Request failed`、`AxiosError`、`SQL`、堆栈或文件路径

正常链路回归：

- 物流 A 类成功问题仍展示 `assistant-result`
- 物流 B 类追问仍展示“需要补充”
- 物流 C 类拒答仍展示“可改问方向”
- BOM 正常问答不受影响
- 自动识别域逻辑不回退

## 8. 风险点

- 当前主工作区已有多项非本任务改动，开发 Codex 必须只处理本需求相关文件。
- `frontend/src/utils/http.ts` 当前仍会弹出全局 `ElMessage.error`，本任务若只改 `/smart-chat` 消息气泡，可能仍出现短暂全局 toast；本轮不做全站错误治理。
- 如果开发 Codex 选择修改全局 HTTP 拦截器，会影响 BOM、上传、历史页等其他页面，必须扩大测试范围；技术主管建议不要这样做。
- 错误提示不能承诺“数据已保存”或“结果正确”，只能说明请求失败和 trace 可用于排查。
- 不得把后端 500 误包装成 B/C 业务状态。
- 不得吞掉错误导致 E2E 误判为成功结果；失败态仍应保持 `status='error'`。

明确不得提交以下文件，除非用户另行确认这是流程文档任务：

- `.gitignore`
- `backend/app/core/config.py`
- `docs/AGENT_FLOW.md`
- `docs/agent_flow/CURRENT_TASK.md`
- `docs/agent_flow/TASK_CARD.md`
- `docs/agent_flow/*` 其他流程文件

## 9. 验收标准

- `/smart-chat` 物流 data-qa 请求失败时，消息区展示业务可理解中文错误。
- 错误消息包含可操作动作：稍后重试、缩小范围、联系技术同事、提供追踪编号中的至少一类。
- 有 `trace_id` 时必须展示追踪编号。
- 错误消息中不得出现 Axios、HTTP 原始英文错误、SQL、表名、堆栈、文件路径。
- 正常物流 A/B/C/空结果展示不变。
- `/smart-chat` BOM 正常问答不回退。
- 不修改后端查询逻辑、数据库结构、A/B/C 分类规则。
- `npm run build` 通过。
- git diff 只包含本任务允许修改的前端文件；不得夹带 `.env`、缓存、pyc、IDE 文件或无关文档。

## 10. 给【全栈开发 Codex】的完整任务指令

你运行在 Codex App 新工作树，本地环境是 `gcl-bp-dev`，启动分支必须是 `agent/bp-dev`。

开始前必须确认：

- 当前分支是 `agent/bp-dev`
- 当前工作树是开发工作树，不是 `agent/bp-main`
- 需求来源是 `REQ-20260429-001`

如果当前分支不是 `agent/bp-dev`，立即停止并向用户说明。

只实现 `REQ-20260429-001`：优化 `/smart-chat` 中物流 data-qa 查询失败时的前端错误提示。

实施要求：

1. 先读取 `AGENTS.md`、`docs/agent_flow/CURRENT_TASK.md`、本任务卡、`frontend/src/views/business-chat/BusinessChatPage.vue`、`frontend/src/utils/http.ts`。
2. 不修改后端 data-qa 查询逻辑，不修改 A/B/C 分类，不改数据库结构。
3. 本次只允许修改本需求相关文件，优先只改 `frontend/src/views/business-chat/BusinessChatPage.vue`。
4. 在页面内新增一个局部 helper，用中文注释说明：
   - 函数功能
   - 参数含义
   - 返回值
   - 为什么要屏蔽技术错误细节
5. 将 `catch` 分支里的 `error.message` 替换为业务化错误消息。
6. 保持 `failAssistantMessage` 的 `status='error'` 行为，不把失败伪装成成功、B 类或 C 类。
7. 不改成功态 `adaptLogisticsResult`、B/C 展示、BOM 展示和自动识别逻辑。
8. 运行 `cd frontend && npm run build`。
9. 最终报告必须包含：
   - 修改文件清单
   - 关键改动
   - 测试命令和结果
   - 风险点
   - 未解决问题
10. 不允许 `git add`、`git commit`、`git push`，除非用户另行明确要求。

明确不得提交以下文件，除非用户另行确认这是流程文档任务：

- `.gitignore`
- `backend/app/core/config.py`
- `docs/AGENT_FLOW.md`
- `docs/agent_flow/CURRENT_TASK.md`
- `docs/agent_flow/TASK_CARD.md`
- `docs/agent_flow/*` 其他流程文件

## 11. 给【测试运维 Codex】的完整任务指令

你运行在 Codex App 新工作树，本地环境是 `gcl-bp-test`，启动分支必须是 `agent/bp-test`。

允许 Codex App 新工作树处于 detached HEAD，但必须同时确认：

- HEAD 基于 `agent/bp-test`
- 已包含 `agent/bp-dev` 的最新开发变更
- 当前工作树是测试工作树，不是 `agent/bp-main` 或 `agent/bp-dev`

如果无法确认以上条件，立即停止并向用户说明。

测试目标：验证 `/smart-chat` 物流 data-qa 失败态提示业务化，且正常问答不回退。

测试步骤：

1. 读取 `AGENTS.md`、`docs/agent_flow/CURRENT_TASK.md`、本任务卡。
2. 记录测试前 git 状态，区分本轮实测结果和历史文档结论。
3. 确认当前 HEAD 包含 `agent/bp-dev` 的最新开发变更。
4. 执行 `cd frontend && npm run build`。
5. 用浏览器或 Playwright 打开 `/smart-chat`。
6. 通过拦截 `/api/v1/logistics/data-qa/query` 或临时断开后端服务模拟失败：
   - 500 + `trace_id`
   - 网络不可达
   - 超时
   - 422
7. 检查页面最后一条助手消息：
   - 有 `data-testid="message-error"`
   - `data-status="error"`
   - 文案为业务化中文
   - 有 trace_id 时展示追踪编号
   - 不含技术细节
8. 回归正常问答：
   - 物流 A 类成功展示答案
   - 物流 B 类展示追问
   - 物流 C 类展示拒答和可改问方向
   - BOM 正常问答可用
9. 输出测试报告：
   - 通过/失败用例
   - 失败截图或 DOM 文本
   - 是否发现技术错误泄露
   - 是否影响正常问答
   - 是否建议阻断交付

不得修改文件，不得提交代码。

明确不得提交以下文件，除非用户另行确认这是流程文档任务：

- `.gitignore`
- `backend/app/core/config.py`
- `docs/AGENT_FLOW.md`
- `docs/agent_flow/CURRENT_TASK.md`
- `docs/agent_flow/TASK_CARD.md`
- `docs/agent_flow/*` 其他流程文件

## 12. 建议分支名和工作树规则

开发工作树：

- 使用 Codex App 的“新工作树”
- 本地环境名：`gcl-bp-dev`
- 启动分支：`agent/bp-dev`
- 如需本地路径，统一放在 `/Users/zhuchangchao/Work/PythonProject/project/agent-worktrees/` 下

测试工作树：

- 使用 Codex App 的“新工作树”
- 本地环境名：`gcl-bp-test`
- 启动分支：`agent/bp-test`
- 允许 detached HEAD，但必须确认 HEAD 基于 `agent/bp-test`，且已包含 `agent/bp-dev` 的最新开发变更
- 如需本地路径，统一放在 `/Users/zhuchangchao/Work/PythonProject/project/agent-worktrees/` 下

建议开发分支名：

- `agent/bp-dev`

建议测试分支名：

- `agent/bp-test`
