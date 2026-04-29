# 前端业务化 UI 重大升级说明

## 升级目标

本轮把前端从技术验证页面升级为业务试运行级产品界面。

- 平台名称：`协鑫集成 经营计划智能助手`
- 网页标签：`经营计划智能助手`
- 当前统一入口：`智能问答`

本轮只调整前端 UI、信息架构、菜单、路由和交互体验，不迁 A，不扩 query_key，不修改物流或 BOM 的业务边界。

## 修改页面

- `frontend/src/layouts/AppLayout.vue`
  - 重做主布局、品牌栏、业务主导航。
  - 一级菜单调整为：智能问答、BOM 数据管理、试运行说明。
  - 查询历史、任务日志、条件查询等技术/管理入口不再作为业务主导航展示。
  - 已清理合并冲突残留，避免运行时加载错误布局代码。
  - 二次优化为极简侧栏：白灰主调，去掉品牌大卡片和多余说明，只保留导航与试运行标识。

- `frontend/src/views/business-chat/BusinessChatPage.vue`
  - 新增统一智能问答入口。
  - 支持自动识别、物流数据、计划 BOM 三种业务域选择。
  - 物流问题调用真实物流接口 `/api/v1/logistics/data-qa/query`。
  - BOM 问题调用真实 BOM 接口 `/api/v1/plan-bom/qa/ask`。
  - 自动识别无法判断时只做业务域追问，不生成假答案。
  - 二次优化为 ChatGPT 式中心对话：移除 hero 大卡片、对话外框和推荐问题卡片，保留居中欢迎语、小型问题 chip 和底部圆角输入框。

- `frontend/src/views/plan-bom/BomDataManagementPage.vue`
  - 新增业务化 BOM 数据管理页。
  - 支持 BOM Excel 上传，调用真实接口 `/api/v1/plan-bom/upload`。
  - 上传结果以订单数、物料数、warning、error 和下一步建议展示。
  - 移除上传后的长说明模块，只保留标题、文件选择、上传动作和结果。

- `frontend/src/views/trial/TrialGuidePage.vue`
  - 新增试运行说明页。
  - 面向业务用户说明 A/B/C 含义、反馈方式和能力边界。
  - 压缩说明文案，保留“可问 / 会追问 / 会说明 / 边界”四类必要内容。

- `frontend/src/router/index.ts`
  - 首页默认跳转到 `/smart-chat`。
  - 新增 `/smart-chat`、`/bom-data`、`/trial-guide`。
  - 旧 `/logistics/data-qa` 路径兼容重定向到统一智能问答入口。

- `frontend/index.html`
  - 浏览器标签更新为 `经营计划智能助手`。

- `frontend/src/api/planBom.ts`
  - BOM 上传方法增加可选参数，支持业务页面传入 source、overwrite、remark。
  - 不在前端解析 Excel，仍调用真实后端上传接口。

- `frontend/tsconfig.json`
  - 增加 `noEmit: true`，防止 `vue-tsc` 把 `.vue.js` 生成到 `src` 目录。
  - 已删除 `src` 下历史生成的 `.vue.js`、`main.js`、`router/index.js`，避免浏览器误加载 Volar 辅助代码。

## 菜单调整

新的一级菜单：

1. 智能问答
2. BOM 数据管理
3. 试运行说明

`查询历史` 从一级菜单移除。历史页和旧查询页暂时保留路由与代码，便于后续管理或回看使用，但不作为业务用户主入口展示。

## 统一智能问答入口

统一入口当前支持：

- 自动识别；
- 物流数据；
- 计划 BOM。

自动识别规则只用于选择调用哪个真实接口，无法判断时提示用户选择业务域。后续扩展经营分析、物料管理、计划管理等业务域时，可继续在统一入口增加 domain adapter。

## 字体和技术信息弱化

- 页面正文和对话正文：约 `14px`。
- 次要说明、标签、提示：约 `12px` 到 `13px`。
- 页面标题：约 `22px` 到 `24px`。
- 主界面不再强调 query_key、planner、slot、guardrail、raw response、已留痕、收起技术详情等技术文案。

## 极简视觉调整

- 主色改为白灰，淡绿用于状态，淡蓝用于业务域选择。
- 去掉大面积边框卡片、阴影和说明块，减少工业后台感。
- 统一问答页保留大留白和中心输入，避免首屏堆模块。
- 推荐问题从大卡片改为轻量 chip，只在空会话状态展示。
- 页面整体锁定为一屏高度，不再出现浏览器级整体滚动条；问答记录区独立滚动，输入框固定在底部。
- 物流和 BOM 返回表格列名在前端做中文展示映射，例如 `city` 显示为“城市”、`total_fee` 显示为“总运费”。
- 业务主界面不展示表名、字段名、SQL、内部口径等技术说明。

## 运行时异常修复

用户反馈的错误：

- `inject() can only be used inside setup() or functional components`
- `__VLS_asFunctionalComponent is not defined`

根因是 `src` 目录存在 Volar/TypeScript 生成的 `.vue.js` 文件，浏览器误加载后把 `useRoute()` 放在组件 setup 外执行。修复方式：

1. 清理 `src` 下 `.vue.js`、`main.js`、`router/index.js` 生成产物；
2. 修复 `AppLayout.vue` 中的冲突残留；
3. 在 `tsconfig.json` 中设置 `noEmit: true`，防止再次生成。

## 已执行检查

- 搜索旧名称和技术化主界面文案。
- 检查路由和菜单。
- `npm run build --prefix frontend`：通过，仅 Vite chunk size warning。
- `python scripts/trial_release_readiness_check.py`：通过。
- `python scripts/plan_bom_upload_api_check.py`：通过。
- `python scripts/plan_bom_qa_api_e2e_check.py`：30/30 通过。
- 本地 dev server 页面源码检查：入口为 `/src/main.ts`，路由解析为 `/src/router/index.ts`，未再加载 `AppLayout.vue.js`。

## 已知限制

- 旧历史页和旧查询页仍保留代码及隐藏路由，便于后续管理回看；它们不再出现在业务一级菜单。
- 当前自动识别是前端轻量关键词路由，不是后端统一 NLU。无法判断时会要求用户选择业务域。
- 经营分析、物料管理、计划管理等业务域只预留入口设计，本轮未接入新后端能力。
