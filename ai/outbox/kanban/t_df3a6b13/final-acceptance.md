# t_df3a6b13 / M10-D2 — D2 第一轮 TDD 完成

## 1. 结论

**M10-D2 第一轮 TDD 阶段完成。D2 验证通过，可收口本轮子阶段。**

本轮只在 `agent/bp-main` 基线的基础上增加了 `real_db_access_enabled` 字段和相关 fallback 保护，未连接真实数据库、未读取 `.env`、未接正式 QA 主链路。

## 2. 修改文件清单

### 代码

1. `backend/app/domains/logistics/services/nl2sql/m10d_shadow_gate.py`
   - `LogisticsNl2SqlM10DShadowGateConfig` 新增 `real_db_access_enabled: bool = False`
   - `LogisticsNl2SqlM10DShadowGateConfig` 新增 `env_path: str = ""`
   - `_build_execution_service()` 新增条件判断：
     - `real_db_access_enabled=True` 且 `env_path` 非空时，尝试加载只读中间库配置
     - 加载成功：构建 `LogisticsReadonlyMiddleDbExecutor` 作为真实 executor
     - 加载失败：静默 fallback 到 `executor_factory()` 提供的 executor
   - 文档注释修正为与实际 fallback 行为一致

2. `tests/unit/logistics/nl2sql/test_m10d_shadow_gate.py`
   - `test_m10d2_real_db_access_disabled_uses_fake_executor()` — 默认不连库保护验证
   - `test_m10d2_real_db_access_enabled_no_env_falls_back_to_fake()` — env 缺失时安全 fallback

### 验收材料

`ai/outbox/kanban/t_df3a6b13/`

- `diff_m10d_shadow_gate.patch`
- `diff_test.patch`

## 3. 验证结果

- **D2 focused**：2 passed
- **D1 + D2 focused 合计**：10 passed（8 D1 + 2 D2）
- **NL2SQL unit 全量**：`236 passed, 9 warnings`（D1 基线为 234，新增 2 个 D2 测试）
- **compile**：通过
- **diff-check**：通过
- **静态扫描**：`findings_count=0`，`static_scan_passed=true`
- **独立 review**：`passed=true`，`security_concerns=[]`，`logic_errors=[]`

## 4. 关键改动说明

D2 遵循 D0 设计，只做了以下最小增量：

1. 新增 `real_db_access_enabled` 配置，默认 False。
2. 新增 `env_path` 配置，用于指定 `backend/.env` 路径。
3. 在 `_build_execution_service()` 中优先检查真实库配置。
4. 条件同时满足时才尝试构建真实 executor；不满足时走原有 fake 路径。
5. 真实 executor 构造失败时静默 fallback，不会影响 gate 正常流程。

## 5. 未完成项（留给后续子阶段）

1. `real_db_access_enabled=True` + 有效 `env_path` 的 E2E smoke 测试（需要真实 `.env` 或 mock env）。
2. smoke runner 脚本 `scripts/dev/run_logistics_nl2sql_m10d2_explain_smoke.py`。
3. 脱敏 JSON/Markdown smoke report 输出。
4. D2 完整 outbox（test.log、static-scan.json、review-result.json 等）。
5. 接入 shadow pipeline 的集成点。
6. timeout 真实中断语义。

## 6. 对既有能力影响

- 物流问答主链路：未修改，无影响。
- 计划 BOM / 功率预测 / 物管 / 前端：未修改，无影响。
- D1 fake executor gate：未修改行为，回归通过。

## 7. 阶段边界

已遵守：
- 只做物流 NL2SQL。
- 默认不连库。
- 不查 SAP Oracle MID。
- 不接正式用户回答。
- 不改前端。
- 未自动 commit / push / deploy。
