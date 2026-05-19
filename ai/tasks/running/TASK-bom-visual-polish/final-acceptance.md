# TASK-bom-visual-polish 最终验收报告

## 任务目标
站在业务人员视角修复“BOM 数据管理”页面视觉 / 交互问题，使页面更清爽、更好看、更符合企业生产级平台的人机交互。

## 当前仓库状态判断
- 本轮仅处理 `BOM 数据管理` 页面和对应前端验收。
- 工作树存在其他历史任务未提交改动；本轮 diff / review / 验收均限定 focused files：
  - `frontend/src/views/plan-bom/BomDataManagementPage.vue`
  - `tests/business_acceptance/test_plan_power_frontend_upload_entry.py`
- 未修改后端业务逻辑、数据库迁移、接口契约、token/密钥配置。

## 根因分析
1. 首屏信息噪音较高：标题、标签、说明文字重复，业务人员很难第一眼判断“现在该做什么”。
2. 上传卡片层级不统一：按钮、说明、状态提示之间缺少统一操作节奏。
3. 历史表暴露技术值：`success`、`manual_import_source`、`Issue 数`、`文件 Hash`、`版本 ID`、`parse_status` 等对业务人员不友好。
4. 功率模型结果卡和历史表未复用统一中文状态转换，导致页面局部仍可能出现 raw 后端状态码。

## 修改文件
```text
.../src/views/plan-bom/BomDataManagementPage.vue   | 1013 ++++++++++++--------
 .../test_plan_power_frontend_upload_entry.py       |  108 ++-
 2 files changed, 688 insertions(+), 433 deletions(-)
```

## 关键改动
1. 首屏工作台清爽化
   - 主标题改为“BOM 文件与功率模型”。
   - 保留“上传数据 / 查看历史”主 tab。
   - 去掉重复 `hero-tags` / `secondary-status-strip` 等装饰性信息。
   - 使用紧凑状态条展示“文件隔离 / 历史批次 / 模型生效”。

2. 上传卡片统一化
   - BOM 与功率模型上传卡片统一布局、间距、虚线上传区、按钮位置。
   - 禁用按钮改为“选择文件后可上传 / 选择模型后可上传”，明确下一步动作。
   - 保留 BOM Excel 上传和功率模型 xlsm 上传隔离。

3. 历史 tab 业务化
   - `success/failed/warning/created` 等状态统一转换为“成功 / 失败 / 需关注 / 已创建”等中文业务状态。
   - `manual_import_source` 转为“手动上传”。
   - `Issue 数` 改为“问题数”。
   - `文件 Hash` 改为“文件指纹”。
   - `版本 ID` 改为“版本编号”。
   - 上传结果卡也改为 `formatStatusLabel(uploadPowerModelResult.version?.parse_status)`，避免上传后暴露 raw 状态码。

4. 验收补强
   - 增加静态验收，防止重复标签、英文装饰、raw 状态、raw 来源、技术字段名回归。
   - 保留历史分页、功率模型版本历史、生效切换相关断言。

## 测试结果
- Focused pytest：`18 passed in 1.38s`
- Frontend build：通过，仅既有 Vite chunk size warning
- `git diff --check`：通过
- Focused security scan：通过，未新增 hardcoded secret/token
- Browser：上传页、BOM 历史、功率模型历史均无 console error / 横向溢出；raw 技术词过滤结果为空
- Full business acceptance：`136 passed, 2 failed, 2 warnings`；2 个失败为真实库数据行数期望 11、实际 13，与本轮 focused UI diff 无关

## Reviewer 结论
Reviewer 结论：
- 第一轮：发现上传结果卡仍直接渲染 parse_status，可能显示 success/warning/failed；判定为 blocking。
- 修复：改为 formatStatusLabel(uploadPowerModelResult.version?.parse_status)，并补测试禁止旧表达式。
- 最终短复审：passed=true，blocking_findings=[]，security_concerns=[]。

## 风险与未解决事项
1. Full acceptance 仍有 2 个非本轮阻塞：`test_plan_power_real_business_qa_regression.py` 中真实库返回 13 行而用例期望 11 行，需要在后续 BOM 真实数据问答任务中单独处理。
2. “设为生效”成功反馈目前主要依赖表格刷新 / 生效状态变化；后续可增加历史 tab 内或全局消息提示。
3. 前端 build 仍有既有 Vite chunk size warning，不影响本轮交付。
4. 本轮做了桌面宽度浏览器验证，移动端窄屏未做专项视觉验收。

## 是否影响现有 BOM / 物流能力
- 不影响物流能力。
- 不改变 BOM 查询 / 上传 / 功率模型接口契约。
- 不改变数据库和后端计算逻辑。
- 只调整 BOM 数据管理页展示、文案和前端验收。

## 下一步建议
1. 人工打开 `/bom-data`，按“上传数据 → 查看历史 → 功率模型版本历史”顺序体验。
2. 若体验通过，本轮 focused diff 可进入提交前确认。
3. 单独安排后续任务处理 full acceptance 的 2 个真实库行数断言问题。
