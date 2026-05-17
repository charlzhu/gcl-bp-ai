# AI Answer Experience V2 验证报告

## 自动化测试

| 验证项 | 命令 | 结果 |
|---|---|---|
| Focused reviewer-fix tests | `python -m pytest tests/business_acceptance/test_business_chat_answer_format_preference.py::test_business_chat_session_keeps_only_safe_audit_table_for_secondary_actions tests/business_acceptance/test_business_chat_answer_format_preference.py::test_business_chat_frontend_caveat_items_guard_old_payloads -q` | 2 passed |
| 答案展示偏好回归 | `python -m pytest tests/business_acceptance/test_business_chat_answer_format_preference.py -q` | 11 passed |
| business_acceptance 全量 | `python -m pytest tests/business_acceptance -q` | 174 passed, 2 warnings |
| 前端构建 | `cd frontend && npm run build` | passed |

warnings：openpyxl 对 xlsm 扩展/条件格式的既有提示，不影响本任务。

## 浏览器 E2E

环境：

- backend：fresh uvicorn on `127.0.0.1:18083`
- frontend：Vite on `127.0.0.1:5177`，proxy 到 fresh backend
- 浏览器 storage：已清空

问题：

```text
2026年1月份、2月份运输方式为铁路的运输总量是多少MW？
```

验收结果：通过。

观察：

- 页面默认展示自然语言回答：`2026年1月、2月铁路方式合计发运量为0MW。`
- 默认未展开指标卡、明细表、图表。
- `数据口径` 默认折叠。
- 可见 `查看数据依据`、`展开明细`、`导出 Excel`。
- 点击 `展开明细` 后明细表正常展开。
- localStorage：
  - `presentation` 无 `debug`；
  - `rawResponse` 仅有 `result_table`；
  - 无 `query_plan`；
  - 无 `presentation.debug`。
- browser console 无 JS error。

截图：

```text
/Users/zhuchangchao/.hermes/cache/screenshots/browser_screenshot_deaaf762584e4bc1a424713e5e39b076.png
```

## 静态安全扫描

基于 task-scoped patch：

```text
diff_lines=1624
hardcoded_secrets=2
shell_injection=0
dangerous_eval_exec=0
unsafe_pickle=0
sql_formatting=0
```

`hardcoded_secrets=2` 均为测试中的 `api_key="test-key"` 假值，非真实密钥。

## 独立 review

- 初始 delegate reviewer 多次因外部 API 超时未返回。
- 改用本地 Codex CLI read-only review。
- 首轮 review：`passed=false`，发现 2 个阻塞点：presentation.debug 持久化风险、caveatItems 旧 payload 兼容问题。
- 已按 TDD 修复并重跑测试。
- 复审 review：`passed=true`，无 security_concerns，无 logic_errors。

复审结果文件：

```text
ai/tasks/running/TASK-ai-answer-experience-v2/codex_review_after_fix_result.json
```

## 结论

AI Answer Experience V2 已通过 focused tests、business_acceptance 全量、前端构建、浏览器 E2E 和独立 Codex review。
