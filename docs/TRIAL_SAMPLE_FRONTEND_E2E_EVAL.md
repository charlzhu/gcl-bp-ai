# TRIAL_SAMPLE_FRONTEND_E2E_EVAL

- 前端地址：`http://127.0.0.1:5173/smart-chat`
- 后端地址：`http://127.0.0.1:8000/api/v1`
- 总计划用例：3281
- 已执行：3281
- 未执行：0
- 状态：completed
- 停止条件：all_cases_completed
- 抓取方式：真实 `/smart-chat` 页面输入问题，读取 DOM 文本、表格、追问和拒答解释。
- 当前前端执行状态：`3281/3281 pass`
- 服务日志位置：`tmp/trial_sample_eval/logs/`。
- 未来复测命令：`backend/.venv/bin/python scripts/trial_sample_e2e_batch_runner.py --resume --include-variants --batch-size 50 --time-budget-minutes 55`
- 当前 `failed_cases.json` 为空；没有用 API 或 service 结果替代网页展示结果。

## 历史执行过程
- 历史过程曾从 679 条 checkpoint 继续执行，新增执行 2602 条后达到全量完成。该信息仅说明执行过程，非当前状态。
