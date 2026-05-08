# NEXT_TASK.md

## 下一步任务：M2 功率模型版本化入库

M1 与 M1.5 已完成。下一轮建议进入：

```text
M2：功率模型版本化入库
```

M2 的目标是把新版 `GCL功率测试基准` xlsm 从动态 Excel 转成可追溯、可校验、可激活的结构化模型版本。

当前主文件：

```text
ai/inbox/attachments/GCL功率测试基准（V2.1）TOPCon 26.04.13.xlsm
```

---

## 一、进入 M2 前必须先读取

1. `AGENTS.md`
2. `README_WORKSPACE.md`
3. `docs/CURRENT_STATUS.md`
4. `docs/NEXT_TASK.md`
5. `docs/PLAN_POWER_BUSINESS_CONFIRMATION.md`
6. `docs/PLAN_POWER_EXCEL_FORMULA_AUDIT.md`
7. `docs/PLAN_POWER_IMPLEMENTATION_PLAN.md`
8. `ai/inbox/attachments_manifest.md`
9. `ai/inbox/attachments/GCL功率测试基准（V2.1）TOPCon 26.04.13.xlsm`

---

## 二、M2 开发准入结论

可以进入 M2。

依据：

1. 新版 Excel 核心结构可解析。
2. 12 个 Sheet / 10 个版型模型页稳定。
3. 配置区仍为 `A1:Y27`。
4. 电池效率区仍为 `C29:C48`。
5. 功率档位区仍为 `K28:T28` 或 48/54 系列有效 8 档。
6. 供应商效率分布区仍为 `C77:Y96`。
7. 公式结构未出现新阻塞项。
8. 业务已确认 `formula_policy = semantic_fixed_mode`。
9. BOM 映射、标板别名、版型别名已固化。
10. M2 表结构和解析器设计不需要大改。

---

## 三、M2 必须固化的业务口径

### 1. 公式策略

```text
formula_policy = semantic_fixed_mode
```

M2 解析器必须记录 Excel 原始公式 issue，尤其：

```text
NT12R-66GDF!R30
NT12R-66GDF!R32
```

这两个单元格在新版中仍出现疑似 `L行-$S$28` 引用；M3 计算时应按 `I行-$S$28` 语义修正。

### 2. BOM 映射口径

| BOM / 用户问法 | 标准归一结果 |
|---|---|
| 间隙贴膜 | 间隙铝膜 |
| 接线盒 300/200 | +300/-200mm |
| 北德 / 新北德 / TÜV北德 | 新北德 |
| 计量院 | 中国计量院 |
| 莱茵 | 莱茵基准 |
| NT12/66GDF | NT12-66GDF |
| NT12R/66GDF | NT12R-66GDF |

---

## 四、M2 具体任务清单

### 1. 数据库 / ORM

新增并迁移以下表，表名以实际项目规范为准，但需覆盖这些实体：

1. `plan_power_model_version`
   - 保存模型版本、文件名、文件哈希、业务版本标签、active 状态、解析状态、`formula_policy`、parse summary、warning/error。
2. `plan_power_model_sheet`
   - 保存每个模型 Sheet 的原始 Sheet 名、normalized model code、cell count、基础功率、面积、标准差、source range。
3. `plan_power_factor_option`
   - 保存配置项及选项：焊带、玻璃、电池厂家、电池尺寸、线缆长度、汇流条、电池工艺 / 影响因子、标板基准。
4. `plan_power_supplier_efficiency_distribution`
   - 保存供应商、效率段、占比、source cell、有效性标记。
5. `plan_power_power_bin`
   - 保存每个 Sheet 的功率档位和 source cell。
6. `plan_power_benchmark_factor`
   - 保存标板基准页数据，并支持原始标板名与 normalized 标板名。
7. `plan_power_model_validation_case`
   - 预留 M3 公式 parity / 抽样校验用例和结果。
8. `plan_power_parse_issue`
   - 保存锚点缺失、异常供应商标题、`#REF!`、`R30/R32` 语义修正等问题。

### 2. 解析服务

新增：

```text
backend/app/domains/plan_bom/services/power_excel_parser_service.py
```

职责：

1. 读取 xlsm，但不执行 VBA。
2. 校验 workbook 是否有 `xl/vbaProject.bin`。
3. 校验 Sheet 集合：10 个版型模型页 + `标板基准` + `更改履历`。
4. 校验固定锚点：`A3/A6/A9/A12/A17/A20/A23/A26/A76`。
5. 提取配置项、选项、影响值、source cell。
6. 提取功率档位、供应商效率分布、标板基准、更改履历。
7. 识别并记录异常供应商标题，如 `0`、`#REF!`、占位 `厂家X`。
8. 识别并记录 `R30/R32` semantic fix issue。
9. 输出内存解析结构，供 service 落库。

### 3. 模型版本服务

新增：

```text
backend/app/domains/plan_bom/services/power_model_service.py
```

职责：

1. 按 `file_hash` 防重复导入。
2. 创建模型版本和所有解析子记录。
3. 查询版本列表 / 版本详情。
4. 激活模型版本，确保最多一个 active 版本。
5. 返回 parse issues 和 warnings。

### 4. API（M2 可新增，但不要接入 QA）

建议新增内部管理接口：

```text
backend/app/domains/plan_bom/api/endpoints/power_model.py
```

接口建议：

1. `POST /api/v1/plan-bom/power-model/import`
2. `GET /api/v1/plan-bom/power-model/versions`
3. `GET /api/v1/plan-bom/power-model/versions/{id}`
4. `POST /api/v1/plan-bom/power-model/versions/{id}/activate`

注意：M2 只做模型导入 / 查询 / 激活，不实现正式功率计算，不接入智能问答。

### 5. 测试

M2 至少新增 / 运行：

1. xlsm 解析单测：Sheet 数、版型、配置区、功率档、供应商分布。
2. 新版 `26.04.13` 文件解析回归。
3. `formula_policy` 保存测试。
4. `R30/R32` parse issue 记录测试。
5. 异常供应商标题过滤 / issue 测试。
6. 文件 hash 去重测试。
7. active 版本切换测试。
8. 不执行 VBA 的约束测试。

---

## 五、M2 禁止事项

1. 不实现正式功率预测计算引擎。
2. 不接入 PlanBom QA。
3. 不修改前端。
4. 不 hardcode 样例题。
5. 不使用 `BOM配置搭配问询：.docx` 中的假订单、假版型、假项目名作为真实测试数据。
6. 不让 LLM 计算功率预测结果。
7. 不自动进入 M3/M4/M5。

---

## 六、M2 完成后报告要求

完成 M2 后必须输出：

1. 修改了哪些文件。
2. 创建了哪些表 / 迁移。
3. 解析了哪个 Excel 文件和文件 hash。
4. 解析到哪些 Sheet、版型、配置项、功率档、供应商。
5. 记录了哪些 parse issues / warnings。
6. `formula_policy` 是否已入库。
7. active 模型版本是否可查询。
8. 运行了哪些测试，实际执行数量 / 总测试数量是多少。
9. 是否影响现有 BOM / 物流能力。
10. 是否建议进入 M3。
