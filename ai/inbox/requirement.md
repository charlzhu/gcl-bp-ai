# 需求：P2.2.1 补齐 business-oracle-excel 在 hermes_orchestrator 中的接入

## 背景

当前 `bash ai/scripts/run_tests.sh ai/reports/manual business-oracle-excel` 已经通过，说明 `run_tests.sh` 已支持
`business-oracle-excel` 测试模式。

但执行：

python ai/scripts/hermes_orchestrator.py run --mode safe --test-mode business-oracle-excel --skip-codex --skip-review
--max-repair-rounds 1

会报错：

argument --test-mode: invalid choice: 'business-oracle-excel'
choose from 'auto', 'smoke', 'full', 'business-import', 'business-oracle'

说明 `ai/scripts/hermes_orchestrator.py` 的 `--test-mode` 参数 choices 尚未包含 `business-oracle-excel`，导致无法通过
orchestrator 统一调度 P2.2 Excel Oracle 验收。

## 目标

只补齐 `business-oracle-excel` 在 `hermes_orchestrator.py` 中的 test-mode 接入，让 orchestrator 可以统一调度 P2.2 Excel
Oracle 验收。

本轮是 P2.2.1 收口任务，不新增业务功能，不扩展 Excel 标准答案计算逻辑，不进入 P2.3。

## 允许修改

- `ai/scripts/hermes_orchestrator.py`
- `ai/scripts/select_test_profile.py`，如存在 test mode 白名单限制
- `docs/BUSINESS_ACCEPTANCE_FRAMEWORK.md`，如需要补充命令说明

## 禁止修改

- 后端业务 service
- 前端页面
- 物流 Excel Oracle 计算逻辑
- 物流 Oracle Engine 核心逻辑
- trial_sample 既有脚本
- 数据库结构
- 生产数据
- `.env`
- token
- auth.json
- 自动 commit / push / deploy

## 功能要求

1. `python ai/scripts/hermes_orchestrator.py run --help` 中能看到 `business-oracle-excel`。
2. `--test-mode business-oracle-excel` 不再被 argparse 拦截。
3. orchestrator 调用 `run_tests.sh` 时，实际传入的 mode 必须是 `business-oracle-excel`，不能被降级成 `smoke`。
4. 不影响既有测试模式：
    - `auto`
    - `smoke`
    - `full`
    - `business-import`
    - `business-oracle`
5. 本轮不新增业务功能。
6. 本轮不扩展 Excel 计算逻辑。
7. 本轮不修改后端、前端、数据库、源数据。
8. 本轮不自动 commit、push、deploy。

## 验收命令

1. 编译检查：

python -m compileall -q ai/scripts

2. 检查 help 中是否出现 business-oracle-excel：

python ai/scripts/hermes_orchestrator.py run --help | grep business-oracle-excel

3. 检查 run_tests.sh 的 business-oracle-excel 是否仍然通过：

bash ai/scripts/run_tests.sh ai/reports/manual business-oracle-excel

4. 检查 orchestrator 能否调度 business-oracle-excel：

python ai/scripts/hermes_orchestrator.py run --mode safe --test-mode business-oracle-excel --skip-codex --skip-review
--max-repair-rounds 1

## 交付要求

1. 输出修改文件清单。
2. 输出实际执行的测试命令和结果。
3. 明确说明本轮只是 P2.2.1 收口，不进入 P2.3。
4. 明确说明没有修改业务后端、业务前端、数据库结构、生产数据、`.env`、token、auth.json。
5. 不自动提交 git。