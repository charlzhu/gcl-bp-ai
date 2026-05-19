# NL2SQL Logistics M9 SQLPlan Generation Shadow MVP Plan

## 背景

M8 已验证物流 NL2SQL 的后半段 shadow-only 安全评估骨架：受控 SQLPlan candidate、确定性 validator、renderer、SQL safety、fake executor / 只读 smoke runner、脱敏评估日志与报表。

但 M8 样例仍以人工注入 SQLPlan candidate 为主，尚未证明“自然语言问题 → SQLPlan candidate”的前半段链路。因此 M9 的目标是补齐 front-half shadow MVP：从物流自然语言问题出发，经过 Query Rewrite、Domain Router、Semantic Catalog recall/rerank、主 LLM SQLPlan Generator，再进入既有 M8 shadow pipeline。

## 用户确认口径

1. SQLPlan Generator 使用当前项目已配置的主 LLM（`settings.llm_base_url` / `settings.llm_api_key` / `settings.llm_model`），测试允许注入 fake client。
2. Embedding / Rerank 应真实可调用；失败时 fail-closed，不降级为未精排结果。
3. M9 阶段允许跑一次真实 reindex + recall smoke。
4. 物流自然语言 golden set 从已有物流回归题中抽取真实/半真实问题。
5. 进入 M10/M12 前的门槛：SQLPlan 结构合法率 ≥ 90%，高确定性问题结果一致率 ≥ 95%，安全违规 0 容忍，正式链路影响 0 容忍。
6. 只读中间库环境可连接正常使用。
7. “整体 NL2SQL 完成”定义为 C：主链路替换、NL2SQL 成为主要物流问答链路；但 M9 不做主链路替换。
8. M12 首批接管范围只限物流高确定性问题；复杂/多轮澄清在后续阶段扩展。
9. M9 允许真实调用 LLM / Embedding / Rerank。
10. SQL 自修复只允许修复 SQLPlan 结构/字段别名/类型等安全问题，不允许移除用户约束、绕过 validator/safety、改域/改源、替换不支持指标或让 LLM patch raw SQL。
11. examples 纳入 Semantic Catalog，但 examples 只保存“自然语言 → SQLPlan 形状”示例，不保存 raw SQL。

## 本阶段范围

1. 新增 Query Rewrite 服务：
   - 保留 original_question；
   - 做最小同义词归一和默认时间口径提示；
   - 不删除用户显式约束；
   - 识别明显不支持口径（如吨数）并保留给后续 fail-closed。
2. 新增最小 Domain Router：
   - M9 只允许 logistics + middle_db + shadow；
   - BOM、功率、物管、经营分析、SAP/Oracle 直查请求必须 skip/fail-closed；
   - 不接正式 QA 主链路。
3. Semantic Catalog 增加 `examples.yaml`：
   - examples 进入 recall document builder；
   - examples 不包含 SQL 字符串、表名、字段名、连接信息或参数值；
   - examples 以 catalog refs、query_type、metrics、dimensions、rules 等结构提示 SQLPlan 形状。
4. 新增 SQLPlan Generator：
   - 使用当前主 LLM；
   - prompt 只允许返回严格 JSON object；
   - 只接受 `LogisticsSqlPlanCandidate` 结构；
   - 任意 raw SQL / where / table guess / answer / computed_value / markdown / 多余解释均 fail-closed；
   - 生成后必须交给现有 `LogisticsSqlPlanValidator` 校验。
5. 新增 M9 shadow runner：
   - 自然语言样例 → rewrite/router/recall/generator → shadow pipeline；
   - 输出脱敏 JSONL/Markdown；
   - 不暴露 SQL 原文、参数值、连接信息、host/user/password/DSN/API key；
   - 默认 fake client/fake executor 可跑单元测试；真实 provider smoke 通过脚本参数显式触发。

## 非范围

- 不替换正式物流 QA 主链路；
- 不把 NL2SQL 答案返回给用户；
- 不接前端；
- 不让 LLM 输出或执行 raw SQL；
- 不直接查询 SAP Oracle MID；
- 不修改 BOM、功率预测、物管正式链路；
- 不写入 `.env`、密钥或真实连接串；
- 不自动 commit / push / deploy。

## 验收测试

### RED/GREEN focused tests

```bash
backend/.venv/bin/python -m pytest tests/unit/logistics/nl2sql/test_m9_sqlplan_generation.py -q
```

### 既有 NL2SQL 回归

```bash
backend/.venv/bin/python -m pytest tests/unit/logistics/nl2sql -q
```

### M9 shadow runner fake smoke

```bash
backend/.venv/bin/python scripts/dev/run_logistics_nl2sql_m9_shadow_sqlplan_generation.py --artifact-dir ai/outbox/kanban/t_m9_nl2sql_shadow
```

### 真实 reindex + recall smoke（M9 允许，失败 fail-closed）

```bash
backend/.venv/bin/python scripts/reindex_logistics_nl2sql_catalog.py
backend/.venv/bin/python scripts/dev/run_logistics_nl2sql_m9_shadow_sqlplan_generation.py --artifact-dir ai/outbox/kanban/t_m9_nl2sql_shadow --live-provider-smoke --max-live-samples 1
```

## 验收指标

1. M9 单元测试通过。
2. M9 fake shadow runner 生成脱敏 JSONL/Markdown。
3. 结构合法率在 fake/golden 样例中可统计，目标 ≥ 90%。
4. 召回/精排不可用时 fail-closed，不进入 generator。
5. SQLPlan validator / SQL safety 继续 0 容忍。
6. 正式物流 QA 主链路影响为 0：本阶段不注册正式 API，不改变正式问答路径。
7. 输出验收材料：`diff.patch`、`test.log`、`review-result.json`、`final-acceptance.md`。