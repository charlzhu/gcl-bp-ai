# 需求：优化 Hermes 自动化流水线执行速度

当前问题：
执行 `python ai/scripts/hermes_orchestrator.py run --mode safe` 时间较长。

优化目标：

1. 给 `hermes_orchestrator.py` 增加参数：
    - `--skip-tests`
    - `--skip-review`
    - `--test-mode smoke`
    - `--test-mode full`
2. 默认测试模式改为 smoke。
3. `run_tests.sh` 默认 smoke 模式，不再默认跑全量 `backend/tests`。
4. 如果本轮没有代码 diff，则自动跳过测试和 Reviewer。
5. 在 `hermes-run.log` 中记录每个阶段耗时：
    - safety_check
    - codex_fullstack
    - run_tests
    - collect_diff
    - codex_reviewer
    - final_report
6. 保持安全规则不变：
    - 不自动 commit
    - 不自动 merge
    - 不自动 push
    - 不自动部署
7. 修改后请运行：
    - `python ai/scripts/hermes_orchestrator.py run --skip-codex`
    - `bash ai/scripts/run_tests.sh ai/reports/manual smoke`

验收标准：

1. `--skip-tests` 时不运行 `run_tests.sh`。
2. `--skip-review` 时不调用 Codex Reviewer。
3. `--test-mode smoke` 时只跑 smoke 检查。
4. `--test-mode full` 时才跑全量测试。
5. 无代码 diff 时自动跳过测试与 Reviewer。
6. final-acceptance.md 中要显示本轮使用的参数和各阶段耗时。