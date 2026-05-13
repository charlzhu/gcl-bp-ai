# TASK-query-planning-v2-phase4 Final Acceptance

## 1. 本轮范围

分支：`agent/TASK-ai-answer-experience-v2`

本轮只做 Query Planning V2 Phase 4 的受控 shadow 接入与审计增强：

1. Query Planning V2 诊断接口增加内部访问保护。
2. 新增 Query Planning V2 shadow 对比报表服务与接口。
3. 物流 Data QA 写入 `sys_query_log.request_payload` 时追加 `query_plan_v2_shadow`。
4. Plan BOM QA 写入 `sys_query_log.request_payload` 时追加 `query_plan_v2_shadow`。
5. shadow 元数据覆盖 DIRECT / CLARIFY / UNSUPPORTED / NO_ANSWER / QUERY_DECOMPOSITION 等策略，但不替换正式查询执行结果。

本轮未做：

- 未让 LLM 生成 SQL。
- 未让 LLM 查数。
- 未让 LLM 生成最终事实答案。
- 未替换物流 `data-qa` 主链路。
- 未替换 BOM QA 主链路。
- 未引入临时 token / admin header。

## 2. 修改文件

### 后端依赖与路由

- `backend/app/api/deps.py`
  - 新增 `require_query_planning_internal_access`：`APP_ENV=prod` 时阻断 Query Planning V2 内部诊断接口，等待正式用户权限模块接管。
  - 新增 `get_query_planning_v2_shadow_report_service`。
- `backend/app/domains/query_planning/api/endpoints/query_plan_v2.py`
  - `/query-planning/v2/diagnose` 增加内部保护依赖。
  - 新增 `/query-planning/v2/shadow-report` 内部 shadow 报表接口。

### Query Planning V2 新增服务

- `backend/app/domains/query_planning/services/shadow_snapshot_builder.py`
  - 从物流/BOM 正式响应构建 `query_plan_v2_shadow`，只做审计元数据，不重新查库、不重新执行。
- `backend/app/domains/query_planning/services/shadow_report_service.py`
  - 内置 10 类物流/BOM shadow 用例。
  - 输出期望策略与实际 query_plan 的对比报表。
- `backend/app/domains/query_planning/services/__init__.py`
  - 导出新增服务。

### 物流 / BOM 历史日志

- `backend/app/domains/logistics/services/data_qa_service.py`
  - `_write_history_snapshot` 写入 `query_plan_v2_shadow`。
  - `response_meta` 增加 `query_plan_v2_strategy`、`query_plan_v2_query_key`、`query_plan_v2_shadow_ready`。
- `backend/app/domains/plan_bom/services/qa_service.py`
  - `_write_history_snapshot` 写入 `query_plan_v2_shadow`。
  - `response_meta` 增加 `query_plan_v2_strategy`、`query_plan_v2_query_key`、`query_plan_v2_shadow_ready`。

### 测试

- `tests/unit/query_planning/test_query_planning_phase4.py`
  - RED/GREEN 覆盖内部访问保护、物流 sys_query_log shadow 写入、BOM sys_query_log shadow 写入、10 类 shadow 报表。
- `tests/unit/query_planning/test_query_planning_endpoint_registration.py`
  - 补充 shadow report 路由注册断言。

### 验收材料

- `ai/tasks/running/TASK-query-planning-v2-phase4/diff.patch`
- `ai/tasks/running/TASK-query-planning-v2-phase4/test.log`
- `ai/tasks/running/TASK-query-planning-v2-phase4/review-result.json`
- `ai/tasks/running/TASK-query-planning-v2-phase4/final-acceptance.md`

## 3. TDD 记录

### RED

新增 `tests/unit/query_planning/test_query_planning_phase4.py` 后先运行失败：

```text
ImportError: cannot import name 'require_query_planning_internal_access' from 'backend.app.api.deps'
1 error in 1.08s
```

### GREEN

实现内部保护、shadow snapshot builder、shadow report service、接口与日志接入后：

```text
python -m pytest tests/unit/query_planning/test_query_planning_phase4.py -q
....                                                                     [100%]
4 passed in 1.03s
```

## 4. 验证结果

### Focused

```text
python -m pytest tests/unit/query_planning -q
..................                                                       [100%]
18 passed in 1.02s
```

```text
python -m pytest tests/unit/query_planning tests/business_acceptance/test_plan_power_m2_model_versioning.py::test_plan_power_write_access_allows_non_prod_and_blocks_prod_until_user_permission_module -q
...................                                                      [100%]
19 passed in 0.98s
```

### Compile

```text
python -m compileall -q backend/app/api/deps.py backend/app/domains/query_planning backend/app/domains/logistics/services/data_qa_service.py backend/app/domains/plan_bom/services/qa_service.py
```

结果：通过，无输出。

### Static scan

新增差异行扫描 hardcoded secret / shell injection / eval / pickle / SQL string-format：无命中。

`ruff`：当前环境未安装，未作为阻塞项。

```text
/opt/anaconda3/bin/python: No module named ruff
```

### Full regression

```text
python -m pytest tests -q
192 passed, 2 warnings in 26.76s
```

两个 warning 均来自既有 `openpyxl` 对 xlsm 扩展/条件格式的提示，不是本轮新增失败。

## 5. 独立 Review

Reviewer 结论：通过。

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": [],
  "summary": "已审查 scoped patch 与测试日志，未发现阻塞性安全或逻辑问题，生产诊断接口在 prod 环境被拒绝且未引入临时 token，shadow 元数据写入不改变正式结果；未修改任何文件。"
}
```

非阻塞建议已记录在 `review-result.json`：后续可补充 TestClient 级 403、真实服务注入可观测 adapter 的 no-execution 证明、异常路径专项测试。

## 6. 风险与边界

1. 当前 Query Planning V2 仍为 shadow / diagnostic，不替代正式物流或 BOM 查询执行链路。
2. `/query-planning/v2/diagnose` 与 `/query-planning/v2/shadow-report` 在非生产环境可用；生产环境当前 fail closed，后续需接入正式用户权限模块。
3. `query_plan_v2_shadow` 写入位于既有查询历史快照内，不新增数据库表、不改表结构。
4. shadow report 默认用例只包含问法、期望策略、期望 intent/query_key，不包含硬编码答案和业务数字。
5. 当前报表的真实匹配率受现有 planner/NLU 能力影响；它用于诊断差距，不代表已全面接管主链路。

## 7. 是否影响现有能力

- 物流 Data QA 主链路：不替换、不改变查询执行；仅在历史日志 payload 中追加 shadow 元数据。
- Plan BOM QA 主链路：不替换、不改变查询执行；仅在历史日志 payload 中追加 shadow 元数据。
- Guardrail：继续有效；新增 shadow builder 只复用既有结果和 Guardrail/NLU 快照。
- LLM：仍不能生成 SQL、不能查数、不能生成最终事实答案。

## 8. 结论

Query Planning V2 Phase 4 当前实现满足本轮验收标准：内部诊断受保护、query_plan_v2 可审计写入、10 类 shadow 报表可回放，且全量测试通过。建议进入下一步前，由用户确认是否继续补充 reviewer 的非阻塞增强测试，或推进下一阶段更受控的灰度接入。
