# E2E 数据问答验收：Hermes 技术经理自动推进模式

## 核心目标

本任务要求 Hermes 作为技术经理自动推进，不需要用户一步一步指挥 Hermes。

Hermes 可以一步一步指挥 Codex 完成：
1. 数据解析
2. 标准答案计算
3. 浏览器页面验证
4. expected / actual 对比
5. 失败原因分类
6. 定向修复
7. 回归验证
8. 最终报告

但 Hermes 必须承担独立审查职责，不能完全依赖 Codex 自己跑、自己测、自己宣布通过。

## 角色边界

### 用户

用户只负责：
1. 提供总需求
2. 确认启动
3. 审批高风险操作
4. 最终验收

用户不需要逐步指挥 Hermes。

### Hermes

Hermes 是技术经理，负责：
1. 理解需求
2. 自动拆分阶段
3. 自动指挥 Codex
4. 检查 Codex 产物
5. 审查标准答案 trace
6. 抽样复算标准答案
7. 检查浏览器页面返回结果
8. 检查页面答案样式
9. 判断失败原因
10. 指挥 Codex 定向修复
11. 控制重试次数
12. 生成最终报告

### Codex

Codex 是受控执行工程师，负责：
1. 写脚本
2. 跑脚本
3. 读取附件
4. 查询只读数据库
5. 浏览器自动化验证
6. 修改代码
7. 修复 Hermes 指定的问题

Codex 不是最终审核人。

## 附件

附件目录：

ai/inbox/attachments/

包括：
1. 23 年至 25 年物流源数据.zip
2. BOM 源数据.zip
3. 物流和 bom样例题.docx

## 数据范围

1. 2023-2025 物流历史数据来自附件 zip。
2. BOM 数据来自附件 zip。
3. 2026 物流数据来自 MySQL xst_cloud 库，只允许只读查询。
4. 如果 2026 数据库不可访问，相关问题必须标记 blocked，不允许编造。

## 自动执行阶段

Hermes 必须自动推进以下阶段。

### Phase 0：数据资产准备

Hermes 指挥 Codex：
1. 解压附件到任务目录
2. 识别物流文件、sheet、字段
3. 识别 BOM 文件、sheet、字段
4. 解析样例题 docx
5. 生成 sample_questions.jsonl
6. 生成 data_profile_report.md

Hermes 检查：
1. 附件是否都被识别
2. 样例题数量是否正确
3. 问题是否被分类
4. 是否有无法解析的文件

### Phase 1：标准答案计算

Hermes 指挥 Codex：
1. 编写标准答案计算脚本
2. 从物流历史附件计算 2023-2025 问题
3. 从 BOM 附件计算 BOM 问题
4. 从 MySQL xst_cloud 只读查询 2026 问题
5. 输出 expected_answers.jsonl
6. 输出 expected_answer_trace.jsonl

Hermes 检查：
1. 每个 expected_answer 是否有 trace
2. trace 是否包含 source、sheet、filter、field、aggregation
3. 抽样复算关键问题
4. no_answer 是否合理
5. blocked 是否合理

### Phase 2：浏览器页面验证

Hermes 指挥 Codex：
1. 使用 Playwright 打开智能助手问答页面
2. 逐题输入样例题
3. 抓取页面答案
4. 抓取表格结构
5. 抓取无答案状态
6. 抓取错误状态
7. 保存截图
8. 保存 page_html
9. 输出 actual_answers.jsonl

Hermes 检查：
1. 页面是否真的回答
2. answer 是否可见
3. 表格是否正常渲染
4. 空结果 / 无答案状态是否正确
5. 页面是否有错误提示
6. 截图是否存在

### Phase 3：答案对比

Hermes 指挥 Codex：
1. 对比 expected_answers 和 actual_answers
2. 数值题支持单位换算和小数误差
3. 表格题检查行列和关键值
4. BOM 题检查物料分类和规格描述
5. 排名题检查排序
6. 无答案题检查是否正确拒答
7. 输出 comparison_result.jsonl
8. 输出 comparison_summary.md

Hermes 检查：
1. comparison_result 是否有每题结论
2. 失败题是否有明确原因
3. 通过题是否有证据
4. 不能只看字符串相等

### Phase 4：失败归因与修复

Hermes 自动判断失败类型：

1. EXPECTED_ERROR：标准答案脚本错误
2. DATA_PARSE_ERROR：附件解析错误
3. DB_QUERY_ERROR：数据库查询错误
4. BACKEND_ERROR：后端问答逻辑错误
5. NLU_ERROR：意图识别错误
6. SQL_TEMPLATE_ERROR：SQL 模板错误
7. FRONTEND_RENDER_ERROR：前端展示错误
8. BROWSER_TEST_ERROR：浏览器验证脚本错误
9. NO_DATA：确实无数据
10. AMBIGUOUS_QUESTION：问题本身歧义

Hermes 指挥 Codex 按失败类型定向修复。

自动修复最多 3 轮。

每轮修复后，只回归失败题和问法变体题。

### Phase 5：鲁棒性验证

Hermes 指挥 Codex 生成问法变体回归集。

要求：
1. 不允许只支持原始样例题
2. 不允许根据 question_id 或完整问题文本硬编码
3. 必须通过意图、指标、维度、时间、实体识别来支持
4. 同义问法必须走同一能力链路

需要覆盖：
1. 年份简写：2025年 / 25年
2. 指标同义词：发运量 / 承运量 / 发货量 / 运输量
3. 主体同义词：物流公司 / 承运商 / 供应商
4. 时间表达：1月 / 1月份 / 2026年1月
5. 区域表达：华东 / 华东区域
6. 订单表达：订单号 / 客户-年份-编号 / 产品型号
7. 表格要求：生成表格 / 表格告诉我 / 列出来

Hermes 检查：
1. 变体题是否命中同一 intent
2. 变体题答案是否和原题一致
3. 修复是否是能力增强，不是硬编码

## 严禁事项

1. 禁止 Hermes 每一步都要求用户指挥
2. 禁止 Codex 自己宣布最终通过
3. 禁止用 LLM 猜标准答案
4. 禁止按完整问题文本硬编码答案
5. 禁止无 trace 的标准答案
6. 禁止无截图的页面验证
7. 禁止只测接口不测页面
8. 禁止无答案问题乱答
9. 禁止自动 commit
10. 禁止自动 push
11. 禁止自动部署
12. 禁止写生产数据库

## 人工闸门

只有以下情况需要询问用户：
1. 需要写数据库
2. 需要改数据库结构
3. 需要修改生产配置
4. diff 超过 1000 行
5. 需要删除大量文件
6. 自动修复 3 轮仍失败
7. 2026 MySQL 连接缺失或无权限
8. 发现业务口径冲突
9. 需要改变核心架构

## 最终输出

必须生成：

1. ai/eval/data_profile_report.md
2. ai/eval/sample_questions.jsonl
3. ai/eval/expected_answers/expected_answers.jsonl
4. ai/eval/expected_answers/expected_answer_trace.jsonl
5. ai/eval/runs/<run_id>/actual_answers.jsonl
6. ai/eval/runs/<run_id>/comparison_result.jsonl
7. ai/eval/runs/<run_id>/comparison_summary.md
8. ai/eval/runs/<run_id>/ui_review_result.jsonl
9. ai/eval/runs/<run_id>/robustness_result.jsonl
10. ai/eval/runs/<run_id>/screenshots/
11. ai/eval/runs/<run_id>/failed_cases.md
12. ai/eval/runs/<run_id>/fixed_cases.md
13. ai/eval/runs/<run_id>/no_answer_cases.md
14. ai/eval/runs/<run_id>/blocked_cases.md
15. ai/eval/runs/<run_id>/e2e_validation_report.md

## 验收标准

1. Hermes 能自动推进完整流程，不需要用户逐步指挥。
2. Codex 负责执行，但 Hermes 负责审查。
3. 标准答案有 trace。
4. Hermes 对关键题进行抽样复算。
5. 页面结果和标准答案完成对比。
6. 页面样式被检查。
7. 失败题有明确分类。
8. 可修复问题经过自动修复和回归。
9. 无答案题被明确标记 no_answer。
10. 数据库不可访问题被标记 blocked。
11. 问法变体通过鲁棒性验证。
12. 修复不能依赖完整问题文本硬编码。
13. 最终报告清楚说明通过、失败、修复、阻塞和风险。