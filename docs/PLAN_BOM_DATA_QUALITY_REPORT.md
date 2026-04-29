# PLAN_BOM_DATA_QUALITY_REPORT

## 数据源
- ZIP：`tmp/plan_bom/input/BOM 源数据.zip`
- 有效 BOM Excel 文件数：`34`
- 成功导入：`34`
- 失败导入：`0`
- 解析订单头：`34`
- 解析材料行：`4034`
- warning：`1972`
- error：`0`

## 标准化输出
- 标准化材料：`tmp/plan_bom/plan_bom_standardized_materials.json`
- 订单索引：`backend/app/domains/plan_bom/config/plan_bom_order_index.json`
- 材料别名配置：`backend/app/domains/plan_bom/config/material_aliases.json`

## 数据质量结论
- 已过滤 `__MACOSX` 和 `._*` 噪音文件。
- 已复用现有 `PlanBomExcelImportService` 解析 Excel，不依赖乱码文件名作为唯一事实来源。
- 失败批次保留在 JSON 报告中；成功批次已进入本地运行库供回归复用。
