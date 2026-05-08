# TASK-plan-power-m2-model-versioning 计划

## 当前仓库已完成能力判断

1. 已有 PlanBom 基础链路：Excel BOM 导入、BOM 明细查询、compare、PlanBom QA、NLU、答案表达层。
2. 已有 Alembic 迁移目录和计划 BOM ORM 集中在 `backend/app/domains/plan_bom/models.py`。
3. M1/M1.5 已完成 Excel 审计与业务口径固化：新版 TOPCon xlsm 为主目标，`formula_policy = semantic_fixed_mode`。
4. 当前尚无 `plan_power_*` ORM、迁移、功率 Excel 解析服务、模型版本管理服务和功率模型管理 API。

## 当前未完成能力判断

1. 不能导入功率预测 xlsm 生成模型版本。
2. 不能结构化查询模型 sheet、配置项、供应商效率分布、功率档、标板基准和 parse issue。
3. 不能激活/切换 active 功率模型版本。
4. 尚未实现 M3 计算引擎、M4 BOM 配置映射、M5 QA/前端接入。

## 本次任务与当前仓库状态一致性

一致。用户已确认进入 M2；`docs/NEXT_TASK.md` 明确 M2 可以新增 ORM、迁移、解析服务、模型版本服务和内部管理 API，但禁止越界进入 M3/M4/M5。

## 本轮允许修改范围

- `backend/app/domains/plan_bom/models.py`
- `backend/alembic/versions/*plan_power*.py`
- `backend/app/domains/plan_bom/services/power_excel_parser_service.py`
- `backend/app/domains/plan_bom/services/power_model_service.py`
- `backend/app/domains/plan_bom/repositories/power_model_repository.py`（如需要）
- `backend/app/domains/plan_bom/schemas/power_model.py`
- `backend/app/domains/plan_bom/api/endpoints/power_model.py`
- `backend/app/domains/plan_bom/api/router.py`
- `backend/app/api/deps.py`
- `tests/business_acceptance/test_plan_power_m2_model_versioning.py` 或等价测试文件
- `ai/tasks/running/TASK-plan-power-m2-model-versioning/*` 任务产物

## 本轮禁止修改范围

1. 不修改前端。
2. 不接入 `PlanBomQaService`、`/smart-chat` 或现有 QA 可答逻辑。
3. 不实现正式功率预测计算引擎。
4. 不实现 BOM 配置自动映射。
5. 不 hardcode `BOM配置搭配问询：.docx` 假订单/假版型/假项目/假答案。
6. 不修改 `.env`、密钥、真实生产连接配置。
7. 不自动 commit、push、deploy。
8. 不覆盖、重命名、删除 `ai/inbox/attachments/` 原始附件。
9. 不修改当前已存在的 logistics 相关脏工作区文件。

## M2 实施拆解

1. 先写 M2 单测：解析新版 xlsm、保存 `formula_policy`、记录 R30/R32 issue、记录异常供应商标题、hash 去重、active 切换。
2. 新增 `plan_power_*` ORM 与 Alembic 迁移。
3. 新增 `PowerExcelParserService`：只读解析 xlsm，不执行 VBA，固定锚点校验，输出内存结构和 warnings/issues。
4. 新增 `PowerModelRepository/PowerModelService`：防重复导入、落库、查询版本列表/详情、激活版本。
5. 新增内部管理 API：导入、版本列表、版本详情、激活。
6. 运行编译、pytest、必要时前端 build 作为回归确认。
7. 生成 diff/test/final acceptance 产物并执行 reviewer 审查。

## 验收标准

1. 新版 `GCL功率测试基准（V2.1）TOPCon 26.04.13.xlsm` 可被解析并生成一个模型版本。
2. 入库版本保存 `formula_policy = semantic_fixed_mode` 和文件 SHA256。
3. 解析到 12 个 Sheet、10 个模型页。
4. 可查询 sheet、配置项、供应商效率分布、功率档、标板基准、parse issues。
5. 记录 `NT12R-66GDF!R30/R32` semantic fix issue。
6. 记录异常供应商标题（例如 0、#REF!、厂家占位）为 warning/issue。
7. 同一文件 hash 重复导入不新增重复版本。
8. active 版本切换保证最多一个 active。
9. 现有 BOM/物流测试不被破坏。
10. M2 不越界实现 M3/M4/M5。
