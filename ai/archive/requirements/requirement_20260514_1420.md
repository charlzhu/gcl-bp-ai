# 任务：计划 BOM 功率预测智能问答功能

## 0. 本轮执行范围

本任务现在正式进入 Hermes 执行。

本功能属于“计划 BOM 业务域”的新增子能力，目标是基于《GCL功率测试基准》Excel，结合现有 BOM 数据，实现“功率预测 /
功率测试基准”的智能问答能力。

本功能复杂，涉及：

- 功率预测 Excel 结构解析
- Excel 公式 / VBA / 宏逻辑审计
- 功率模型版本化入库
- 后端功率预测计算引擎
- BOM 配置自动映射
- 计划 BOM 智能问答接入
- 前端智能助手展示

因此必须分阶段执行，不能一次性直接大改代码。

本轮只执行：

**M1：功率预测 Excel 结构与公式审计 + 现有计划 BOM 链路梳理 + 后续实施方案设计**

本轮允许做：

1. 阅读项目代码。
2. 阅读 AGENTS.md、README_WORKSPACE.md、ai/inbox/requirement.md。
3. 阅读 ai/inbox/attachments_manifest.md。
4. 阅读 ai/inbox/attachments/ 下的附件。
5. 审计功率预测 Excel 的 Sheet、配置区、公式、宏依赖、功率档位分布、供应商效率分布。
6. 梳理现有计划 BOM 和智能问答代码链路。
7. 输出设计文档和后续实施计划。
8. 必要时可以写临时分析脚本读取 Excel 结构，但不要把临时脚本接入正式业务代码。
9. 必要时可以调用 Codex 辅助读取代码、分析公式、生成文档初稿，但 Hermes 必须独立复核。

本轮暂时不要做：

1. 不要创建数据库迁移。
2. 不要新增正式 ORM 模型。
3. 不要新增正式接口。
4. 不要修改计划 BOM 业务主链路。
5. 不要修改 PlanBomQaService 的可答逻辑。
6. 不要修改前端。
7. 不要接入 /smart-chat。
8. 不要实现正式功率预测计算引擎。
9. 不要 hardcode 样例题。
10. 不要把样例题中的假订单号当成真实验收数据。

本轮交付文档：

1. docs/PLAN_POWER_EXCEL_FORMULA_AUDIT.md
2. docs/PLAN_POWER_IMPLEMENTATION_PLAN.md

完成 M1 后，停止并输出完成报告，等待我确认后再进入 M2/M3/M4/M5。

---

## 1. 任务背景

当前项目已有“计划 BOM”业务域，已经实现或部分实现：

1. BOM Excel 上传导入。
2. BOM 明细查询。
3. BOM compare。
4. BOM 自然语言问答。
5. 统一智能助手入口。
6. 查询日志、导出、候选确认、回放等相关能力。

现在需要在现有“计划 BOM”业务域下新增一个子能力：

**计划 BOM 功率预测智能问答**

该能力基于《GCL功率测试基准》xlsm 文件。

该 Excel 不是普通静态表，而是一个动态功率预测模型。业务人员在 Excel 中选择不同配置项后，下方电池效率区、各功率档百分比、组件预测模型档位分布、电池产出分布都会自动变化。

配置项包括但不限于：

1. 焊带选型。
2. 玻璃选型。
3. 电池厂家。
4. 电池尺寸。
5. 面积。
6. 标准差。
7. 线缆长度。
8. 汇流条。
9. 标板基准。

未来系统不能要求业务员继续在前端手动点这些配置。业务目标是：

```text
业务员直接在智能助手中自然语言提问
↓
系统自动理解问题
↓
如果问题涉及订单 / 评审号 / 项目名，则自动查询 BOM
↓
系统从 BOM 中抽取玻璃、间隙贴膜、焊带、汇流条、接线盒等配置
↓
系统映射成功率预测模型中的配置项
↓
系统调用后端确定性功率预测计算引擎
↓
返回供应商、效率段、功率档位分布、目标比例匹配度
```

---

## 2. 附件位置

附件位于：

```text
ai/inbox/attachments/
```

附件包括：

1. GCL功率测试基准（V2.1）26.03.26 (1).xlsm——副本.xlsm
2. BOM配置搭配问询：.docx

请先读取：

```text
ai/inbox/attachments_manifest.md
```

再处理附件。

如果附件不存在、文件名不一致、文件无法读取，请停止本轮任务并在报告中明确说明，不要编造附件内容。

---

## 3. 重要业务说明

`BOM配置搭配问询：.docx` 只作为业务问题类型和问法参考。

非常重要：

1. 文档里的版型号是假的。
2. 文档里的订单号是假的。
3. 文档里的评审号是假的。
4. 文档里的项目名是假的。
5. 文档里的问题不能直接当成真实测试数据。
6. 文档里的问题不能 hardcode。
7. 不能为了让样例题通过而伪造数据。
8. 不能把样例题中的假数据写入测试基线。

该文档只用于理解：

1. 用户会怎么问。
2. 问题里有哪些槽位。
3. 系统应该走什么链路。
4. 最终答案应该用什么格式展示。
5. 后续应如何基于真实 BOM 数据生成真实测试题。

正式开发和测试时，必须基于当前项目中真实存在的 BOM 数据，结合导入后的功率预测模型，自行生成多组真实可验证测试题。

---

## 4. 功能定位

本功能属于：

```text
计划排产业务域 / 计划 BOM 域 / 功率预测子模块
```

不要新建独立业务域。

建议逻辑结构：

```text
plan_bom
├── BOM 查询
├── BOM 对比
├── BOM 自然语言问答
└── 功率预测智能问答
```

核心关系：

1. BOM 模块负责回答：订单用了什么材料配置？
2. 功率预测模块负责回答：这套配置能落入什么功率档？
3. 智能问答模块负责回答：业务员自然语言问题最终应该怎么解释、查数、计算和展示？

---

## 5. 当前已有能力需要复用

优先复用现有代码和表结构。

现有计划 BOM 数据表包括：

1. plan_bom_header
2. plan_bom_material_line
3. plan_bom_revision
4. plan_bom_import_batch
5. plan_bom_export_task
6. plan_bom_export_file

其中：

`plan_bom_header` 用于定位订单、评审号、订单名称、版本、文件实例。

`plan_bom_material_line` 用于读取 BOM 材料行，包括：

1. material_name
2. material_category
3. description
4. standard_usage
5. unit
6. remark
7. order_identity_key
8. file_instance_key
9. version_no
10. sap_code
11. import_batch_id

功率预测需要从 BOM 中抽取的核心材料包括：

1. 玻璃。
2. 间隙贴膜。
3. 焊带 / 互联条。
4. 汇流条。
5. 接线盒 / 线缆。

如果当前项目中这些材料分类、字段名、服务名与上述描述不完全一致，以实际代码和数据库结构为准，但必须在 M1 文档中记录差异。

---

## 6. 总体目标

最终要实现“计划 BOM 功率预测智能问答”能力：

1. 支持周期性导入新的功率预测 Excel。
2. 每次导入生成独立模型版本。
3. 系统自动解析 Excel 中的版型、配置项、配置选项、供应商效率分布、功率档位。
4. 后端复现 Excel 的核心计算逻辑。
5. 支持 active 模型版本。
6. 支持根据用户自然语言问题自动识别版型、订单、配置、供应商、目标功率、目标比例。
7. 如果问题包含订单 / 评审号 / 项目名，则自动查 BOM 并映射到功率预测配置。
8. 输出供应商、电池效率段、功率档位分布、目标比例匹配度。
9. 返回结果要可追溯到模型版本和 BOM 数据来源。
10. 支持后续新版本功率预测 Excel 导入和切换。
11. 原有 BOM 查询、BOM compare、BOM 上传、物流问答能力不能被破坏。

---

## 7. 禁止事项

必须严格遵守：

1. 不允许 hardcode 样例题答案。
2. 不允许 hardcode 附件中的假订单、假版型、假项目名。
3. 不允许让 LLM 直接计算功率结果。
4. 不允许把功率预测做成主要依赖前端手动配置的页面。
5. 不允许跳过 Excel 公式 / VBA 审计直接开发问答。
6. 不允许覆盖旧功率模型版本。
7. 不允许破坏现有 BOM 查询、BOM compare、BOM 上传、物流问答能力。
8. BOM 配置无法映射时，不能瞎猜，必须返回追问或人工确认提示。
9. openpyxl 不执行 VBA，也不能可靠重算 Excel 公式，因此必须明确后端计算逻辑如何复现。
10. 不允许把临时分析脚本误接入正式业务链路。

LLM 的职责仅限于：

1. 意图识别。
2. 槽位抽取。
3. 同义词归一化辅助。
4. 答案表达。

确定性职责必须由后端完成：

1. BOM 查询。
2. 功率模型解析。
3. 公式计算。
4. 功率档位分布计算。
5. 供应商推荐。
6. 效率段推荐。
7. 匹配度计算。
8. 版本追溯。

---

## 8. 本轮 M1 必须审计的 Excel 内容

请对 `GCL功率测试基准（V2.1）26.03.26 (1).xlsm——副本.xlsm` 做结构和公式审计。

必须识别并记录：

1. 工作簿是否为 xlsm。
2. 是否包含 VBA / 宏工程。
3. 所有 Sheet 名称。
4. 每个 Sheet 是否属于版型模型页、标板基准页、版本履历页或其他辅助页。
5. 每个版型 Sheet 对应的组件版型。
6. 每个版型 Sheet 的配置选择区位置。
7. 配置项名称。
8. 配置选项名称。
9. 配置选项对应的功率影响值。
10. 电池效率区位置。
11. 功率档位区位置。
12. 组件预测模型档位分布区位置。
13. 电池产出分布 / 供应商效率分布区位置。
14. 标板基准相关数据来源。
15. 哪些单元格是输入项。
16. 哪些单元格是输出项。
17. 哪些单元格是公式。
18. 核心公式依赖链。
19. VBA 是否参与核心计算。
20. 后端需要复现哪些计算公式。
21. 哪些结果可以作为静态参数读取。
22. 哪些结果不能只读静态值，必须由后端重新计算。
23. 是否存在疑似公式复制错误、固定单元格依赖、隐藏行列、合并单元格、数据验证下拉项。
24. 当前 Excel 是否依赖固定行列位置，如果依赖，后续导入器如何做防错。
25. 后续如何对系统计算结果与 Excel 结果做抽样校验。

M1 文档必须给出具体单元格范围、Sheet 名称、字段解释和风险说明。不能只写抽象结论。

---

## 9. 本轮 M1 必须梳理的现有项目链路

请阅读当前项目代码，重点梳理：

1. 计划 BOM 域目录结构。
2. BOM 上传导入链路。
3. BOM 明细查询链路。
4. BOM compare 链路。
5. PlanBomQaService 或等价 QA 服务链路。
6. PlanBomNluCenterService 或等价 NLU 服务链路。
7. PlanBomAnswerPresentationService 或等价答案展示链路。
8. /api/v1/plan-bom/qa/ask 入口。
9. /smart-chat 前端智能助手入口。
10. 查询日志 sys_query_log 的写入方式。
11. 当前 C 类拒答中是否已有 power_cell_requirement 或类似功率相关 intent。
12. 当前代码中哪些位置适合接入功率预测链路。
13. 哪些位置不能直接改，避免影响原 BOM 回归。

如果实际代码中服务名与上述名称不同，请以实际代码为准，并在文档中说明对应关系。

---

## 10. 推荐后续新增目录

后续建议在现有计划 BOM 域下新增功率预测子模块：

```text
backend/app/domains/plan_bom/power/
```

建议包含：

1. __init__.py
2. constants.py
3. models.py
4. schemas.py
5. repository.py
6. excel_parser.py
7. calculation_engine.py
8. recommendation_service.py
9. bom_config_resolver.py
10. qa_adapter.py
11. api.py

如果当前项目风格更适合分散到原有目录，也可以使用：

1. backend/app/domains/plan_bom/services/
2. backend/app/domains/plan_bom/repositories/
3. backend/app/domains/plan_bom/schemas/
4. backend/app/domains/plan_bom/api/endpoints/
5. backend/app/domains/plan_bom/config/

但必须保持功能边界清晰，不能污染原 BOM 查询主链路。

M1 的实施方案文档中必须结合当前真实项目目录，给出推荐落点。

---

## 11. 建议后续新增配置文件

后续建议新增：

1. backend/app/domains/plan_bom/config/power_aliases.json
2. backend/app/domains/plan_bom/config/power_bom_mapping.yaml

用途：

power_aliases.json：

1. 版型别名。
2. 标板别名。
3. 供应商别名。
4. 材料规格别名。
5. 用户问法归一化。

power_bom_mapping.yaml：

1. BOM material_category 到功率模型配置项的映射。
2. BOM description 到功率配置 option 的映射规则。
3. 无法映射时的追问策略。

不要把全部映射规则硬编码在 Python 代码里。

M1 文档中需要说明这些配置文件的建议结构。

---

## 12. 建议后续新增数据表

表名前缀建议使用：

```text
plan_power_
```

### 12.1 plan_power_model_version

功率模型版本表，用于记录每次导入的功率预测 Excel。

建议字段：

1. version_id
2. version_name
3. source_file_name
4. file_hash
5. status
6. is_active
7. uploaded_at
8. activated_at
9. sheet_count
10. model_count
11. warning_count
12. error_count
13. validation_summary_json
14. created_at
15. updated_at

要求：

1. 每导入一份新的功率预测 Excel，都生成一个新版本。
2. 同一时间只能有一个 active 版本。
3. 旧版本必须保留，不能覆盖。
4. 智能问答默认使用 active 版本。

### 12.2 plan_power_model_sheet

功率模型版型表。

建议字段：

1. id
2. version_id
3. sheet_name
4. model_type
5. base_efficiency
6. base_power
7. cell_count
8. area
9. std_dev
10. power_bin_start
11. power_bin_end
12. power_bin_step
13. raw_meta_json
14. created_at
15. updated_at

用途：记录每个 Sheet 对应的版型和基础参数。

### 12.3 plan_power_factor_option

配置选项影响因子表。

建议字段：

1. id
2. version_id
3. model_type
4. factor_type
5. option_name
6. normalized_option_name
7. power_delta
8. is_default
9. source_sheet_name
10. source_cell_ref
11. raw_json
12. created_at
13. updated_at

factor_type 建议标准化为：

1. ribbon
2. glass
3. cell_supplier
4. cell_size
5. area
6. std_dev
7. cable_length
8. busbar
9. benchmark
10. other_factor

### 12.4 plan_power_supplier_efficiency_distribution

供应商效率分布表。

建议字段：

1. id
2. version_id
3. model_type
4. supplier_name
5. normalized_supplier_name
6. efficiency
7. ratio
8. source_sheet_name
9. source_row_no
10. source_col_no
11. created_at
12. updated_at

### 12.5 plan_power_prediction_cache

功率预测结果缓存表。

建议字段：

1. id
2. version_id
3. model_type
4. combination_hash
5. supplier_name
6. config_json
7. target_power_json
8. target_ratio_json
9. distribution_json
10. matched_efficiency_range
11. match_score
12. created_at

第一版可以实时计算 + 缓存，不要一开始强制全组合预计算到爆表。

### 12.6 plan_power_model_validation_case

功率模型校验用例表。

建议字段：

1. id
2. version_id
3. model_type
4. case_name
5. input_config_json
6. excel_result_json
7. system_result_json
8. diff_json
9. status
10. created_at

用途：记录系统计算结果与 Excel 抽样结果是否一致。

M1 文档中需要判断这些表是否合理，并结合现有项目的 ORM / Alembic 风格给出后续落库建议。本轮不要创建这些表。

---

## 13. 建议后续新增接口

### 13.1 上传功率模型

```text
POST /api/v1/plan-bom/power-model/upload
```

功能：

1. 上传 xlsm。
2. 生成模型版本。
3. 解析 Sheet。
4. 解析配置项。
5. 解析供应商效率分布。
6. 解析功率档位。
7. 执行抽样校验。

### 13.2 查询模型版本

```text
GET /api/v1/plan-bom/power-model/versions
```

### 13.3 激活模型版本

```text
POST /api/v1/plan-bom/power-model/{version_id}/activate
```

要求：

1. 只有校验通过的版本才能激活。
2. 同一时间只能有一个 active 版本。

### 13.4 功率预测调试接口

```text
POST /api/v1/plan-bom/power/query
```

用途：输入版型、配置、供应商，返回功率档位分布。

该接口主要用于开发、验收、调试，不是业务员主入口。

### 13.5 功率推荐接口

```text
POST /api/v1/plan-bom/power/recommend
```

用途：输入版型、配置、目标功率档、目标比例，返回供应商推荐、效率段推荐、匹配度。

### 13.6 智能问答入口

继续复用现有：

```text
POST /api/v1/plan-bom/qa/ask
```

不要给业务员新增复杂入口。

M1 文档中需要结合当前路由结构，给出后续接口落点建议。本轮不要新增接口。

---

## 14. 问答意图设计

建议后续新增或细化这些功率预测意图：

1. power_supplier_recommendation
2. power_supplier_efficiency_requirement
3. power_all_supplier_efficiency_ranges
4. power_order_requirement_match
5. power_explicit_config_match

不要把所有功率问题都塞进一个粗粒度 intent。

M1 文档中需要说明：

1. 每个 intent 的含义。
2. 需要抽取哪些槽位。
3. 必填槽位和可选槽位。
4. 缺槽时如何追问。
5. 如何区分纯 BOM 问题、纯功率预测问题、BOM + 功率预测混合问题。

---

## 15. 典型链路

### 15.1 订单 + 目标功率 + 目标比例

用户问法类似：

```text
某订单用哪些家电池可以满足 715 和 720 的 2:8 占比？
```

处理流程：

1. 识别订单 / 评审号 / 项目名。
2. 识别版型。
3. 识别目标功率档：715、720。
4. 识别目标比例：2:8。
5. 查询 plan_bom_header 定位 BOM。
6. 查询 plan_bom_material_line 提取核心材料。
7. 映射成功率预测配置。
8. 遍历有有效效率分布的供应商。
9. 调用功率预测引擎。
10. 返回推荐供应商、效率段、功率档位占比、匹配度。

### 15.2 明确配置 + 各家供应商

用户问法类似：

```text
NT12R-66GDF，焊带 0.24+0.26，玻璃双镀，汇流条 6*0.4+4*0.35反光，接线盒 300/200，标板新北德，620:625 = 1:1，各家供应商效率段在哪里？
```

处理流程：

1. 不查 BOM。
2. 直接抽取用户给出的版型和配置。
3. 遍历所有有有效效率分布的供应商。
4. 计算各供应商功率档位分布。
5. 计算目标比例匹配度。
6. 返回表格。

### 15.3 明确配置 + 指定供应商

用户问法类似：

```text
同样配置下，芜湖需要使用哪个效率段？
```

处理流程：

1. 识别供应商。
2. 识别配置。
3. 识别目标功率档和比例。
4. 只计算指定供应商。
5. 返回推荐效率段和预计功率档占比。

### 15.4 BOM 配置无法映射

处理流程：

1. 系统查到了订单 BOM。
2. 系统提取了玻璃、焊带、汇流条、接线盒等材料。
3. 但某些材料规格无法映射到功率预测模型配置项。
4. 系统不能瞎猜。
5. 返回 B 类追问或人工确认提示。

示例：

```text
已找到该订单 BOM，但“汇流条”规格无法匹配到当前功率预测模型中的配置选项。请确认该规格对应以下哪一项：A / B / C。
```

---

## 16. BOM 配置映射要求

后续新增：

```text
PlanBomPowerConfigResolverService
```

职责：

1. 根据订单号 / 评审号 / 订单名称定位 BOM。
2. 从 plan_bom_material_line 中提取核心材料。
3. 根据 material_category 和 description 解析：
    - 玻璃
    - 间隙贴膜
    - 焊带
    - 汇流条
    - 接线盒 / 线缆
4. 映射到功率预测模型中的配置选项。
5. 输出映射结果、原始描述、未识别项、置信度。

输出结构建议：

```json
{
  "order_no": "xxx",
  "version_no": "A0",
  "model_type": "NT12R-66GDF",
  "resolved_config": {
    "glass": {
      "value": "双镀",
      "source_description": "xxx",
      "confidence": 0.95
    },
    "ribbon": {
      "value": "0.24+0.26",
      "source_description": "xxx",
      "confidence": 0.92
    },
    "busbar": {
      "value": "6*0.4+4*0.35反光",
      "source_description": "xxx",
      "confidence": 0.90
    },
    "cable_length": {
      "value": "300/200",
      "source_description": "xxx",
      "confidence": 0.88
    }
  },
  "unresolved_items": []
}
```

M1 文档中需要说明该服务与现有 BOM 查询服务如何协作。

---

## 17. 计算引擎要求

后续新增：

1. PowerPredictionEngine
2. PowerRecommendationService

核心流程：

```text
输入：版型 + 配置 + 供应商 + 目标功率档 + 目标比例
↓
读取当前 active 功率模型版本
↓
读取版型基础参数
↓
读取配置项影响因子
↓
读取供应商效率分布
↓
逐效率段计算功率档概率
↓
按供应商效率分布加权汇总
↓
得到最终功率档位分布
↓
计算目标比例匹配度
↓
返回推荐结果
```

匹配度第一版可以先简单实现：

目标：620:625 = 1:1

目标占比：

1. 620 = 50%
2. 625 = 50%

预测占比：

1. 620 = 48%
2. 625 = 46%
3. 其他 = 6%

评分原则：

1. 目标档差异越小越好。
2. 其他档泄漏越少越好。
3. 供应商有效效率分布越完整越好。
4. 无有效效率分布的供应商不能参与推荐。

M1 文档中必须说明后续计算引擎的公式复现方案和校验方案。

---

## 18. 测试要求

由于 `BOM配置搭配问询：.docx` 中的问题是假数据，所以测试题必须自行生成。

后续测试要求：

1. 从当前 plan_bom_header / plan_bom_material_line 中找真实存在的订单。
2. 提取这些订单的核心材料配置。
3. 结合 active 功率预测模型，生成真实可执行测试题。
4. 测试题不能依赖 hardcode。
5. 测试题和预期结果要能追溯到 BOM 数据和功率模型版本。

测试覆盖：

1. 订单 + 目标功率 + 目标比例。
2. 明确配置 + 各家供应商。
3. 明确配置 + 指定供应商。
4. BOM 配置无法映射。
5. 无 active 模型版本。
6. 供应商无有效效率分布。
7. 版型无法识别。
8. 目标功率档不在模型范围内。
9. 问法不同但语义相同。
10. 样例题中的假订单无法命中真实数据时，不能伪造答案。

建议后续新增：

1. backend/app/domains/plan_bom/config/plan_power_acceptance_questions.json
2. backend/app/domains/plan_bom/config/plan_power_acceptance_baseline.json

本轮 M1 只需要在实施方案中设计测试策略，不要创建正式测试基线。

---

## 19. 全量里程碑

### M1：功率 Excel 结构与公式审计

本轮执行范围。

交付：

1. docs/PLAN_POWER_EXCEL_FORMULA_AUDIT.md
2. docs/PLAN_POWER_IMPLEMENTATION_PLAN.md

验收：

1. 能列出所有 Sheet、版型、配置项、供应商效率分布、功率档位区域。
2. 能说明后端需要复现哪些公式 / VBA 逻辑。
3. 能说明哪些公式目前无法确认。
4. 能说明哪些内容需要业务确认。
5. 能说明与现有计划 BOM 链路的接入点。
6. 未确认公式前，不进入问答开发。

### M2：功率模型版本与入库

后续执行。

交付：

1. 新增 plan_power_* 表或 ORM。
2. 新增功率模型上传接口。
3. 新增模型版本查询接口。
4. 新增模型版本激活接口。

验收：

1. 上传 xlsm 后能生成模型版本。
2. 能解析出版型、配置项、供应商效率分布。
3. 重复上传同文件能识别 file_hash。
4. 能设置 active 版本。
5. 旧版本保留可查。

### M3：功率预测计算引擎

后续执行。

交付：

1. PowerPredictionEngine
2. PowerRecommendationService

验收：

1. 至少抽样 10 组配置。
2. 系统计算结果与 Excel 当前结果误差在业务允许范围内。
3. 误差超过阈值必须失败并记录原因。
4. 不能让 LLM 直接计算结果。

### M4：BOM 配置自动映射

后续执行。

交付：

1. PlanBomPowerConfigResolverService
2. power_bom_mapping.yaml
3. power_aliases.json

验收：

输入真实订单号 / 评审号后，能返回：

1. 版型。
2. 玻璃。
3. 焊带。
4. 汇流条。
5. 接线盒 / 线缆。
6. 未识别项。
7. 置信度。
8. 原始 BOM 描述。

### M5：接入 PlanBom QA 和智能助手

后续执行。

交付：

1. PlanBomNluCenterService 新增功率意图。
2. PlanBomQaService 接入功率预测链路。
3. PlanBomAnswerPresentationService 支持功率预测表格。
4. BusinessChatPage.vue 补充功率预测关键词路由。

验收：

1. 真实生成的功率预测测试题可回答。
2. 原有 BOM 查询回归通过。
3. 原有 BOM compare 不受影响。
4. 原有物流问答不受影响。
5. /smart-chat 能正确路由到计划 BOM 功率预测链路。

---

## 20. Hermes 与 Codex 分工要求

Hermes 负责：

1. 阅读任务和附件。
2. 拆解任务。
3. 指挥 Codex 检查代码和实现。
4. 独立复核 Codex 的结果。
5. 对比 Excel 原始结果和系统结果。
6. 检查是否满足验收标准。
7. 输出完成报告。

Codex 负责：

1. 读取项目代码。
2. 编写或修改代码。
3. 编写测试。
4. 执行编译和测试。
5. 输出变更说明。

要求：

1. 不能只让 Codex 自己跑自己测。
2. Hermes 必须独立检查结果。
3. 本轮 M1 不需要 Codex 大规模改代码。
4. 如果 Codex 生成文档，Hermes 必须复核 Excel 结构和代码链路是否真实准确。
5. 如果发现不确定内容，必须标注“待确认”，不能编造。

---

## 21. 本轮验收命令

本轮 M1 原则上只产出文档，不应改业务代码。

仍建议执行基础检查：

```bash
python -m compileall backend scripts
```

如果需要检查前端未受影响，可执行：

```bash
npm run build --prefix frontend
```

如果当前项目有统一测试脚本，继续执行：

```bash
python ai/scripts/run_tests.sh smoke
```

或按项目实际脚本执行。

如果这些命令因环境依赖缺失失败，必须在报告中说明失败原因，不要伪造成功。

---

## 22. 本轮完成报告要求

完成 M1 后必须输出：

1. 阅读了哪些文件。
2. 阅读了哪些附件。
3. 功率 Excel 解析到了哪些 Sheet。
4. 每个 Sheet 对应哪些版型。
5. 每个 Sheet 的配置区在哪里。
6. 每个 Sheet 的电池效率区在哪里。
7. 每个 Sheet 的功率档位区在哪里。
8. 每个 Sheet 的供应商效率分布区在哪里。
9. 发现了哪些公式。
10. VBA / 宏是否参与核心计算。
11. 后端需要复现哪些计算逻辑。
12. 哪些内容还不能确认。
13. 哪些地方需要业务确认。
14. 现有计划 BOM 代码链路如何接入。
15. 后续 M2/M3/M4/M5 的具体开发建议。
16. 本轮是否修改代码。
17. 本轮修改了哪些文件。
18. 运行了哪些测试。
19. 测试是否通过。
20. 是否影响现有 BOM / 物流能力。

---

## 23. 本轮成功标准

本轮成功不以“功能上线”为标准。

本轮成功标准是：

1. 已完整读懂功率预测 Excel 的结构。
2. 已明确公式 / VBA / 宏是否影响核心计算。
3. 已明确后端能否复现计算逻辑。
4. 已明确功率模型如何版本化入库。
5. 已明确如何与现有 BOM 查询、BOM QA、智能助手结合。
6. 已明确后续开发的文件、表、接口、服务、测试路线。
7. 只产出必要文档，不破坏当前项目功能。
