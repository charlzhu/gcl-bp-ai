# 物流域 NLU Slot Schema

## 设计原则

统一 slot 只服务自然语言理解、评测和后续受控接入，不直接等同于数据库字段，也不绕过现有 query_key。

当 slot 缺失会导致误算时，必须进入澄清；当 slot 当前不可靠时，不能直接回答。

## 公共实现

当前公共 slot 抽取已沉淀到 `backend/app/domains/logistics/services/slot_extractor.py`，由 NLU Center 与 `data_qa_planner` 共同调用。

已统一抽取的核心能力包括：

- 时间：年份、跨年列表、月份/月区间、季度、时间范围、来源层判断；
- 地理与线路：区域、省份、省份列表、始发地、目的城市；
- 系统过滤：基地名称、基地编码、任务状态；
- 运输条件：运输方式、车型；
- 业务主体：客户、项目地、承运商/物流公司；
- 复用结构：`time_range`、`core_filters`、`source_scope`。

当前公共实现只负责槽位识别和归一，不直接决定最终 query_key，也不绕过澄清 / 不支持边界。

## 时间类 Slot

| Slot | 含义 | 映射关系 | 缺失处理 |
| --- | --- | --- | --- |
| `year` | 单一年份 | planner `filters.year` | 多数历史/系统统计题必须给出；部分已固化累计口径除外 |
| `month` | 单月 | planner `filters.months=[n]` | 2026 系统月度题缺失时通常澄清 |
| `quarter` | 季度 | 当前主要用于 BCR 澄清，不是通用可执行 slot | 需确认季度口径和数据来源 |
| `date_range` | 起止月份或相对时间 | planner `filters.months` 或相对范围文本 | 相对时间需先确认具体范围 |
| `year_to_date` | 年初至今/当前累计 | planner `default_ytd_scope` | 只有已固化 2026 累计题可直接回答 |
| `historical_range` | 2023–2025 历史范围 | 历史 Excel 台账 | 未明确年份但写明“历史累计”时可用于候选判断 |
| `system_2026_range` | 2026 系统范围 | 正式系统数据 | 2026 前系统测试数据不纳入正式统计 |

## 指标类 Slot

| Slot | 含义 | 现有字段 / query_key 映射 | 缺失处理 |
| --- | --- | --- | --- |
| `shipment_mw` | 发运量 MW，默认运量口径 | `actual_watt` 折算 MW；`hist_mw_summary`、`sys_mw_and_trip_count` | 如果只说“量”但未确认 MW/件数，需澄清 |
| `shipment_quantity` | 发运件数 | `shipment_count`、`actual_qty` | 和 MW 容易混用时需澄清 |
| `shipment_trip_count` | 车次 | `trip_count`、`hist_trip_count_by_region` | 与唯一车辆数混用时需澄清 |
| `total_fee` | 总运费/总费用 | `total_fee`、`sys_total_fee_by_filters` | 缺时间或范围时需澄清，已固化累计口径除外 |
| `avg_fee` | 平均运费/单车均费 | `avg_fee`、`hist_avg_fee_by_month`、`hist_route_pricing_analysis` | 平均基础不明确时需澄清 |
| `unit_fee_per_watt` | 单瓦成本/元瓦 | `fee_per_watt`、`sys_unit_fee_per_watt` | 分子是否含额外费用、平均方式不明时需澄清 |
| `signedfor_rate` | SIGNEDFOR 签收率 | `sys_signedfor_rate_by_carrier` | 分母或状态范围不清时需澄清 |
| `fill_rate` | 字段填充率 | `sys_delivery_distance_fill_rate_by_province` | 字段和统计对象不清时需澄清 |
| `parse_success_rate` | 解析成功率 | `sys_parse_success_rate_by_carrier` | 解析状态口径不清时需澄清 |

## 维度类 Slot

| Slot | 含义 | 映射关系 | 当前可靠性 |
| --- | --- | --- | --- |
| `region` | 区域 | `region_name` | 历史台账较稳定 |
| `province` | 省份 | `province`、`delivery_province` | 历史/系统均可用于已固化 query_key |
| `city` | 城市 | `city`、`delivery_city` | 用于城市排名、送达城市任务量 |
| `base` | 基地 | 历史 `origin_place`、系统 `base_code/base_name` | 系统基地已有限收口；仓库维度仍不可靠 |
| `carrier` | 承运商/物流公司 | 历史 `carrier_name`、系统 `company_name` | 稳定维度之一 |
| `customer` | 客户 | `customer_name` | 客户/项目简称归并不清时需澄清 |
| `project` | 项目 | `project_name` | 当前不是完全稳定通用维度 |
| `transport_type` | 运输方式 | `transport_mode`、`ship_type` | 公路/汽运、铁路/铁运需归一 |
| `vehicle_type` | 车型 | `required_vehicle_type`、`vehicle_type` | 17.5、13m 等已做别名归一 |
| `procurement_type` | 采购方式 | `procurement_type` | 特殊业务口径已部分固化，其余需澄清 |

## 条件类 Slot

| Slot | 含义 | 映射关系 | 缺失/风险 |
| --- | --- | --- | --- |
| `origin_place` | 始发地 | `origin_place` | 线路题缺始发/目的时澄清 |
| `destination_province` | 目的省份 | `province`、`delivery_province` | 省市混用需澄清 |
| `destination_city` | 目的城市 | `city`、`delivery_city` | 地址/城市层级不清需澄清 |
| `base_code` | 系统基地编码 | `base_code` | 只在已固化 2026 基地过滤题中使用 |
| `ship_type` | 系统运输方式 | `ship_type` | 同义口径不清需澄清 |
| `status` | 任务状态 | `task_status` | 状态分母、任务表范围不清需澄清 |
| `supplier` | 供应商/承运商 | `company_name`、`carrier_name` | 与客户混用时需澄清 |
| `special_business_type` | 特殊业务类型 | `special_scope`、`procurement_type` | 经营计划、辅料送样、刘娟用车已部分固化 |

## 来源层 Slot

| Slot | 含义 | 当前规则 |
| --- | --- | --- |
| `historical_2023_2025` | 2023–2025 历史 Excel 台账 | 历史正式统计来源 |
| `system_2026` | 2026+ 正式系统数据 | 2026 前系统库测试数据不纳入统计 |
| `mixed` | 历史 + 系统混合 | 只能在上层语义层统一，不允许原始层粗暴混查 |
| `unknown` | 来源不明 | 需要结合问题、年份或澄清追问判断 |

## 当前不可靠 Slot

| Slot | 原因 | 当前处理 |
| --- | --- | --- |
| `warehouse` | 一期按路线 1 暂不补 allocate 链路，仓库维度不作为可靠统计维度 | 不能直接回答，进入澄清或不支持 |
| `eta` | 缺受控 ETA 模型和在途轨迹推理链路 | C 类不支持 |
| `forecast` | 当前不做预测模型 | C 类不支持 |
| `extra_fee_detail_reason` | 额外费用项目/原因/明细口径未固化 | C 类不支持或待业务 owner 补口径 |

## 和现有 query_key 的关系

- `sys_mw_and_trip_count`：需要 `year=2026`，通常需要 `month/date_range/year_to_date`，指标为 `shipment_mw` 和可选 `shipment_trip_count`。
- `hist_mw_summary`：需要历史年份或历史累计口径，指标为 `shipment_mw`，可按区域/月份过滤。
- `hist_total_fee_by_province`：省份 + 历史总费用，当前已支持历史累计或具体年份。
- `hist_avg_fee_by_month`：历史年份 + 始发地 + 目的省 + 车型，输出月度平均运费。
- `hist_route_pricing_analysis`：线路/车型/年份条件，输出平均运费、月均或跨年比较。
- `sys_signedfor_rate_by_carrier`：2026 系统承运商 SIGNEDFOR 签收率排名。
- `sys_delivery_distance_fill_rate_by_province`、`sys_parse_success_rate_by_carrier`、`sys_company_mapping_gap`：状态/数据质量类能力。

## 术语归一配置

统一术语归一由 `backend/app/domains/logistics/config/logistics_nlu_normalization.json` 管理，NLU Center 启动时加载。

当前配置分为：

- `metric_synonyms`：指标别名，例如发运量/运量/发货量、总费用/总运费、元瓦/单瓦成本。
- `dimension_synonyms`：维度别名，例如物流公司/承运商、客户/最终客户、项目/项目名称。
- `filter_synonyms`：条件别名，例如始发地、目的省份、状态、特殊业务口径。
- `time_synonyms`：时间别名，例如 26年/2026年、1月份/1月、截至目前/年初至今。
- `text_replacements`：安全文本替换，例如把“总车数”归一为“车次”，把“17米五”归一为“17.5”。
- `unreliable_slots`：当前不能直接用于回答的不可靠 slot，例如仓库、ETA、预测、额外费用原因明细。

原则上新增同义词应优先进入配置，不应继续散落在大量 if/else 中。当前少量启发式 query_key 候选仍在 NLU Center 代码中，是为了诊断 A 类同构变体，不参与正式执行。

## 澄清触发原则

以下缺口径不得直接猜：

- 缺时间范围；
- 缺指标口径；
- 缺比较对象或比较标准；
- 缺异常定义；
- 缺排名方向或 TopN 数量；
- 缺平均基础；
- 缺数据来源层；
- 缺状态分母；
- 客户/项目/承运商归并口径不清。
