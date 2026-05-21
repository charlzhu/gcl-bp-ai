# t_df3a6b13 / M10-D2 — D2-2 完成：EXPLAIN smoke runner

## 1. 结论

**M10-D2-2 阶段完成。** 新增了基于真实 `backend/.env` 配置的 M10-D EXPLAIN smoke runner，包含 CLI 入口脚本和完整的脱敏 artifact 输出。

## 2. 修改文件清单

### 新增文件

1. **`backend/app/domains/logistics/services/nl2sql/m10d2_explain_smoke.py`**
   - `LogisticsNl2SqlM10D2ExplainSmokeSample` — 存储 SQLPlan 已 render 的安全 SQL 的样例定义
   - `LogisticsNl2SqlM10D2ExplainSmokeOutcome` — 单条例样执行结果（含 gate report + 脱敏 record）
   - `LogisticsNl2SqlM10D2ExplainSmokeRunResult` — runner 总返回（含报表、artifacts 路径）
   - `build_default_logistics_nl2sql_m10d2_explain_smoke_samples()` — 默认 aggregate EXPLAIN 样例
   - `run_logistics_nl2sql_m10d2_explain_smoke()` — 核心 runner：读 env → 构建 M10D gate → 对每个样例跑 EXPLAIN → 写出脱敏 JSONL/Markdown artifact
   - 辅助函数：环境不可用 record 构造、脱敏、secret 过滤、artifact 写入

2. **`scripts/dev/run_logistics_nl2sql_m10d2_explain_smoke.py`**
   - CLI 入口：`--env-path` / `--artifact-dir`
   - 输出脱敏 JSON 摘要（不暴露 SQL/参数/密码）

### 修改文件

3. **`tests/unit/logistics/nl2sql/test_m10d_shadow_gate.py`**
   - D2-1 测试恢复：`test_m10d2_real_db_access_disabled_uses_fake_executor`、`test_m10d2_real_db_access_enabled_no_env_falls_back_to_fake`
   - D2-2 新增 3 个测试：
     - `test_m10d2_smoke_runner_env_unavailable_writes_deidentified_blocked_artifact`
     - `test_m10d2_smoke_runner_stub_executor_success_generates_deidentified_artifacts`
     - `test_m10d2_smoke_runner_stub_explain_failed_records_failure_without_leak`

4. **`backend/app/domains/logistics/services/nl2sql/m10d2_explain_smoke.py`**
   - 新增 `executor_factory` 参数：传入时使用工厂模式（不连真实库），不传时使用真实 `LogisticsReadonlyMiddleDbExecutor`

## 3. runner 设计要点

### 默认行为（生产 smoke）
```
env_path → load_readonly_middle_db_config()
  ├── 失败 → blocked artifact + return
  └── 成功 → LogisticsReadonlyMiddleDbExecutor(config)
              → 对每个 sample 创建 M10D shadow gate
              → gate.run(rendered_sql, real_db_access_enabled=True)
              → 写出脱敏 JSONL + Markdown
```

### stub 模式（单测传入 executor_factory）
```
env_path → load_readonly_middle_db_config()
  ├── 失败 → blocked artifact + return
  └── 成功 → 使用 executor_factory(config) 提供的 executor
              → gate.run(rendered_sql, real_db_access_enabled=False)  # 不改 env 实际连接
```

## 4. 安全脱敏保障

- runner 对所有 artifact record 做 **二次脱敏**：`redact_evaluation_text` + 自定义 `_sanitize_m10d2_text`
- 从 config 提取 `host`/`database`/`user`/`password`/`host:port` 全部替换为 `[REDACTED]`
- M10-D gate 报告本身不暴露 SQL、表名、字段名、参数值
- artifact 中 `description`、`warnings`、`question` 等文本字段过 `redact_evaluation_text`

## 5. 验证结果

| 测试范围 | 结果 |
|---------|------|
| D2-2 focused（3 个 smoke runner 测试） | **3 passed** |
| D1 + D2-1 + D2-2 focused 合计 | **13 passed** |
| NL2SQL unit 全量 | **239 passed, 9 warnings**（基线 236，新增 3 个） |

## 6. 关键改动说明

1. **smoke runner 不走 shadow pipeline**：直接使用 M10-D gate，绕过了 shadow pipeline 的 candidate gate 和 SQLPlan validation，直接处理已 render 的安全 SQL。
2. **executor_factory 控制模式**：传入时禁用 real_db_access，使用工厂模式；不传时自动使用 `LogisticsReadonlyMiddleDbExecutor` 连接真实中间库。
3. **env 缺失时 fail-closed**：不等 executor_factory，直接返回 blocked artifact。

## 7. 未完成项（留给后续子阶段）

1. D2-3: 接入 shadow pipeline（在正式 QA 链路中挂载 M10-D gate）
2. D2-4: 完整 outbox 材料（static scan、独立 review、final-acceptance.md 最终版）
3. timeout 真实中断语义（M10-D gate 当前使用 perf_counter 计时但不中断）

## 8. 对既有能力影响

- 物流问答主链路：未修改，无影响
- 计划 BOM / 功率预测 / 物管 / 前端：未修改，无影响
- D1/D2-1 fake executor gate：回归通过，无影响
- 未自动 commit / push / deploy
