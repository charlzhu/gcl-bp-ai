# TASK-bom-layout-v2 最终验收说明

## 用户问题
用户截图指出 BOM 数据管理页 5 个视觉/布局问题：
1. 上方概览区域和下方工作区紧贴，缺少层级；
2. 下方上传工作区和上方信息混在一个大框内；
3. BOM 上传批次指标卡不够企业级；
4. 当前生效模型指标卡不协调；
5. 上传数据 / 查看历史 tab 样式不协调。

## 根因
- 原页面将 hero、指标卡、tab、上传卡片塞在同一个 `bom-management-panel` 内，只靠细边框分隔，导致区域 1/2 视觉粘连。
- 指标卡只有左侧色条 + 普通白底，缺少企业级指标组件所需的顶部状态、数值层级、浅色背景和一致阴影。
- 主 tab 使用简单胶囊按钮，尺寸、圆角、色彩和整体卡片语言不统一。
- 本轮重构后又发现一个真实布局风险：固定高度页面容器使用 CSS grid 后，grid track 会压缩第二个工作区，配合 `overflow:hidden` 会裁掉上传按钮；已通过 `grid-auto-rows: max-content` 修复。

## 修改范围
- `frontend/src/views/plan-bom/BomDataManagementPage.vue`
  - 拆分为 `bom-hero-card` 和 `bom-workspace-card` 两个独立区域；
  - 页面容器增加 `gap: 22px`、`grid-auto-rows: max-content`，保留内部滚动；
  - 指标卡重构为 `overview-card__top / label / badge / value / desc`；
  - 指标卡增加顶部渐变色条、浅色背景、阴影和更明确的字号层级；
  - 主 tab 改为 `management-tabs--segmented`，增加 `workspace-tab-label` 与状态圆点；
  - 上传卡片增大内边距、高度、圆角、阴影和 dropzone 空间，左右卡片对齐；
  - 保留 BOM 上传和功率模型上传隔离、历史 tab/分页、版本生效能力。
- `tests/business_acceptance/test_plan_power_frontend_upload_entry.py`
  - 新增布局级验收，覆盖 hero/workspace 分层、指标卡结构、tab 结构、页面间距和内部滚动模型；
  - 更新旧的页面滚动容器验收，避免锁死旧 padding。

## 验证结果
- Focused 验收：`19 passed in 2.06s`。
- 前端 build：通过，仅保留既有 Vite chunk size warning。
- `git diff --check`：通过。
- focused diff 安全扫描：通过，未新增硬编码密钥/token。
- 禁用 token/权限字符串搜索：`frontend/src` 中 0 matches。
- 浏览器复验：
  - 1/2 区域已明显分开；
  - 3/4 指标卡更像企业级组件且风格协调；
  - 5 主 tab 与页面风格协调；
  - 上传卡片下半部可通过页面内部滚动完整看到；
  - 无横向溢出、裁切、错位；
  - console 无错误。
- 独立 reviewer：通过，无阻塞问题，无安全问题。

## Full acceptance 状态
全量 business acceptance 当前结果：`137 passed, 2 failed, 2 warnings`。
失败用例仍为既有/无关的真实 BOM QA 行数断言：线长/接线盒样例当前返回 13 行，但测试期望 11 行。该失败不在本次 BOM 页面 UI focused diff 内。

## 风险与后续建议
- 本次未修改后端、上传接口、功率模型解析、BOM 查询逻辑。
- reviewer 非阻塞建议：二级 `history-tabs` 后续也可统一成胶囊风格，使历史页内部视觉更一致。
- 建议后续单独处理 full acceptance 的真实 BOM QA 行数断言问题。
