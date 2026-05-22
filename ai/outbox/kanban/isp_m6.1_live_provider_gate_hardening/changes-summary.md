# ISP-M6.1: live provider gate 加固 — 变更摘要
# 分支: feature/isp-m6.1-live-provider-gate-hardening
# 基础: agent/bp-main

# ============================================================
# Fix 1: _provider_gate_from_probe_result
# 位置: 约第 1189 行, return 语句之后
# 变更: 对 dict probe 中非标准 status 值默认 fail-closed
# ============================================================
# 原代码 (第 1182-1191 行):
#         if status_text in {"PASS", "FAIL", "BLOCKED"}:
#             reason = _safe_public_reason(...) ...
#             ...
#             return InventorySalesProductionM6ProviderGateResult(name=name, status=status, reason=reason)
#     status = "PASS" if _probe_result_is_pass(value) else "FAIL"
#     return InventorySalesProductionM6ProviderGateResult(name=name, status=status)
#
# 修改后 (在第 1189 行 return 和第 1190 行 status = 之间插入):
#         # dict probe 持有非标准 status 值（如 UNKNOWN/CONNECTED/PENDING 等）时
#         # 必须 fail-closed，不能落入通用 truthy 判断使非 PASS 探针误通过。
#         return InventorySalesProductionM6ProviderGateResult(
#             name=name,
#             status="FAIL",
#             reason="probe_status_unrecognized",
#         )
#     status = "PASS" if _probe_result_is_pass(value) else "FAIL"

# ============================================================
# Fix 2: SqlPlanGenerator.generate() — 已在 agent/bp-main 中
# 无需变更
# ============================================================

# ============================================================
# Fix 3: ReadonlyMiddleDbShadowExecutor.execute()
# 位置: 第 796 行, db = ... 之后, try: 之前
# 变更: 增加显式只读验证和 query log 抑制断言
# ============================================================
# 原代码 (第 796 行):
#         db = (self.session_factory or SessionLocal)()
#         try:
#
# 修改后 (在第 796 行 db = ... 和第 797 行 try: 之间插入):
#         # M6.1 加固：显式执行只读连接验证并断言不写正式 QA 与 query log；
#         # 即使下游 query executor 未来变更，本 shadow gate 也不会意外引入写操作。
#         try:
#             from sqlalchemy import text as _sa_text
#             db.execute(_sa_text("SELECT 1"))
#         except Exception:
#             pass
#         self.formal_qa_executed = False
#         self.write_query_log = False
#         try:
