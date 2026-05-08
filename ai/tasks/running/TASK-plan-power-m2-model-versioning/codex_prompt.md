你是受控 Codex 工程师，当前任务是实现 gcl-bp-ai 项目的 M2：计划 BOM 功率模型版本化入库。

工作目录：/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai
当前分支应为：agent/TASK-plan-power-m2-model-versioning

【必须先读取】
1. AGENTS.md
2. docs/NEXT_TASK.md
3. docs/CURRENT_STATUS.md
4. docs/PLAN_POWER_BUSINESS_CONFIRMATION.md
5. docs/PLAN_POWER_EXCEL_FORMULA_AUDIT.md
6. docs/PLAN_POWER_IMPLEMENTATION_PLAN.md
7. ai/inbox/attachments_manifest.md
8. ai/tasks/running/TASK-plan-power-m2-model-versioning/plan.md
9. backend/app/domains/plan_bom/models.py
10. backend/app/domains/plan_bom/api/router.py
11. backend/app/api/deps.py
12. backend/alembic/versions/*.py

【重要脏工作区保护】
开始前运行 git status。当前已有与本轮无关的 logistics 修改/未跟踪文件，不能改动、格式化、回滚、删除这些文件：
- backend/app/domains/logistics/repositories/data_qa_repository.py
- backend/app/domains/logistics/services/data_qa_planner.py
- backend/app/domains/logistics/services/sync_service.py
- tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py
- tests/business_acceptance/test_logistics_system_sync_normalization.py
- ai/eval/runs/run_20260507_001940_full_all/logistics_planner_clarification_scan_after_fix_round5.md

【本轮目标】
实现 M2 功率模型版本化入库：把新版 xlsm 解析成可追溯、可查询、可激活的结构化模型版本。主文件：
ai/inbox/attachments/GCL功率测试基准（V2.1）TOPCon 26.04.13.xlsm

【允许修改】
- backend/app/domains/plan_bom/models.py
- backend/alembic/versions/*plan_power*.py
- backend/app/domains/plan_bom/services/power_excel_parser_service.py
- backend/app/domains/plan_bom/services/power_model_service.py
- backend/app/domains/plan_bom/repositories/power_model_repository.py
- backend/app/domains/plan_bom/schemas/power_model.py
- backend/app/domains/plan_bom/api/endpoints/power_model.py
- backend/app/domains/plan_bom/api/router.py
- backend/app/api/deps.py
- tests/business_acceptance/test_plan_power_m2_model_versioning.py
- ai/tasks/running/TASK-plan-power-m2-model-versioning/codex_final.md（最终总结）

【禁止修改/禁止行为】
1. 不修改 frontend。
2. 不修改 PlanBom QA 可答逻辑，不接入 /smart-chat。
3. 不实现正式功率预测计算引擎、推荐服务、BOM 配置映射。
4. 不 hardcode BOM配置搭配问询.docx 中假数据。
5. 不修改 .env/密钥/账号/token，不连接生产库。
6. 不覆盖/重命名/删除 ai/inbox/attachments 原始附件。
7. 不自动 commit/push/deploy。
8. 不动 logistics 既有脏文件。

【实现要求】
A. ORM + 迁移
新增以下表（字段可按项目风格略作调整，但必须覆盖语义）：
1. plan_power_model_version：文件名、hash、source_type=xlsm、business_version_label、formula_policy、is_active、parse_status、sheet_count、model_sheet_count、warning_count、error_count、parse_summary_json、warning_json、created_at、activated_at。
2. plan_power_model_sheet：version_id、sheet_name、normalized_model_code、cell_count、base_power、center_power_cell、area_default、std_dev_default、source_range、raw_meta_json。
3. plan_power_factor_option：version_id、sheet_id、factor_key、option_label、normalized_option_label、effect_value、area_value、std_dev_value、source_cell_ref、is_default、is_valid、invalid_reason、raw_json。
4. plan_power_supplier_efficiency_distribution：version_id、sheet_id、supplier_name、normalized_supplier_name、efficiency_value、ratio_value、source_cell_ref、is_valid、invalid_reason。
5. plan_power_power_bin：version_id、sheet_id、power_bin、bin_order、source_cell_ref、is_valid。
6. plan_power_benchmark_factor：version_id、model_code、benchmark_name、normalized_benchmark_name、effect_value、source_sheet_name、source_cell_ref、raw_json。
7. plan_power_model_validation_case：预留 M3 parity 字段，可简化但需建表。
8. plan_power_parse_issue：version_id、sheet_id nullable、level、issue_code、message、source_sheet_name、source_cell_ref、raw_json。

B. PowerExcelParserService
新增 backend/app/domains/plan_bom/services/power_excel_parser_service.py。
职责：
1. 只读读取 xlsm，使用 openpyxl load_workbook(..., keep_vba=True, data_only=False)，不执行 VBA。
2. 校验文件含 xl/vbaProject.bin。
3. 校验 12 个 sheet = 10 个模型页 + 标板基准 + 更改履历；模型页使用审计文档中的名称，注意 NT12R-78GDF 末尾空格。
4. 校验模型页锚点 A3/A6/A9/A12/A17/A20/A23/A26/A76。
5. 提取配置项选项和影响值：上方配置区 A1:Y27，按锚点分组；可以保守解析为 factor_key + option_label + effect_value + source_cell_ref，不能伪造。
6. 提取功率档 K28:T28（空/无效跳过，48/54 系列可只有 8 档）。
7. 提取供应商效率分布区 C77:Y96：识别供应商标题、效率段、比例；无效供应商标题如 0/#REF!/厂家X 记录 issue/warning，不作为有效供应商。
8. 提取标板基准页 A1:E10，支持新增“功率最优”列，保存 benchmark factor。
9. 识别并记录 semantic fix issue：新版仍有 NT12R-66GDF!R30 和 NT12R-66GDF!R32 疑似 L行-$S$28 引用，记录 issue_code=SEMANTIC_FORMULA_FIX_REQUIRED，formula_policy=semantic_fixed_mode。
10. 输出内存解析结构，供 service 落库。
11. 所有新增/修改函数写中文注释，说明功能、参数、返回值、关键业务逻辑。

C. PowerModelService + Repository
1. 按 file_hash 防重复导入：同一 hash 已存在则返回 existing，不新增版本。
2. 创建模型版本和所有解析子记录。
3. 查询版本列表、版本详情。
4. 激活版本时保证最多一个 active 版本。
5. 入库 formula_policy 固定 semantic_fixed_mode。
6. 事务失败必须 rollback。

D. API
新增 backend/app/domains/plan_bom/api/endpoints/power_model.py 并在 plan_bom/api/router.py 注册。
接口建议：
1. POST /api/v1/plan-bom/power-model/import：上传 xlsm 并解析入库。
2. GET /api/v1/plan-bom/power-model/versions：版本列表。
3. GET /api/v1/plan-bom/power-model/versions/{id}：版本详情。
4. POST /api/v1/plan-bom/power-model/versions/{id}/activate：激活版本。
返回统一 ApiResponse。不要接入 QA。

E. Tests（必须 TDD 思路，至少新增单测）
新增 tests/business_acceptance/test_plan_power_m2_model_versioning.py，使用 SQLite in-memory 或临时 DB，Base.metadata.create_all 直接建表，不连接真实 MySQL。
至少覆盖：
1. 解析新版 xlsm：sheet_count=12，model_sheet_count=10。
2. formula_policy = semantic_fixed_mode。
3. 记录 NT12R-66GDF!R30/R32 semantic issue。
4. 解析出功率档、供应商效率分布、标板基准。
5. 异常供应商标题 issue/warning 存在。
6. 同文件 hash 去重。
7. active 版本切换最多一个 active。
8. 不执行 VBA：只检查存在 vbaProject.bin，不调用任何宏。

【必须运行并把结果写入 codex_final.md】
- PYTHONPATH=. pytest tests/business_acceptance/test_plan_power_m2_model_versioning.py -q
- PYTHONPATH=. pytest tests -q
- python -m compileall backend/app scripts
如遇前端未修改可不跑 npm build，但 codex_final.md 中要说明 M2 未修改前端。

【最终输出文件】
写入 ai/tasks/running/TASK-plan-power-m2-model-versioning/codex_final.md，包含：
1. 修改文件列表。
2. 新增表和迁移说明。
3. 解析 Excel 文件名和 hash。
4. 解析到的 sheet/model/config/power_bin/supplier/benchmark/issue 摘要。
5. 测试命令和真实执行数量/结果。
6. 是否遵守 M2 边界。
7. 未 commit/push/deploy 声明。

请直接实施，不要提问。