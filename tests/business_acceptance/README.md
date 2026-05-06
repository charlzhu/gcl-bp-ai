# business_acceptance

本目录保存可复用业务问题集验收框架的测试、夹具和本地产物约定。

## 目录约定

- `fixtures/`：放置小型脱敏 docx / json 夹具，不放真实业务原始文件。
- `outputs/`：保留本地调试输出约定，正式运行默认写入 `tmp/business_acceptance` 或 `ai/reports/.../business_acceptance`。
- `test_*.py`：使用标准库 `unittest`，避免为导入框架额外引入测试依赖。

## 当前边界

- 当前只完成 Word/docx 问题导入、业务域分类和 oracle 状态标记。
- 当前不调用后端业务 service，不计算真实物流/BOM 标准答案。
- 当前不影响既有 `trial_sample_*` 脚本和 3281/3281 真实网页 E2E 口径。
