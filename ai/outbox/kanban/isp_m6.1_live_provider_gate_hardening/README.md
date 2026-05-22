# ISP-M6.1 完整修补文件 — 请复制以下内容到目标文件
# 目标: backend/app/domains/business_analysis/services/inventory_sales_production/m6_live_provider_gate.py
# 分支: feature/isp-m6.1-live-provider-gate-hardening
# 基础: agent/bp-main (已含 Fix 2 - try-except in generate)
#
# 本文件包含两个额外修改:
#   Fix 1 (行 ~1189): _provider_gate_from_probe_result fail-closed
#   Fix 3 (行 ~796): ReadonlyMiddleDbShadowExecutor 只读保护
#
# 由于终端工具不可用（cwd 丢失），请手动应用或使用以下命令:
#   cd /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai
#   git checkout feature/isp-m6.1-live-provider-gate-hardening
#   然后根据 ai/outbox/kanban/isp_m6.1_live_provider_gate_hardening/m6.1-fixes.patch 应用修改
