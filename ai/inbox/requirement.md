# 需求：修复 hermes_orchestrator 不支持 business-import test-mode

## 背景

当前 `bash ai/scripts/run_tests.sh ai/reports/manual business-import` 已经通过，说明 run_tests.sh 已支持 business-import。

但执行：

python ai/scripts/hermes_orchestrator.py run --mode safe --test-mode business-import --until-pass --repair-on-fail
--max-repair-rounds 2

会报错：

argument --test-mode: invalid choice: 'business-import' (choose from 'auto', 'smoke', 'full')

说明 hermes_orchestrator.py 的 argparse choices 仍未包含 business-import。

## 目标

只修复 orchestrator 的 test-mode 参数支持，让 `--test-mode business-import` 能被正常解析，并能传递给 run_tests.sh。

## 修改范围

允许修改：

- ai/scripts/hermes_orchestrator.py
- ai/scripts/select_test_profile.py，如 orchestrator 依赖它限制 test mode
- ai/scripts/acceptance_judge.py，如有必要

禁止修改：

- 后端业务代码
- 前端业务代码
- trial_sample 脚本
- tests/business_acceptance 业务导入逻辑
- .env、token、auth.json
- 自动 commit / push / deploy

## 功能要求

1. `python ai/scripts/hermes_orchestrator.py run --help` 中能看到 business-import。
2. `--test-mode business-import` 不再被 argparse 拦截。
3. orchestrator 调用 run_tests.sh 时，实际传入的 mode 必须是 business-import，而不是 smoke。
4. 不影响 auto / smoke / full 既有模式。
5. 本轮不要求新增业务功能。

## 验收命令

python -m compileall -q ai/scripts
python ai/scripts/hermes_orchestrator.py run --help | grep business-import
bash ai/scripts/run_tests.sh ai/reports/manual business-import
python ai/scripts/hermes_orchestrator.py run --mode safe --test-mode business-import --skip-codex --skip-review
--max-repair-rounds 1

## 交付要求

输出修改文件清单、测试结果、是否满足验收标准。