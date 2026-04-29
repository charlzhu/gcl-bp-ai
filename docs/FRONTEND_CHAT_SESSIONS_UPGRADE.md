# 智能问答多对话窗口升级说明

## 本轮目标

本轮完成统一智能问答的多对话窗口能力。窗口作为一级菜单“智能问答”下的二级子菜单展示，每个窗口保存独立聊天记录，支持新建、切换、右键重命名和删除。

本轮只改前端会话体验，不修改物流 / BOM 后端业务边界，不迁 A，不扩 query_key。

## 对话窗口模型

每个窗口包含：

- `id`：窗口唯一 ID。
- `title`：二级菜单显示名称。
- `domain`：`auto` / `logistics` / `plan_bom`。
- `createdAt`：创建时间。
- `updatedAt`：更新时间。
- `messages`：当前窗口消息列表。
- `isNew`：是否为空白新窗口。
- `isPinned`：预留置顶字段。
- `lastQuestion`：最后一次用户问题。

每条消息包含：

- `id`
- `role`：`user` / `assistant` / `system`
- `content`
- `domain`
- `status`
- `presentation`
- `createdAt`
- `rawResponse`
- `loading`
- `error`

## 菜单设计

一级菜单保持：

- 智能问答
- BOM 数据管理
- 试运行说明

“智能问答”下新增二级菜单：

- 新建对话
- 具体对话窗口列表

当前选中窗口会高亮显示，标题过长会省略。窗口标题默认使用首条用户问题前 18 个字符，也可右键重命名。

## 新建窗口唯一性规则

- 已有内容的窗口可以存在多个。
- 同一时间只允许存在一个空白新窗口。
- 如果已有空白新窗口，再点击“新建对话”，不会创建第二个，而是自动聚焦已有空白窗口。
- 用户在空白窗口发送第一条消息后，该窗口转为正式窗口。
- 空白窗口被删除后，可以重新创建。
- 空白窗口即使被重命名，只要没有消息，仍视为唯一空白新窗口。

## 右键重命名 / 删除

对二级窗口菜单右键可操作：

- 重命名：弹出输入框，空标题不允许保存，标题会限制并截断。
- 删除：删除前确认；删除当前窗口后自动切换到最近更新窗口；如果没有其他窗口，自动创建一个空白新窗口。

删除只影响前端本地会话，不影响后端业务数据。

## localStorage 持久化策略

当前没有新增后端 session API，本轮采用前端 localStorage：

- 保存窗口摘要列表。
- 保存当前激活窗口 ID。
- 保存每个窗口的消息、标题、业务域和更新时间。
- 最多保留 20 个窗口。
- 单窗口最多保留最近 80 条消息，避免 localStorage 无限增长。

后续如接入后端会话存储，可以保持当前窗口模型不变，将 `businessChatSessions.ts` 内的读写替换为后端 API。

## 真实接口调用

统一智能问答仍调用真实接口：

- 物流数据：`POST /api/v1/logistics/data-qa/query`
- 计划 BOM：`POST /api/v1/plan-bom/qa/ask`

自动识别只负责选择调用哪个接口，不生成答案，不 mock 数据，不 hardcode 业务结果。

## 已修改页面

- `frontend/src/layouts/AppLayout.vue`
  - 将智能问答改为包含二级会话列表的菜单。
  - 增加新建对话、右键重命名、右键删除。

- `frontend/src/views/business-chat/BusinessChatPage.vue`
  - 按当前会话窗口读取和写入消息。
  - 支持请求返回写回原窗口，切换窗口不串消息。
  - 保留物流 / BOM 真实接口适配。

- `frontend/src/utils/businessChatSessions.ts`
  - 新增本地会话模型、持久化、唯一空白窗口、重命名、删除和更新事件。

## 已执行检查

- 搜索确认未引入 `mock` / `hardcode` / 技术主菜单字段。
- 检查菜单已包含“智能问答”二级窗口列表。
- 检查新建空白窗口唯一性逻辑。
- 检查右键重命名 / 删除逻辑。
- `npm run build --prefix frontend` 通过。
- `python scripts/trial_release_readiness_check.py` 通过。

## 已知限制

- 当前会话只保存在当前浏览器本地 localStorage，不跨浏览器、不跨设备同步。
- 刷新页面可保留会话；清理浏览器缓存会清除本地窗口。
- 暂未提供后端会话审计接口；如需要统一留痕，可在后端新增 conversation/session 存储并复用当前前端模型。
