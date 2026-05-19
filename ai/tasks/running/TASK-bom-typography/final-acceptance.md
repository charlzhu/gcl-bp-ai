# TASK-bom-typography 最终验收报告

## 任务目标
用户指出 BOM 数据管理页整体字号太大、排版和字体不需要那么大、业务员要看得懂看得清、不要花哨。本轮目标是收敛字号、间距、渐变和阴影，让页面更像稳重的业务后台。

## 根因
上一版为了解决区域粘连和指标卡质感，加入了较大的 hero 标题、指标数字、强渐变、光斑装饰和较重阴影。虽然层次更明显，但对业务数据管理页来说视觉强调过度，导致页面显得“字大、花哨”。

## 修改范围
- frontend/src/views/plan-bom/BomDataManagementPage.vue
- tests/business_acceptance/test_plan_power_frontend_upload_entry.py

## 关键改动
1. 新增字号/少装饰静态验收：禁止超大 hero 字号、超大指标字号、radial-gradient 光斑、overview-card 装饰圆、重阴影等回归。
2. Hero 标题字号从 clamp(34px, 4vw, 52px) 收敛为 clamp(26px, 2.4vw, 34px)。
3. 指标值字号从 clamp(28px, 2.6vw, 38px) 收敛为 clamp(22px, 2vw, 30px)。
4. Tab 从 44px / 15px / 重阴影收敛为 36px / 14px / 轻阴影。
5. 上传标题、文件名、按钮高度、卡片高度、dropzone 留白同步收敛。
6. 去除页面 radial-gradient 背景光斑、hero 装饰光斑、指标卡装饰圆和多处强渐变，保留白底、细边框、轻阴影。
7. 保留上一轮用户关心的结构：上方概览与下方工作区分离、上传/历史 tab、BOM 与功率模型上传隔离、历史分页、功率模型生效能力。

## 验收结果
- Focused 测试：20 passed。
- 前端 build：通过，仅既有 chunk size warning。
- git diff --check：通过。
- 安全扫描：通过，无新增 secret/token，无临时功率模型 token 回归。
- 浏览器复验：首屏、上传区底部、历史表格与分页均清晰克制，无横向溢出/裁切/错位，console 无错误。
- Reviewer：通过，无阻塞问题。

## Full acceptance 状态
全量 business acceptance 当前为 138 passed, 3 failed, 2 warnings。失败点在后端真实业务 QA 回归：供应商推荐导出列断言、线长/接线盒行数断言。本轮只改 BOM 页面前端样式与前端验收，不影响这些后端 QA 结果，不能声明 full 全量通过。

## 风险与后续建议
- 当前页面已从“设计感偏强”收敛为“业务后台稳重清晰”。
- 若继续打磨，建议统一二级历史 tab 风格，并单独处理 full acceptance 中 3 个真实业务 QA 失败。
