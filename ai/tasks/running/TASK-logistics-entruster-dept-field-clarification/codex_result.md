# Codex 执行结果

## 结论

已修复物流问答中“经营计划 + 刘娟 + 用车总费用”被旧 `special_scope=planning` 吞掉委托人条件的问题。

当前规则：

- `经营计划` / `经营计划部` 优先映射为 `expand_dept` 字段过滤。
- `刘娟` 优先映射为 `entrusted_person` 字段过滤。
- 两者同时出现时走 `sys_total_fee_by_filters`，并叠加下推 `expand_dept` 与 `entrusted_person`。
- 未受控的人名/业务词，例如 `26年 张三 用车总费用是多少`，返回 `clarification_category=field_scope_mapping`，要求用户确认字段口径，不默认查全量、不套用旧特殊口径。

## 修改文件

- `backend/app/domains/logistics/services/data_qa_planner.py`
- `backend/app/domains/logistics/services/data_qa_service.py`
- `backend/app/domains/logistics/repositories/data_qa_repository.py`

未修改 `.env`、密钥、账号、token、前端、Plan BOM、历史旧任务文件；未执行 commit / push / deploy。

## 关键改动

- planner 新增 2026 系统总费用受控字段映射，优先于旧 `special_scope`。
- planner 新增未知字段口径澄清：未知“用车”范围词不再被宽松承运商抽取吞掉。
- repository `sys_total_fee_by_filters` 新增 `expand_dept`、`entrusted_person` 参数，并使用 SQL 参数绑定：
  - `st.expand_dept = :expand_dept`
  - `st.entrusted_person = :entrusted_person`
- service 透传字段过滤参数，并在摘要中展示：
  - `扩充部门=...`
  - `委托人=...`
- service 计算逻辑中补充字段过滤说明，保留旧 `special_scope` 兼容分支。

## 验证

已通过：

```bash
PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_field_scope_clarification.py --tb=short
```

结果：

```text
5 passed in 0.65s
```

已通过：

```bash
PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_system_sync_normalization.py --tb=short
```

结果：

```text
2 passed in 0.25s
```

已通过：

```bash
python -m py_compile backend/app/domains/logistics/services/data_qa_planner.py backend/app/domains/logistics/services/data_qa_service.py backend/app/domains/logistics/repositories/data_qa_repository.py
```

附加回归命令已尝试：

```bash
PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py tests/business_acceptance/test_logistics_system_sync_normalization.py --tb=short
```

结果：`test_logistics_system_sync_normalization.py` 的 2 个用例通过；`test_logistics_e2e_failure_repair_round1.py` 中 16 个用例在初始化真实 MySQL 会话时失败，根因是当前沙箱网络禁止连接 `127.0.0.1`：

```text
PermissionError: [Errno 1] Operation not permitted
pymysql.err.OperationalError: (2003, "Can't connect to MySQL server on '127.0.0.1'")
```

该失败不是本次业务断言失败。

## 风险与未完成项

- 当前只把业务确认过的 `经营计划/经营计划部`、`刘娟` 作为受控字段映射；更多扩充部门、委托人、客户、承运商别名需要业务确认后再加入映射。
- 需要真实 MySQL 的 `test_logistics_e2e_failure_repair_round1.py` 在当前沙箱不能完整验证，需在允许访问本地数据库的环境复跑。

## 影响范围

- 影响物流 data-qa 的 2026 系统总费用字段过滤路径。
- 保留旧 `sys_special_total_fee` / `special_scope` 兼容能力。
- 不影响现有 Plan BOM、前端、物流同步归一化用例。
