# TASK-plan-power-m2-model-versioning Codex 最终总结

## 1. 修改文件列表

本轮按 M2 允许范围新增 / 修改：

1. `backend/app/domains/plan_bom/models.py`
2. `backend/alembic/versions/20260508_0004_create_plan_power_model_versioning.py`
3. `backend/app/domains/plan_bom/services/power_excel_parser_service.py`
4. `backend/app/domains/plan_bom/services/power_model_service.py`
5. `backend/app/domains/plan_bom/repositories/power_model_repository.py`
6. `backend/app/domains/plan_bom/schemas/power_model.py`
7. `backend/app/domains/plan_bom/api/endpoints/power_model.py`
8. `backend/app/domains/plan_bom/api/router.py`
9. `backend/app/api/deps.py`
10. `tests/business_acceptance/test_plan_power_m2_model_versioning.py`
11. `ai/tasks/running/TASK-plan-power-m2-model-versioning/codex_final.md`

未修改本轮禁止范围中的 PlanBom QA、`/smart-chat`、前端、正式计算引擎、BOM 配置映射、原始附件、密钥配置、部署配置。

## 2. 新增表和迁移说明

新增 Alembic 迁移：

```text
backend/alembic/versions/20260508_0004_create_plan_power_model_versioning.py
```

新增 8 张表：

1. `plan_power_model_version`
2. `plan_power_model_sheet`
3. `plan_power_factor_option`
4. `plan_power_supplier_efficiency_distribution`
5. `plan_power_power_bin`
6. `plan_power_benchmark_factor`
7. `plan_power_model_validation_case`
8. `plan_power_parse_issue`

迁移 `down_revision = 20260419_0003`。`plan_power_model_version.file_hash` 建唯一约束，用于同一 xlsm 防重复导入。激活版本通过服务层事务保证最多一个 `is_active=1`。

## 3. 解析 Excel 文件名和 hash

解析文件：

```text
ai/inbox/attachments/GCL功率测试基准（V2.1）TOPCon 26.04.13.xlsm
```

SHA256：

```text
97207519ff88a2cb58c79e75fb94381331a953affd0685099ccd7bf2145f36a7
```

解析器只读读取 xlsm，使用 `openpyxl.load_workbook(..., keep_vba=True, data_only=False)` 读取公式结构，并额外读取缓存值用于 J1/B14/B15/效率分布等入库字段；未执行 VBA，只检查到 `xl/vbaProject.bin` 存在。

## 4. 解析摘要

实际解析摘要：

```text
sheet_count=12
model_sheet_count=10
formula_policy=semantic_fixed_mode
factor_option_count=916
valid_factor_option_count=307
power_bin_count=92
supplier_distribution_count=178
benchmark_factor_count=36
warning_count=66
error_count=0
```

模型页：

```text
NT10-72GDF
NT10-78GDF
NT12R-66GDF
NT12R-66GDF (2.0)
NT12-66GDF
NT12R-78GDF
NT12R-48GDF
NT12R-48BGDF
NT12R-54GDF
NT12R-54BGDF
```

注意：Excel 原始 Sheet `NT12R-78GDF ` 带尾随空格，入库保留原始 `sheet_name`，`normalized_model_code` 归一为 `NT12R-78GDF`。

已记录 parse issue：

1. `SEMANTIC_FORMULA_FIX_REQUIRED`：2 条，`NT12R-66GDF!R30`、`NT12R-66GDF!R32`。
2. `INVALID_SUPPLIER_TITLE`：64 条，覆盖 `#REF!` 和 `厂家X` 等异常供应商标题。

## 5. 实现说明

1. `PowerExcelParserService`：只读解析 xlsm，校验 VBA 工程、12 个 Sheet、10 个模型页、固定锚点，提取配置选项、功率档、供应商效率分布、标板基准和 parse issue。
2. `PowerModelRepository`：负责 `plan_power_*` 落库、hash 去重查询、版本详情组装、active 切换。
3. `PowerModelService`：负责导入入口、同 hash existing 返回、版本列表、版本详情、激活版本。
4. `power_model.py` API：新增导入、版本列表、版本详情、激活接口，统一返回 `ApiResponse`，未接入 PlanBom QA。

## 6. 测试命令和真实执行结果

已运行：

```bash
PYTHONPATH=. pytest tests/business_acceptance/test_plan_power_m2_model_versioning.py -q
```

结果：

```text
5 passed in 3.47s
```

已运行：

```bash
python -m compileall backend/app scripts
```

结果：

```text
通过，退出码 0
```

已运行：

```bash
PYTHONPATH=. pytest tests -q
```

结果：

```text
27 tests collected
13 passed
14 failed
```

失败原因：14 个失败均来自既有 logistics business acceptance 测试在当前沙箱内尝试连接 `mysql+pymysql://root:***@127.0.0.1:3306/logistics_ai`，socket 连接被拒绝：

```text
PermissionError: [Errno 1] Operation not permitted
pymysql.err.OperationalError: Can't connect to MySQL server on '127.0.0.1'
```

新增 M2 测试使用 SQLite in-memory，未连接真实 MySQL，已通过。

## 7. 是否遵守 M2 边界

已遵守：

1. 未修改前端。
2. 未接入 `/smart-chat`。
3. 未修改 PlanBom QA 可答逻辑。
4. 未实现正式功率预测计算引擎。
5. 未实现 BOM 配置自动映射。
6. 未 hardcode `BOM配置搭配问询：.docx` 中假数据。
7. 未修改 `.env`、密钥、账号、token。
8. 未覆盖、重命名、删除 `ai/inbox/attachments` 原始附件。
9. 未主动修改本轮禁止触碰的 logistics 脏文件。

脏工作区说明：最终 `git status` 中仍可见与本轮无关的 logistics 脏文件、logistics 测试文件、`ai/eval` 未跟踪文件，以及前端页面脏文件；这些文件未纳入本轮修改清单，M2 交付只以上方“修改文件列表”为准。

## 8. 当前仍未解决的问题

1. `PYTHONPATH=. pytest tests -q` 受当前沙箱网络/本机 MySQL 连接限制影响，既有 logistics DB 依赖测试未能通过。
2. M2 只完成模型版本化入库，尚未进入 M3 计算引擎、M4 BOM 映射、M5 QA/前端接入。
3. 解析器保存了 Excel 缓存值和公式追溯信息，但不会执行宏，也不会重算公式；正式计算需 M3 按 `semantic_fixed_mode` 实现。

## 9. 对现有 BOM / 物流能力影响

1. 未修改 BOM 查询、BOM compare、PlanBom QA 逻辑。
2. 未修改 logistics 业务代码。
3. 新增 API 仅注册在计划 BOM 子路径 `power-model` 下，作为 M2 内部模型管理接口。
4. 前端未修改，M2 未运行 npm build。

## 10. 未 commit / push / deploy 声明

本轮未执行 commit、push、deploy。
