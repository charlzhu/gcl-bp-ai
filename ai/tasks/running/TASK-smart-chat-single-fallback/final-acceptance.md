# TASK-smart-chat-single-fallback final acceptance

## 任务
修复“智能问答”菜单中删除唯一对话后会弹出两个新对话的问题，保证兜底新对话永远只有一个。

## 当前仓库状态判断
- 已完成能力：智能问答存在本地会话列表、激活会话和删除后兜底会话逻辑。
- 未完成/异常能力：删除唯一会话时原实现先广播空会话列表，多个组件监听器会同时触发 ensure，导致额外创建兜底会话。
- 本轮允许修改范围：`frontend/src/utils/businessChatSessions.ts` 会话删除逻辑；新增聚焦回归测试 `tests/business_acceptance/test_business_chat_session_lifecycle.py`。
- 本轮禁止修改范围：后端 BOM/物流业务链路、接口、数据库迁移、生产部署、用户密钥与大范围 UI 重构。

## 根因
`removeBusinessChatSession()` 删除最后一个会话后先执行 `clearActiveBusinessChatSessionId()`，随后立即 `emitBusinessChatSessionUpdated()` 广播“空列表 + 无 active”状态。该事件是同步分发的，`AppLayout` 与 `BusinessChatPage` 等监听器收到事件后都会调用 `ensureBusinessChatSession()`；其中一个监听器会先创建新会话。原函数回到自身后又无条件 `createBlankBusinessChatSession()`，因此最终出现 2 个“新对话”。

## 修复
删除唯一会话时不再先广播空列表状态，而是直接调用 `createBlankBusinessChatSession()` 创建唯一兜底会话；由创建函数统一保存、设置 active 并广播更新。

## 修改文件
- `frontend/src/utils/businessChatSessions.ts`
- `tests/business_acceptance/test_business_chat_session_lifecycle.py`

## 验证
- RED：新增测试在修复前失败，复现“实际 2 个新对话”。
- GREEN：`backend/.venv/bin/python -m pytest tests/business_acceptance/test_business_chat_session_lifecycle.py -q --tb=short` 通过。
- Build：`npm run build --prefix frontend` 通过。
- Static：focused `git diff --check` 通过；focused added-lines security scan 无发现。
- Browser：`/smart-chat` 删除唯一会话后 DOM 与 localStorage 均只剩 1 个“新对话”，console/js_errors=0。
- Review：独立 reviewer 通过。

## 已知非本任务问题
当前工作区在本任务开始前已有多处脏文件。运行既有更宽的 `tests/business_acceptance/test_plan_power_frontend_upload_entry.py` 时有 1 个失败：`test_business_chat_fall_ratio_estimate_uses_independent_nowrap_segment_rows` 期望 `isFallRatioEstimateColumn`，属于既有未完成的表格展示任务，非本次两文件 diff 引入。本次未越界修复该无关问题。

## 影响评估
- 不影响后端、数据库、BOM 查询、物流问答与计划 BOM 功率计算。
- 只改变删除最后一个本地智能问答会话时的事件广播顺序，风险较低。

## 是否通过本轮验收
本轮聚焦 bug 修复通过；若要合并当前整个脏工作区，仍需先处理上述无关既有失败与其他未提交改动。
