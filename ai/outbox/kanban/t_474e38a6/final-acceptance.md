# M13 验收材料

## 1. 修改文件清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `scripts/dev/run_logistics_nl2sql_m9_provider_smoke.py` | 修改 | 扩展 Live Provider Smoke 从 4→6 样本（M11-1） |
| `backend/app/domains/logistics/services/nl2sql/sql_execution.py` | 修改 | 添加 execute_timeout + _run_with_timeout（M11-4） |
| `backend/app/domains/logistics/services/nl2sql/m10d_shadow_gate.py` | 修改 | 静默 fallback → 显式 RuntimeError（M12-2） |
| `tests/unit/logistics/nl2sql/test_m10d_shadow_gate.py` | 修改 | 适配 fallback 行为变更 |

### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/app/domains/logistics/services/nl2sql/m10d_explain_classifier.py` | M11-2 EXPLAIN 分类器 |
| `backend/app/domains/logistics/services/nl2sql/m11_joint_runner.py` | M11-3 联合 Runner |
| `backend/app/domains/logistics/services/nl2sql/m12_unified_report.py` | M12-1 统一评估报告渲染器 |
| `tests/unit/logistics/nl2sql/test_m10d_explain_classifier.py` | M11-2 聚焦测试 17个 |
| `tests/unit/logistics/nl2sql/test_m11_timeout_execution.py` | M11-4 聚焦测试 5个 |
| `tests/unit/logistics/nl2sql/test_m11_joint_runner.py` | M11-3 聚焦测试 4个 |
| `tests/unit/logistics/nl2sql/test_m12_unified_report.py` | M12-1 聚焦测试 7个 |
| `docs/NL2SQL_LOGISTICS_QA_SIDECAR_DESIGN.md` | M12-3 QA Sidecar 设计文档 |
| `ai/outbox/nl2sql-m11-design-audit/design-audit.md` | M11-0 设计审计 |
| `ai/outbox/nl2sql-m12-boundary-cleanup/boundary-cleanup-checklist.md` | M12-2 边界清理清单 |

## 2. 测试结果

```
全量 NL2SQL 回归: 325 passed, 9 warnings
物流正式 QA + Query Planning 回归: 431 passed, 9 warnings
```

## 3. 关键业务口径

所有改动遵循：
- shadow-only：不替换正式物流 QA 主链路
- 默认关闭：gate/adapter 默认 disabled
- 脱敏合规：report/response_meta 不输出 SQL/表名/字段名/参数值
- 不影响现有物流/BOM/功率预测/产销存能力

## 4. 风险点

| 风险 | 缓解措施 |
|------|----------|
| real_db 加载失败从静默 fallback 改为显式 RuntimeError | 生产环境有配置时不会触发；测试已适配新行为 |
| Live Provider Smoke 需要真实 provider | 配置缺失时 fail-closed 为 BLOCKED，不伪造通过 |
| QA Sidecar 设计文档的设计需要人工确认后才进入 M13 实现 | 当前文档仅为设计，未实现 |

## 5. 未修改或影响

- 物流正式 QA 主链路（不改）
- 计划 BOM / 功率预测（不改）
- 产销存经营分析（不改）
- 物管 SAP MID（不改）
- .env / 密钥 / 连接串（不改）
- main 分支（不改）
- 未 commit / push / deploy

## 6. 当前 worktree 分支

```
feature/nl2sql-m11
```

基线分支 `agent/bp-main` 已 rebase 到最新。
