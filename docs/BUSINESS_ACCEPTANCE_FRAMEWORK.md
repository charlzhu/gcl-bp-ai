# BUSINESS_ACCEPTANCE_FRAMEWORK

## 目标

`business_acceptance` 用于把新的 Word/docx 业务问题文档导入为可复用验收用例，后续再接入物流 Excel/MySQL 和 BOM 不规则 Excel 标准答案计算器，以及真实 Web 页面逐题验收。

## 当前已实现

- 从 `.docx` 中读取编号问题。
- 生成 `raw_questions.json`。
- 生成 `normalized_cases.json`。
- 将问题分类为 `logistics` / `bom` / `unknown`。
- 标记 `oracle_status`：
  - `READY`：导入文档已携带标准答案。
  - `NEED_ORACLE`：业务域已识别，但尚未绑定可复算标准答案。
  - `NEED_DATA`：无法识别当前数据域，需要先确认数据来源。
  - `NEED_CLARIFICATION`：缺少时间、指标、异常定义或比较口径。
  - `UNSUPPORTED`：预测、策略设计或开放分析类问题。
- 生成 `case_classification_report.md`。
- 新增 `ai/scripts/run_tests.sh ... business-import` 测试模式。

## 目录约定

- `scripts/business_acceptance_importer.py`：导入与标准化核心模块。
- `scripts/business_acceptance_import_questions.py`：命令行入口。
- `tests/business_acceptance/`：轻量回归测试与目录约定。
- 默认输出：`tmp/business_acceptance/`。
- Hermes 报告输出：`ai/reports/<task>/.../business_acceptance/`。

## 使用方式

```bash
python scripts/business_acceptance_import_questions.py \
  --question-file /path/to/questions.docx \
  --output-dir tmp/business_acceptance
```

自测模式不依赖真实业务文件：

```bash
python scripts/business_acceptance_import_questions.py \
  --self-test \
  --output-dir tmp/business_acceptance_self_test
```

自动化测试：

```bash
bash ai/scripts/run_tests.sh ai/reports/manual business-import
```

## 当前边界

- 当前不修改物流或 BOM 业务核心逻辑。
- 当前不调用 `/smart-chat`，不执行真实 Web E2E。
- 当前不计算真实标准答案，只标记 oracle 准备状态。
- 既有 `trial_sample_*` 脚本和 3281/3281 真实网页 E2E 结果口径保持独立。
