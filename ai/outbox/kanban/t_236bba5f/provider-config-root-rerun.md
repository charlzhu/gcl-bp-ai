# 主项目环境 provider/live gate 补充复跑结果

## 目的

`t_236bba5f` 在独立 worktree 中 blocked，原因是该 worktree 没有 `backend/.env`，导致 provider 配置未注入。为区分“代码失败”和“环境未加载”，已在主项目环境做一次无代码、脱敏 gate 复跑。

## 复跑环境

- 主项目路径：`/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai`
- HEAD：与预检 worktree 相同，均为 `f24d39ae318cea9af081aa05b3edfdcdcf46ef33`
- 主项目状态：仅存在既有 tracked `.gitignore` 修改；本次复跑未修改代码、未 stage、未 commit、未 push。
- 输出目录：`/tmp/hermes/nl2sql_m10_provider_config_gate_root/`

## 结果

| Gate | 结果 | 证据 |
|---|---:|---|
| provider smoke | PASS | `/tmp/hermes/nl2sql_m10_provider_config_gate_root/provider-smoke.log` |
| catalog reindex | PASS | `indexed_count=127` |
| live provider M9 shadow gate | PASS | `total=3, success=2, validation_failed=1, recall_failed=0, expected_status_mismatch_count=0` |

## 结论

M9/M9.1 当前代码能力与 provider/live gate 在主项目环境下可以通过；`t_236bba5f` 的 blocker 是独立 worktree 没有加载私有 provider 配置，不是 M9 代码失败。

因此可以创建 M10 candidate-SQL safety-gate Shadow MVP 的代码开发看板任务，但 M10 worker 必须注意：

1. 不得复制、提交或输出 `.env` / 密钥。
2. 独立 worktree 如无 venv，可使用主项目 `backend/.venv/bin/python`。
3. 需要 live provider gate 时，应通过既有主项目环境或安全的进程级环境注入方式加载配置，只输出 PASS/BLOCKED 摘要，不输出配置值。
