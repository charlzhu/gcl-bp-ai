# 计划 BOM 功率预测智能问答实施方案（M1 + M1.5）

> 本文基于 M1 审计与 M1.5 业务确认，设计后续 M2/M3/M4/M5 实施路线。
> M1.5 已固化 `formula_policy = semantic_fixed_mode`，并确认新版 `GCL功率测试基准（V2.1）TOPCon 26.04.13.xlsm` 作为 M2 主要开发目标。
> 本轮未创建数据库迁移、未新增接口、未修改前端、未接入 PlanBom QA、未实现正式计算引擎。
> Excel 结构与公式细节见：`docs/PLAN_POWER_EXCEL_FORMULA_AUDIT.md`；业务口径见：`docs/PLAN_POWER_BUSINESS_CONFIRMATION.md`。

## 1. 当前仓库能力判断

### 1.1 已完成能力

当前仓库已具备计划 BOM 的基础链路：

1. **BOM Excel 导入模型与服务**
   - ORM：`backend/app/domains/plan_bom/models.py`
   - 导入服务：`backend/app/domains/plan_bom/services/excel_import_service.py`
   - 导入端点：`backend/app/domains/plan_bom/api/endpoints/import_excel.py`
   - 当前主表：`plan_bom_import_batch`、`plan_bom_header`、`plan_bom_material_line`、`plan_bom_revision` 等。

2. **BOM 查询 / compare 服务**
   - 查询服务：`backend/app/domains/plan_bom/services/query_service.py`
   - 查询仓储：`backend/app/domains/plan_bom/repositories/query_repository.py`
   - 查询端点：`backend/app/domains/plan_bom/api/endpoints/query.py`
   - 已支持订单定位、当前版本判定、多候选、材料明细、跨订单 / 跨版本 compare、compare 快照写入 `sys_query_log`。

3. **PlanBom QA 与 NLU 中心**
   - QA 端点：`backend/app/domains/plan_bom/api/endpoints/qa.py`
   - QA 服务：`backend/app/domains/plan_bom/services/qa_service.py`
   - NLU 中心：`backend/app/domains/plan_bom/services/nlu_center_service.py`
   - 表达层：`backend/app/domains/plan_bom/services/answer_presentation_service.py`
   - 当前已有 `power_cell_requirement` 意图识别，但在 `qa_service.py` 中进入 C 类拒答：当前 BOM 数据不支持功率倒推。

4. **智能助手前端路由与展示能力**
   - `/smart-chat` 页面：`frontend/src/views/business-chat/BusinessChatPage.vue`
   - 前端已支持自动识别 / 物流 / 计划 BOM 的 domain switch、表格 / 图表 / 卡片等通用 presentation 展示。
   - 当前尚未有功率预测专属展示结构和关键词路由。

### 1.2 未完成能力

1. 尚无 `plan_power_*` 模型版本表。
2. 尚无功率预测 xlsm 解析服务。
3. 尚无 active 功率模型版本管理。
4. 尚无 `PowerPredictionEngine` / `PowerRecommendationService`。
5. 尚无 BOM 材料描述到功率模型配置项的映射服务。
6. 尚无真实订单驱动的功率预测验收题与 baseline。
7. `PlanBomQaService` 仍把功率问题视为 C 类拒答，未接入确定性计算链路。

### 1.3 本次任务与当前仓库状态一致性

一致。M1/M1.5 已完成 Excel 审计、业务口径固化和 M2 准入判断。当前仓库还缺少结构化功率模型版本和公式复现能力；下一步应先进入 M2 模型版本化入库，不应直接接入 QA 或实现前端展示。

### 1.4 本轮允许 / 禁止修改范围

允许：

1. 新增 / 更新 `docs/PLAN_POWER_EXCEL_FORMULA_AUDIT.md`。
2. 新增 / 更新 `docs/PLAN_POWER_IMPLEMENTATION_PLAN.md`。
3. 新增 `docs/PLAN_POWER_BUSINESS_CONFIRMATION.md`。
4. 更新 `docs/CURRENT_STATUS.md`、`docs/NEXT_TASK.md`、`ai/inbox/attachments_manifest.md`。

禁止：

1. 不创建数据库迁移。
2. 不新增接口。
3. 不修改前端。
4. 不接入 PlanBom QA。
5. 不实现正式计算引擎。
6. 不 hardcode `BOM配置搭配问询：.docx` 的假问题 / 假订单 / 假版型 / 假答案。

## 2. 总体目标架构

功率预测能力应作为 **计划 BOM 业务域的子能力**，不要新建独立业务域。建议目录：

```text
backend/app/domains/plan_bom/
  models.py                               # M2 增加 plan_power_* ORM
  api/endpoints/power_model.py             # M2 模型上传 / 查询 / 激活
  services/power_excel_parser_service.py   # M2 xlsm 解析
  services/power_model_service.py          # M2 版本管理
  services/power_prediction_engine.py      # M3 确定性计算
  services/power_recommendation_service.py # M3 推荐与匹配度
  services/power_config_resolver_service.py# M4 BOM -> 配置映射
  config/power_bom_mapping.yaml            # M4 材料映射规则
  config/power_aliases.json                # M4 同义词 / 别名归一；需包含 M1.5 已确认映射
  config/plan_power_acceptance_questions.json # M5 真实测试题
  config/plan_power_acceptance_baseline.json  # M5 可追溯 baseline
```

前端后续只在 M5 追加展示，不在 M2/M3/M4 先行修改。

## 3. 业务链路设计

```text
用户自然语言问题
↓
PlanBomNluCenterService：识别功率预测意图 + 抽取槽位
↓
若包含订单 / 评审号：PlanBomQueryService 定位当前有效 BOM
↓
PlanBomPowerConfigResolverService：从 BOM 材料行抽取玻璃、焊带、汇流条、接线盒/线缆、电池尺寸、版型等配置
↓
PowerModelService：读取 active 功率模型版本
↓
PowerPredictionEngine：按 Excel VBA + 公式确定性计算功率档位分布
↓
PowerRecommendationService：按目标功率档 / 目标比例计算匹配度并排序
↓
PlanBomAnswerPresentationService：结构化呈现供应商、效率段、档位分布、风险和追溯信息
↓
BusinessChatPage.vue：展示结果表格 / 分布图 / 追溯信息
```

LLM 只允许参与：

1. 意图识别。
2. 槽位抽取。
3. 同义词归一化辅助。
4. 答案表达润色。

后端确定性代码必须负责：

1. BOM 查询。
2. Excel 模型解析。
3. 配置映射。
4. 公式计算。
5. 供应商推荐。
6. 效率段推荐。
7. 匹配度计算。
8. 版本追溯。

## 4. M2：功率模型版本与入库

### 4.1 目标

把新版 `GCL功率测试基准（V2.1）TOPCon 26.04.13.xlsm` 从动态 Excel 转成可追溯、可校验、可激活的结构化模型版本。M2 只做模型入库和解析校验，不实现正式计算引擎，不接入 QA，不修改前端。

### 4.2 建议数据表 / ORM

本阶段可以在 `backend/app/domains/plan_bom/models.py` 中追加 ORM，并通过迁移创建表。建议表如下：

1. `plan_power_model_version`
   - `id`
   - `version_no`：业务版本号，可从文件名 + 更改履历生成。
   - `file_name`
   - `file_hash`
   - `source_type`：`xlsm`
   - `is_active`
   - `parse_status`：`SUCCESS / FAILED / WARNING`
   - `parse_summary_json`
   - `warning_json`
   - `formula_policy`：固定为 `semantic_fixed_mode`
   - `business_version_label`：如 `TOPCon 26.04.13`
   - `created_at / activated_at`

2. `plan_power_model_sheet`
   - `id`
   - `model_version_id`
   - `sheet_name`
   - `normalized_model_code`
   - `cell_count`
   - `base_efficiency_label`
   - `base_power`
   - `center_power_cell`：如 `I36`
   - `std_dev_default`
   - `area_default`
   - `source_range`

3. `plan_power_factor_option`
   - `id`
   - `model_version_id`
   - `sheet_id`
   - `factor_key`：`ribbon / glass / supplier / cell_size / cable / busbar / process / benchmark`
   - `option_label`
   - `normalized_option_label`
   - `effect_value`
   - `area_value`
   - `std_dev_value`
   - `source_cell_ref`
   - `is_valid`
   - `invalid_reason`

4. `plan_power_supplier_efficiency_distribution`
   - `id`
   - `model_version_id`
   - `sheet_id`
   - `supplier_name`
   - `efficiency_value`
   - `ratio_value`
   - `source_cell_ref`

5. `plan_power_power_bin`
   - `id`
   - `model_version_id`
   - `sheet_id`
   - `power_bin`
   - `bin_order`
   - `source_cell_ref`

6. `plan_power_benchmark_factor`
   - `id`
   - `model_version_id`
   - `model_code`
   - `benchmark_name`
   - `effect_value`
   - `source_sheet_name`
   - `source_cell_ref`

7. `plan_power_model_validation_case`
   - 预留 M3 抽样校验：模型版本、输入配置、Excel 对照值、系统计算值、误差、校验状态。

8. `plan_power_parse_issue`
   - 保存 semantic fixed 公式问题、锚点缺失、无效供应商标题、`#REF!`、占位供应商、公式未确认等 warning / error。

### 4.3 M2 服务与接口

建议新增：

1. `PowerExcelParserService`
   - 读取 xlsm。
   - 校验 Sheet 名、锚点、配置行、功率档、供应商分布区。
   - 提取 VBA 存在性与宏代码哈希。
   - 不执行宏。
   - 保存 `formula_policy = semantic_fixed_mode`。
   - 识别 `NT12R-66GDF!R30/R32` 语义修正 issue。
   - 标记异常供应商标题，例如 `0`、`#REF!`、占位 `厂家X`。

2. `PowerModelService`
   - 按 `file_hash` 防重复导入。
   - 创建模型版本。
   - 查询版本列表 / 版本详情。
   - 激活某版本，保证最多一个 active 版本。

3. API：`backend/app/domains/plan_bom/api/endpoints/power_model.py`
   - `POST /plan-bom/power-model/import`：上传 xlsm 并解析。
   - `GET /plan-bom/power-model/versions`：版本列表。
   - `GET /plan-bom/power-model/versions/{id}`：版本详情。
   - `POST /plan-bom/power-model/versions/{id}/activate`：激活版本。

注意：M2 才新增接口，本轮 M1.5 不新增。

### 4.4 M2 验收

1. 上传同一 xlsm 能识别相同 `file_hash`，避免重复版本。
2. 能解析 10 个版型模型页、`标板基准`、`更改履历`。
3. 能列出每个版型的配置项、供应商、效率段、功率档位。
4. 能记录 `R30/R32` semantic fixed issue、异常供应商标题和其他 parse warning。
5. `formula_policy = semantic_fixed_mode` 已保存到模型版本。
6. active 版本可查询且旧版本保留。

## 5. M3：功率预测计算引擎

### 5.1 目标

实现不依赖 Excel、不执行 VBA、不调用 LLM 的确定性功率预测计算。

### 5.2 输入模型

`PowerPredictionRequest` 建议包含：

```json
{
  "model_code": "NT12R-66GDF",
  "configuration": {
    "ribbon": "0.26",
    "glass": "双镀+间隙铝膜",
    "supplier": "通威",
    "cell_size": "182.3*210",
    "cable": "+300/-200mm（4mm²）",
    "busbar": "6*0.3+4*0.25反光",
    "process": "默认",
    "benchmark": "新北德"
  },
  "target_power_ratio": {
    "620": 0.5,
    "625": 0.5
  }
}
```

### 5.3 核心公式复现

后端实现时按 `PLAN_POWER_EXCEL_FORMULA_AUDIT.md` 的公式链路实现：

```text
center_power = base_power
  + ribbon_delta
  + glass_delta
  + supplier_delta
  + cell_size_delta
  + cable_delta
  + busbar_delta
  + process_delta
  + benchmark_delta

single_cell_power = efficiency * area / 1000
module_theoretical_power = single_cell_power * cell_count
actual_power = 以 center_power 为中心按 Excel I29:I48 逻辑推导
bin_probability = normal_cdf((actual_power - lower_bin) / std_dev)
                - normal_cdf((actual_power - upper_bin) / std_dev)
weighted_distribution[bin] = sum(efficiency_ratio_i * bin_probability_i_bin)
```

`NORMSDIST` 等价实现：

```python
normal_cdf(x) = 0.5 * (1 + erf(x / sqrt(2)))
```

### 5.4 关键实现类

1. `PowerPredictionEngine`
   - 读取 active 模型版本。
   - 校验配置项是否存在。
   - 计算中心功率、效率段、功率档概率、加权分布。
   - 返回完整追溯字段：模型版本、source cell、每项影响值。

2. `PowerRecommendationService`
   - 遍历供应商或指定供应商。
   - 排除无有效效率分布的供应商。
   - 计算目标比例匹配度。
   - 输出推荐排序、命中档位、其他档泄漏、置信度和风险提示。

### 5.5 匹配度第一版

建议第一版评分：

```text
score = 100
  - 目标档位占比绝对误差和 * 100
  - 其他档泄漏占比 * 50
  - 缺失效率分布惩罚
  - 配置映射低置信度惩罚
```

输出必须包含：

1. 目标档位预测占比。
2. 目标比例差异。
3. 非目标档泄漏。
4. 有效效率分布覆盖率。
5. 供应商效率段建议。
6. 无法推荐原因。

### 5.6 M3 校验

1. 从 Excel 中人工选取至少 10 组配置。
2. 对比：`I36`、`D29:D48`、`K29:T48` / `K29:R48`、`K71:T71`。
3. 误差阈值建议：中心功率 ≤ 0.01W；比例 ≤ 0.0001 或业务确认阈值。
4. `R30:R34` 按业务确认口径使用 `semantic_fixed_mode`；可保留 `excel_raw_mode` 仅用于差异诊断，但正式系统口径只能使用 `semantic_fixed_mode`。

## 6. M4：BOM 配置自动映射

### 6.1 目标

把真实 BOM 的材料描述映射到功率模型配置项。

### 6.2 输入来源

从当前真实数据库查询：

1. `plan_bom_header`：订单号、版本、订单名称、当前版本。
2. `plan_bom_material_line`：材料类别、物料名称、描述、SAP 编码、用量。

### 6.3 需要映射的配置

| 功率模型配置 | BOM 来源候选 | 说明 |
|---|---|---|
| 版型 | BOM 文件名 / 订单名称 / 物料描述 / 产品型号字段 | 已确认 `NT12/66GDF` -> `NT12-66GDF`，`NT12R/66GDF` -> `NT12R-66GDF`；无分隔符写法建议兼容 |
| 玻璃选型 | 玻璃材料、镀釉、双镀、间隙膜 / 间隙贴膜 | 已确认“间隙贴膜”等同于“间隙铝膜” |
| 焊带选型 | 焊带规格 | 解析 0.26 / 0.24 / 0.23 / 0.28 等 |
| 汇流条 | 汇流条规格 | 解析宽度、厚度、反光等 |
| 线缆长度 | 接线盒 / 线缆描述 | 已确认“接线盒 300/200”映射到 `+300/-200mm`；仍需结合线径 4mm² / 6mm² |
| 电池尺寸 | 电池片 / 版型 | 多数可由版型默认，但需支持显式覆盖 |
| 电池厂家 | 用户指定或推荐遍历 | BOM 不一定有电池供应商，缺失时走所有有效供应商 |
| 标板基准 | 用户指定 / 默认 active 模型默认值 | 已确认“北德/新北德/TÜV北德”->“新北德”，“计量院”->“中国计量院”，“莱茵”->“莱茵基准” |

### 6.4 建议配置文件

1. `backend/app/domains/plan_bom/config/power_aliases.json`
   - 版型别名。
   - 供应商别名。
   - 标板别名。
   - 材料关键词别名。

2. `backend/app/domains/plan_bom/config/power_bom_mapping.yaml`
   - 每个配置项的材料类别来源。
   - 正则解析规则。
   - 优先级。
   - 置信度规则。
   - 需要人工确认的 fallback。

### 6.5 M4 服务

`PlanBomPowerConfigResolverService`：

1. 输入订单号 / 评审号 / 订单名称。
2. 调用 `PlanBomQueryService` 定位当前 BOM。
3. 提取核心材料。
4. 应用 mapping 规则。
5. 输出：
   - `model_code`
   - `resolved_configuration`
   - `unresolved_items`
   - `confidence`
   - `source_material_lines`
   - `warnings`

### 6.6 M4 验收

1. 对真实订单能返回版型、玻璃、焊带、汇流条、接线盒 / 线缆。
2. 映射结果能追溯到材料行。
3. 无法映射时返回明确缺失项，不能编造。
4. `BOM配置搭配问询：.docx` 的假订单无法命中时必须返回空 / 不支持，不得伪造答案。

## 7. M5：接入 PlanBom QA 与智能助手

### 7.1 后端接入点

1. `PlanBomNluCenterService`
   - 扩展功率意图：`power_prediction_recommendation`、`power_supplier_efficiency_query`、`power_target_ratio_match`。
   - 抽取槽位：订单号、评审号、版型、供应商、目标功率档、目标比例、玻璃、焊带、汇流条、线缆、标板。

2. `PlanBomQaService`
   - 将当前 `power_cell_requirement` 的 C 类拒答改为“条件满足时进入功率预测链路”。
   - 无 active 模型、无真实 BOM、配置无法映射、供应商无效率分布时仍返回受控 C 类或 B 类，不返回假结果。

3. `PlanBomAnswerPresentationService`
   - 新增 display type，如 `power_prediction_distribution`。
   - 展示供应商推荐表、效率段、功率档分布、匹配度、追溯信息、风险提示。

4. `sys_query_log`
   - 建议记录 `query_type=plan_power_prediction`。
   - `request_payload` 保存问题、槽位、BOM 追溯、模型版本、配置映射摘要。
   - 结果快照保存推荐摘要，避免历史回放依赖模型版本变化。

### 7.2 前端接入点

1. `frontend/src/views/business-chat/BusinessChatPage.vue`
   - 自动识别中加入功率预测关键词路由。
   - 在 plan_bom domain 下展示功率 prediction presentation。

2. `frontend/src/api/planBom.ts`
   - 复用 QA 接口响应结构，或补充功率 presentation 类型定义。

3. 展示建议：
   - 推荐供应商排名表。
   - 目标功率档预测占比。
   - 非目标档泄漏。
   - 效率段覆盖条形图。
   - 模型版本与 BOM 来源追溯。

### 7.3 M5 验收

1. 真实生成的功率预测测试题可回答。
2. 原有 BOM 查询回归通过。
3. 原有 BOM compare 不受影响。
4. 原有物流问答不受影响。
5. `/smart-chat` 能正确路由到计划 BOM 功率预测链路。

## 8. 测试策略

### 8.1 M2 测试

1. xlsm 解析单测：Sheet 数、版型、配置项、功率档、供应商分布。
2. 锚点校验失败测试：复制一份临时 xlsm 改锚点后应失败。
3. file_hash 去重测试。
4. active 版本切换测试。

### 8.2 M3 测试

1. Excel 抽样对齐测试：至少 10 组配置。
2. 全部版型最小烟测：10 个版型各跑一组默认配置。
3. 无效率分布供应商不可推荐。
4. 目标功率档不在模型范围内应受控失败。
5. 疑似公式问题按业务确认口径测试。

### 8.3 M4 测试

1. 从真实 `plan_bom_header` / `plan_bom_material_line` 自动生成测试题。
2. 覆盖 BOM 中玻璃、焊带、汇流条、接线盒 / 线缆的映射。
3. 映射失败返回 `unresolved_items`，不能编造配置。
4. 假订单 / 假评审号不命中真实数据时受控返回空结果。

### 8.4 M5 测试

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

### 8.5 回归检查

每个后续里程碑至少执行：

```bash
python -m compileall backend scripts
npm run build --prefix frontend
```

如存在项目统一测试脚本，再执行 smoke / E2E；测试数量必须核对“已执行数量 / 总样例数”，不能只报告抽样通过。

## 9. 风险控制

1. **Excel 公式口径风险**：`R30:R34` 已确认采用 `semantic_fixed_mode`，M2/M3 必须保存并执行该口径，不能回退为照搬 Excel 原疑似错误公式。
2. **宏依赖风险**：后端禁止执行 VBA，必须重写宏逻辑。
3. **版型别名风险**：`NT12R-78GDF ` 有尾随空格，BOM 文件名可能省略短横线，必须做别名归一。
4. **BOM 映射风险**：材料描述不一定稳定，mapping 规则必须可配置并输出置信度。
5. **样例文档污染风险**：`BOM配置搭配问询：.docx` 只能作为问法参考，不能作为真实测试数据。
6. **LLM 越界风险**：所有功率数值必须来自确定性引擎，LLM 输出不能作为计算结果。
7. **版本追溯风险**：功率模型版本、BOM 版本、配置映射来源必须一并入日志，否则历史结果不可复现。

## 10. 推荐开发顺序

### M2 开发顺序

1. 新增 `plan_power_*` ORM 与迁移：`model_version`、`model_sheet`、`factor_option`、`supplier_efficiency_distribution`、`power_bin`、`benchmark_factor`、`model_validation_case`、`parse_issue`。
2. 编写 `PowerExcelParserService`，先只解析新版 TOPCon xlsm 并返回内存结构。
3. 编写解析单测，覆盖 12 个 Sheet / 10 个模型页。
4. 落库模型版本和解析结果，保存 `formula_policy = semantic_fixed_mode`。
5. 增加版本查询 / 激活接口。
6. 输出 parse issues：`NT12R-66GDF!R30/R32`、异常供应商标题、`#REF!`、占位供应商。
7. 验证同一 `file_hash` 防重复导入。

### M3 开发顺序

1. 先实现 `normal_cdf` 与单效率段落档概率。
2. 实现中心功率计算。
3. 实现效率段功率推导。
4. 实现供应商效率分布加权。
5. 实现目标比例匹配度。
6. 建立 Excel 抽样校验脚本。

### M4 开发顺序

1. 读取真实 BOM 数据，统计材料描述模式。
2. 编写 `power_aliases.json` 与 `power_bom_mapping.yaml`。
3. 实现 `PlanBomPowerConfigResolverService`。
4. 输出置信度和 unresolved items。
5. 用真实订单生成测试题。

### M5 开发顺序

1. 扩展 NLU 意图与槽位。
2. QA 接入功率预测服务。
3. 表达层新增功率 prediction presentation。
4. 前端展示功率预测结果。
5. 全量回归 BOM / 物流问答。

## 11. M1.5 结论与 M2 准入判断

1. 新版 TOPCon `26.04.13` Excel 可以后端解析和版本化入库，不能当静态表读缓存结果。
2. VBA 仍参与核心计算，后端必须重写选择事件逻辑。
3. `formula_policy = semantic_fixed_mode` 已固化；新版仍有 `NT12R-66GDF!R30/R32` 需要语义修正。
4. BOM 映射、标板别名、版型别名已固化，M4 应写入配置化映射。
5. M2 表结构和解析器设计不需要大改，但需补充 `formula_policy`、`business_version_label`、`model_validation_case`、异常供应商标题 parse issue。
6. 建议进入 M2：功率模型版本化入库。
7. M2 只做模型入库和解析校验，不实现正式计算引擎、不接入 QA、不修改前端。
