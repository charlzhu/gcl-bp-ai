# TRIAL_SAMPLE_EXPECTED_ANSWER_METHOD

## 核算口径
- 物流题标准答案优先使用 `logistics_ai` 中间库表时间和数据。
- 23-25 年历史物流题读取 `dwd_logistics_hist_shipment_detail`。
- 2026 年系统物流题读取 `dwd_logistics_ship_task`、`dwd_logistics_ship_product` 等中间库表。
- 源数据 zip 用于文件数量、字段和时间范围核验；若与中间库不一致，报告差异，不混用结果。
- BOM 题读取 `tmp/plan_bom/plan_bom_standardized_materials.json` 中的真实标准化材料行。

## 构建结果
- 样例题数量：1391
- 标准答案状态分布：`{'needs_clarification': 603, 'answerable': 746, 'unsupported': 42}`
- BOM 标准化材料行数：4034
- logistics_ai 可用：True

## 源文件核验
- history_logistics_zip: `23 年至 25 年物流台账数据.zip`，exists=True，excel_count=4
- system_2026_logistics_zip: `物流 26 年源数据.zip`，exists=True，excel_count=13
- bom_source_zip: `BOM 源数据.zip`，exists=True，excel_count=34
- 运行环境本地路径已脱敏。

## 中间库时间范围
- `{'history': {'min_date': datetime.date(2023, 1, 3), 'max_date': datetime.date(2025, 12, 31), 'row_count': 24234}, 'system_2026': {'min_date': datetime.date(2026, 1, 1), 'max_date': datetime.date(2026, 4, 22), 'row_count': 992}}`

## 安全边界
- 本脚本不调用 QA service、不读取前端结果、不让 LLM 查数。
- 业务定义不足的问题标为需要追问或无法回答，不硬算。
