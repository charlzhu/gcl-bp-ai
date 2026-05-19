已完成修复，未 commit / push / deploy，未触碰 `.env`、密钥、账号或 token。

修改了：

- [data_qa_planner.py](/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/backend/app/domains/logistics/services/data_qa_planner.py:97)：新增受控字段映射，`经营计划/经营计划部 -> expand_dept`，`刘娟 -> entrusted_person`；未知“用车”范围词返回 `field_scope_mapping` 澄清。
- [data_qa_repository.py](/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/backend/app/domains/logistics/repositories/data_qa_repository.py:2497)：`sys_total_fee_by_filters` 新增 `expand_dept`、`entrusted_person` 参数，并用 SQL 参数绑定下推。
- [data_qa_service.py](/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/backend/app/domains/logistics/services/data_qa_service.py:2119)：透传字段过滤，并在摘要中展示 `扩充部门=...`、`委托人=...`。
- [codex_result.md](/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/ai/tasks/running/TASK-logistics-entruster-dept-field-clarification/codex_result.md:1)：已写入执行摘要。

验证结果：

```bash
PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_field_scope_clarification.py --tb=short
# 5 passed in 0.65s

PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_system_sync_normalization.py --tb=short
# 2 passed in 0.25s

python -m py_compile backend/app/domains/logistics/services/data_qa_planner.py backend/app/domains/logistics/services/data_qa_service.py backend/app/domains/logistics/repositories/data_qa_repository.py
# passed
```

附加合并回归已尝试，其中 `test_logistics_e2e_failure_repair_round1.py` 有 16 个用例因当前沙箱禁止连接本地 MySQL `127.0.0.1` 失败，错误为 `PermissionError: [Errno 1] Operation not permitted`，不是业务断言失败。同步归一化测试单独通过。

保留了旧 `special_scope` 兼容能力；本次反馈场景已经改走字段过滤，不影响 Plan BOM、前端或物流同步归一化用例。

