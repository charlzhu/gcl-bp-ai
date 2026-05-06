cat > ai/inbox/requirement.md <<'EOF'
# 需求：P2.1.1 补齐 business-oracle 在 hermes_orchestrator 中的接入

## 背景

当前 P2.1 已完成物流 Oracle Engine 数据源路由框架：

- `scripts/business_acceptance_oracle_engine.py` 已存在
- `tests/business_acceptance/oracle/` 已存在
- `ai/scripts/run_tests.sh` 已支持 `business-oracle`
- 手动执行 `bash ai/scripts/run_tests.sh ai/reports/manual business-oracle` 可以通过

但 `ai/scripts/hermes_orchestrator.py` 的 `--test-mode` 参数 choices 目前只包含：

- auto
- smoke
- full
- business-import

尚未包含：

- business-oracle

导致无法通过 orchestrator 统一调度 business-oracle 验收。

## 目标

只补齐 `business-oracle` 在 `hermes_orchestrator.py` 中的 test-mode 接入，不修改 Oracle Engine 业务逻辑。

## 允许修改

- `ai/scripts/hermes_orchestrator.py`
- `ai/scripts/select_test_profile.py`，如存在 test mode 白名单限制
- `docs/BUSINESS_ACCEPTANCE_FRAMEWORK.md`，如需要补充命令说明

## 禁止修改

- 后端业务 service
- 前端页面
- 物流 Oracle Engine 计算逻辑
- trial_sample 既有脚本
- 数据库结构
- 生产数据
- `.env`
- token
- auth.json
- 自动 commit / push / deploy

## 功能要求

1. `python ai/scripts/hermes_orchestrator.py run --help` 中能看到 `business-oracle`。
2. `--test-mode business-oracle` 不再被 argparse 拦截。
3. orchestrator 调用 `run_tests.sh` 时，实际传入的 mode 必须是 `business-oracle`。
4. 不影响 `auto`、`smoke`、`full`、`business-import` 既有模式。
5. 本轮不新增业务功能，不扩展 Excel/MySQL 计算逻辑。

## 验收命令

```bash
python -m compileall -q ai/scripts
python ai/scripts/hermes_orchestrator.py run --help | grep business-oracle
bash ai/scripts/run_tests.sh ai/reports/manual business-oracle
python ai/scripts/hermes_orchestrator.py run --mode safe --test-mode business-oracle --skip-codex --skip-review --max-repair-rounds 1