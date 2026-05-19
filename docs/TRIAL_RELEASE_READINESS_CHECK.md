# 试运行发布前检查报告

- 发布包：经营计划智能助手试运行发布包：物流问答 + 计划 BOM 问答
- 生成时间：`2026-05-14T16:25:05`
- 总体结果：`未通过`

## 状态分布

- 物流：`A=656 / B=178 / C=69 / D=0`
- BOM：`A=86 / B=40 / C=3 / D=0`

## 检查项

| 检查项 | 结果 |
| --- | --- |
| `required_docs_exist` | `FAIL` |
| `required_reports_exist` | `PASS` |
| `frontend_files_exist` | `PASS` |
| `env_example_exists` | `PASS` |
| `logistics_distribution_ok` | `PASS` |
| `bom_distribution_ok` | `PASS` |
| `bom_upload_api_report_ok` | `PASS` |
| `bom_qa_api_e2e_ok` | `PASS` |
| `logistics_e2e_report_ok` | `PASS` |
| `guardrail_bounded_check_ok` | `PASS` |
| `no_real_api_key_in_docs` | `PASS` |
| `status_docs_not_wave_or_migration` | `PASS` |

## 非阻塞说明

- logistics full rollout 路径仍保留；发布前门禁使用 bounded Guardrail check，避免长时间挂起。
- 当前发布包不包含继续迁 A、扩 query_key 或 BOM Wave3 能力开发。

## 失败明细

- 缺失文档：`['docs/LOGISTICS_903_ACCEPTANCE_REPORT.md']`