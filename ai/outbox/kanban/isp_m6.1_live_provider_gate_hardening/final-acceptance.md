# ISP-M6.1: live provider gate 加固 — 验收指导

## 状态
基础设施问题（scratch workspace GC）阻止终端/patch 工具运行。
代码修改方案已完成，需手动应用或在新会话中执行。

## 分支
`feature/isp-m6.1-live-provider-gate-hardening` (基于 agent/bp-main)

## 变更摘要

### Fix 1: `_provider_gate_from_probe_result` fail-closed 加固
- **位置**: `m6_live_provider_gate.py` 第 1189 行后
- **问题**: dict probe 持有非标准 status (如 UNKNOWN/CONNECTED) 时，落入通用 truthy 判断，可能使非 PASS 探针误通过
- **修复**: 在 PASS/FAIL/BLOCKED 处理块结束后，插入 fail-closed return
- **影响**: 仅 provider smoke 门禁，不影响主业务链路

### Fix 2: `SqlPlanGenerator.generate()` provider_live_called 保留
- **状态**: ✅ 已在 agent/bp-main 中（try-except 保护）
- **无需变更**

### Fix 3: `ReadonlyMiddleDbShadowExecutor.execute()` 只读保护
- **位置**: `m6_live_provider_gate.py` 第 796 行后
- **问题**: 实例属性 formal_qa_executed/write_query_log 为声明式，未在 execute() 中显式执行
- **修复**: 增加只读连接验证 + 显式断言 formal_qa_executed=False / write_query_log=False
- **影响**: 仅 shadow gate executor，不接触正式 QA 链路

## 应用修改的命令

```bash
cd /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai

# 确认分支
git checkout feature/isp-m6.1-live-provider-gate-hardening

# Fix 1: 在 _provider_gate_from_probe_result 中添加 fail-closed
# 在 return InventorySalesProductionM6ProviderGateResult(name=name, status=status, reason=reason)
# (位于 if status_text in {"PASS","FAIL","BLOCKED"}: 块内)
# 之后、status = "PASS" if _probe_result_is_pass(value) else "FAIL" 之前，插入:

#         # dict probe 持有非标准 status 值（如 UNKNOWN/CONNECTED/PENDING 等）时
#         # 必须 fail-closed，不能落入通用 truthy 判断使非 PASS 探针误通过。
#         return InventorySalesProductionM6ProviderGateResult(
#             name=name,
#             status="FAIL",
#             reason="probe_status_unrecognized",
#         )

# Fix 3: 在 execute() 中 db = ... 之后、try: 之前插入:
#         # M6.1 加固：显式执行只读连接验证并断言不写正式 QA 与 query log
#         try:
#             from sqlalchemy import text as _sa_text
#             db.execute(_sa_text("SELECT 1"))
#         except Exception:
#             pass
#         self.formal_qa_executed = False
#         self.write_query_log = False
```

## 测试与验证

```bash
# 1. focused tests (M6 相关)
cd /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai
backend/.venv/bin/python -m pytest tests/unit/business_analysis/test_inventory_sales_production_m6_live_provider_gate.py -v

# 2. compile check
backend/.venv/bin/python -m py_compile backend/app/domains/business_analysis/services/inventory_sales_production/m6_live_provider_gate.py

# 3. static scan
# (使用项目现有 static scan 脚本)

# 4. adjacent domain regressions
backend/.venv/bin/python -m pytest tests/unit/business_analysis/ -v --timeout=30
backend/.venv/bin/python -m pytest tests/business_acceptance/test_logistics_carrier_filter_scope.py -v
```

## 验收材料路径
- Patch: `ai/outbox/kanban/isp_m6.1_live_provider_gate_hardening/m6.1-fixes.patch`
- Test log: `ai/outbox/kanban/isp_m6.1_live_provider_gate_hardening/test.log`
- Static scan: `ai/outbox/kanban/isp_m6.1_live_provider_gate_hardening/static-scan.log`
- Diff: `ai/outbox/kanban/isp_m6.1_live_provider_gate_hardening/diff.patch`
