# implementation-plan

## TDD 顺序

1. 新增 `tests/unit/logistics/nl2sql/test_candidate_sql_gate.py`，先写 RED 测试：合法 SELECT+LIMIT 通过；无 LIMIT、多语句、注释、非 SELECT、UNION/INTO OUTFILE/LOAD_FILE/SLEEP/BENCHMARK/FOR UPDATE/LOCK 拒绝；危险输入 reason 不回显完整 SQL。
2. 运行 RED：`backend/.venv/bin/python -m pytest tests/unit/logistics/nl2sql/test_candidate_sql_gate.py -q`，保存 `red-test.log`，预期因模块/功能缺失失败。
3. 新增最小 `candidate_sql_gate.py`：纯 shadow-only，不执行 SQL，不接主链路；用保守文本扫描实现 fail-closed，输出结构化 Pydantic 结果。
4. 如需对外使用，最小更新 `__init__.py` 导出，不改变现有调用链。
5. 运行 GREEN focused、Full focused、compileall、git diff --check，并保存日志。
6. 生成 `diff.patch`、`review.md`、`gate-summary.json`、`final-acceptance.md`。

## 设计边界

- 默认无 sqlglot；不安装依赖。
- M10-A 对 LIMIT 超上限先拒绝，不做下调。
- reason 只返回稳定业务安全说明和 reason code，不回显完整 SQL、不包含 host/user/password/DSN/API key。
- `repair_info` 默认为 `None`，仅在缺少/超限 LIMIT 等可修复场景给简短结构化提示。
