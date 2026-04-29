# 物流 903 真实用户验收样例集

生成时间：2026-04-27T00:39:29

## 一、样例规模与结果

- 样例总数：`85`
- 通过：`85`
- 失败：`0`
- 状态覆盖：`{'answerable': 20, 'answerable_variant': 20, 'needs_clarification': 12, 'clarification_then_answerable': 8, 'business_confirmation_required': 10, 'unsupported': 12, 'empty_result': 1, 'execution_error': 1, 'loading': 1}`
- 验证模式：`{'live_data_qa': 82, 'frontend_static': 3}`

## 二、样例清单

| 样例 | 题号 | 预期状态 | query_key / 边界 | 变体问法 | 验收说明 |
| --- | --- | --- | --- | --- | --- |
| UA-001 | Q001 | answerable | hist_quantity_by_region | 华东区域在历史物流台账中的总发运件数是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-002 | Q002 | answerable | hist_quantity_by_region | 华中区域在历史物流台账中的总发运件数是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-003 | Q003 | answerable | hist_quantity_by_region | 华南区域在历史物流台账中的总发运件数是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-004 | Q004 | answerable | hist_quantity_by_region | 华北区域在历史物流台账中的总发运件数是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-005 | Q005 | answerable | hist_quantity_by_region | 西南区域在历史物流台账中的总发运件数是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-006 | Q006 | answerable | hist_quantity_by_region | 西北区域在历史物流台账中的总发运件数是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-007 | Q007 | answerable | hist_quantity_by_region | 东北区域在历史物流台账中的总发运件数是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-008 | Q008 | answerable | hist_total_fee_by_province | 江苏省历史发运的总费用是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-009 | Q009 | answerable | hist_total_fee_by_province | 安徽省历史发运的总费用是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-010 | Q010 | answerable | hist_total_fee_by_province | 广东省历史发运的总费用是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-011 | Q011 | answerable | hist_total_fee_by_province | 云南省历史发运的总费用是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-012 | Q012 | answerable | hist_total_fee_by_province | 新疆省历史发运的总费用是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-013 | Q013 | answerable | hist_total_fee_by_province | 河北省历史发运的总费用是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-014 | Q014 | answerable | hist_total_fee_by_province | 浙江省历史发运的总费用是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-015 | Q015 | answerable | hist_total_fee_by_province | 山东省历史发运的总费用是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-016 | Q016 | answerable | hist_transport_mode_record_summary | 按运输方式统计，公路对应的发运记录数是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-017 | Q017 | answerable | hist_transport_mode_record_summary | 按运输方式统计，铁路对应的发运记录数是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-018 | Q018 | answerable | hist_transport_mode_record_summary | 按运输方式统计，水路对应的发运记录数是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-019 | Q019 | answerable | hist_transport_mode_record_summary | 按运输方式统计，汽运对应的发运记录数是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-020 | Q020 | answerable | hist_transport_mode_record_summary | 按运输方式统计，铁运对应的发运记录数是多少？ | A 类原题应直接进入 OK，并返回结构化结果。 |
| UA-021 | Q021 | answerable_variant | hist_product_spec_mw_summary | 规格为GCL-NT10/78GDF-640W的历史发运总瓦数帮我看一下是多少？ | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-022 | Q022 | answerable_variant | hist_product_spec_mw_summary | 规格为GCL-NT10/72GDF-590W的历史发运总瓦数帮我看一下是多少？ | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-023 | Q023 | answerable_variant | hist_product_spec_mw_summary | 规格为GCL-NT10/72GDF-585W的历史发运总瓦数帮我看一下是多少？ | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-024 | Q024 | answerable_variant | hist_product_spec_mw_summary | 规格为GCL-NT12R/66GDF-620W的历史发运总瓦数帮我看一下是多少？ | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-025 | Q025 | answerable_variant | hist_product_spec_mw_summary | 规格为GCL-NT12/66GDF-710W的历史发运总瓦数帮我看一下是多少？ | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-026 | Q031 | answerable_variant | hist_avg_fee_per_watt_by_transport | 华东区域各运输方式的平均元/瓦分别帮我看一下是多少，并按成本从低到高排序？ | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-027 | Q032 | answerable_variant | hist_avg_fee_per_watt_by_transport | 西南区域各运输方式的平均元/瓦分别帮我看一下是多少，并按成本从低到高排序？ | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-028 | Q033 | answerable_variant | hist_avg_fee_per_watt_by_transport | 西北区域各运输方式的平均元/瓦分别帮我看一下是多少，并按成本从低到高排序？ | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-029 | Q034 | answerable_variant | hist_avg_fee_per_watt_by_transport | 华中区域各运输方式的平均元/瓦分别帮我看一下是多少，并按成本从低到高排序？ | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-030 | Q035 | answerable_variant | hist_avg_fee_per_watt_by_transport | 华南区域各运输方式的平均元/瓦分别帮我看一下是多少，并按成本从低到高排序？ | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-031 | Q036 | answerable_variant | hist_avg_fee_per_watt_by_transport | 华北区域各运输方式的平均元/瓦分别帮我看一下是多少，并按成本从低到高排序？ | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-032 | Q042 | answerable_variant | hist_plan_actual_deviation | 帮我看下：对比2023年华东区域计划发运件数与实际发运件数的偏差率。 | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-033 | Q043 | answerable_variant | hist_plan_actual_deviation | 对比24年西北区域计划发运件数与实际发运件数的偏差率。 | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-034 | Q044 | answerable_variant | hist_plan_actual_deviation | 对比25年西南区域计划发运件数与实际发运件数的偏差率。 | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-035 | Q045 | answerable_variant | hist_plan_actual_deviation | 对比25年华南区域计划发运件数与实际发运件数的偏差率。 | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-036 | Q046 | answerable_variant | hist_plan_actual_deviation | 对比24年华中区域计划发运件数与实际发运件数的偏差率。 | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-037 | Q047 | answerable_variant | hist_top_customers_fee_and_mw_by_province | 帮我看下：江苏省发运记录中，按客户名称统计前5名客户的总费用和总瓦数。 | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-038 | Q048 | answerable_variant | hist_top_customers_fee_and_mw_by_province | 帮我看下：云南省发运记录中，按客户名称统计前5名客户的总费用和总瓦数。 | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-039 | Q049 | answerable_variant | hist_top_customers_fee_and_mw_by_province | 帮我看下：新疆省发运记录中，按客户名称统计前5名客户的总费用和总瓦数。 | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-040 | Q050 | answerable_variant | hist_top_customers_fee_and_mw_by_province | 帮我看下：河北省发运记录中，按客户名称统计前5名客户的总费用和总瓦数。 | A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。 |
| UA-041 | Q026 | needs_clarification | clarification_boundary | 帮我看下2024Q1的物流发运车次或车辆数是多少？ | B 类应返回业务化追问，不能伪装成成功态。 |
| UA-042 | Q027 | needs_clarification | clarification_boundary | 帮我看下2024Q2的物流发运车次或车辆数是多少？ | B 类应返回业务化追问，不能伪装成成功态。 |
| UA-043 | Q028 | needs_clarification | clarification_boundary | 帮我看下2025Q1的物流发运车次或车辆数是多少？ | B 类应返回业务化追问，不能伪装成成功态。 |
| UA-044 | Q029 | needs_clarification | clarification_boundary | 帮我看下2025Q3的物流发运车次或车辆数是多少？ | B 类应返回业务化追问，不能伪装成成功态。 |
| UA-045 | Q030 | needs_clarification | clarification_boundary | 帮我看下2025Q4的物流发运车次或车辆数是多少？ | B 类应返回业务化追问，不能伪装成成功态。 |
| UA-046 | Q037 | needs_clarification | clarification_boundary | 帮我看下2024-01从合肥始发的订单中，平均每车装载托数是多少？ | B 类应返回业务化追问，不能伪装成成功态。 |
| UA-047 | Q038 | needs_clarification | clarification_boundary | 帮我看下2024-06从阜宁始发的订单中，平均每车装载托数是多少？ | B 类应返回业务化追问，不能伪装成成功态。 |
| UA-048 | Q039 | needs_clarification | clarification_boundary | 帮我看下2025-03从合肥始发的订单中，平均每车装载托数是多少？ | B 类应返回业务化追问，不能伪装成成功态。 |
| UA-049 | Q040 | needs_clarification | clarification_boundary | 帮我看下2025-07从合肥始发的订单中，平均每车装载托数是多少？ | B 类应返回业务化追问，不能伪装成成功态。 |
| UA-050 | Q041 | needs_clarification | clarification_boundary | 帮我看下2025-10从阜宁始发的订单中，平均每车装载托数是多少？ | B 类应返回业务化追问，不能伪装成成功态。 |
| UA-051 | Q231 | needs_clarification | clarification_boundary | 帮我看下把最近几个特殊订单列出来。 | B 类应返回业务化追问，不能伪装成成功态。 |
| UA-052 | Q233 | needs_clarification | clarification_boundary | 帮我看下同一笔发运记录在历史台账中运输方式为“公路”，但在2026任务表中对应任务transport为空，系统应给出哪个答案？ | B 类应返回业务化追问，不能伪装成成功态。 |
| UA-053 | Q088 | clarification_then_answerable | hist_total_fee_summary | 识别广德始发地在历史数据中可能存在的异常高成本运输记录，并解释异常原因。 | 原题保持追问；用户补齐条件后，应能进入真实 A 类回答闭环。 |
| UA-054 | Q223 | clarification_then_answerable | hist_total_fee_summary | 最近物流成本是不是变高了？ | 原题保持追问；用户补齐条件后，应能进入真实 A 类回答闭环。 |
| UA-055 | Q223 | clarification_then_answerable | hist_total_fee_summary | 最近物流成本是不是变高了？ | 原题保持追问；用户补齐条件后，应能进入真实 A 类回答闭环。 |
| UA-056 | Q266 | clarification_then_answerable | sys_procurement_avg_loading_trucks | 招标任务与询比价任务的平均装车数分别是多少？ | 原题保持追问；用户补齐条件后，应能进入真实 A 类回答闭环。 |
| UA-057 | Q315 | clarification_then_answerable | hist_total_fee_by_province | 若铁路资源增加10%，哪些省份最适合从公路切换到铁路以降低成本？ | 原题保持追问；用户补齐条件后，应能进入真实 A 类回答闭环。 |
| UA-058 | SQ510 | clarification_then_answerable | hist_total_fee_summary | 2024年“经营计划”口径下的用车总费用是多少？需要说明具体筛选字段。 | 原题保持追问；用户补齐条件后，应能进入真实 A 类回答闭环。 |
| UA-059 | SQ511 | clarification_then_answerable | hist_total_fee_summary | 2024年“经营计划”与普通发运口径的运费差异是多少？ | 原题保持追问；用户补齐条件后，应能进入真实 A 类回答闭环。 |
| UA-060 | SQ512 | clarification_then_answerable | hist_total_fee_summary | 2025年“经营计划”口径下的用车总费用是多少？需要说明具体筛选字段。 | 原题保持追问；用户补齐条件后，应能进入真实 A 类回答闭环。 |
| UA-061 | Q060 | business_confirmation_required |  | 业务上想确认：2023年各区域发运达标率的均值与中位数分别是多少？ | 业务定义或数据口径未确认，必须保留 B 并解释缺口。 |
| UA-062 | Q061 | business_confirmation_required |  | 业务上想确认：2024年各区域发运达标率的均值与中位数分别是多少？ | 业务定义或数据口径未确认，必须保留 B 并解释缺口。 |
| UA-063 | Q062 | business_confirmation_required |  | 业务上想确认：2025年各区域发运达标率的均值与中位数分别是多少？ | 业务定义或数据口径未确认，必须保留 B 并解释缺口。 |
| UA-064 | Q086 | business_confirmation_required |  | 业务上想确认：识别合肥始发地在历史数据中可能存在的异常高成本运输记录，并解释异常原因。 | 业务定义或数据口径未确认，必须保留 B 并解释缺口。 |
| UA-065 | Q087 | business_confirmation_required |  | 业务上想确认：识别阜宁始发地在历史数据中可能存在的异常高成本运输记录，并解释异常原因。 | 业务定义或数据口径未确认，必须保留 B 并解释缺口。 |
| UA-066 | Q088 | business_confirmation_required |  | 业务上想确认：识别广德始发地在历史数据中可能存在的异常高成本运输记录，并解释异常原因。 | 业务定义或数据口径未确认，必须保留 B 并解释缺口。 |
| UA-067 | Q094 | business_confirmation_required |  | 业务上想确认：当任务长期停留在ALLOCATED状态时，应如何识别潜在履约风险并给出优先排查清单？ | 业务定义或数据口径未确认，必须保留 B 并解释缺口。 |
| UA-068 | Q095 | business_confirmation_required |  | 业务上想确认：当任务长期停留在PREALLOCATE状态时，应如何识别潜在履约风险并给出优先排查清单？ | 业务定义或数据口径未确认，必须保留 B 并解释缺口。 |
| UA-069 | Q096 | business_confirmation_required |  | 业务上想确认：当任务长期停留在ENTER状态时，应如何识别潜在履约风险并给出优先排查清单？ | 业务定义或数据口径未确认，必须保留 B 并解释缺口。 |
| UA-070 | Q097 | business_confirmation_required |  | 业务上想确认：当任务长期停留在LEAVE状态时，应如何识别潜在履约风险并给出优先排查清单？ | 业务定义或数据口径未确认，必须保留 B 并解释缺口。 |
| UA-071 | Q076 | unsupported |  | 基于2023–2025历史数据，预测华东区域未来3个月的物流总费用波动区间。 | C 类必须拒答并解释原因，不能让 LLM 改写边界。 |
| UA-072 | Q077 | unsupported |  | 基于2023–2025历史数据，预测西南区域未来3个月的物流总费用波动区间。 | C 类必须拒答并解释原因，不能让 LLM 改写边界。 |
| UA-073 | Q078 | unsupported |  | 基于2023–2025历史数据，预测西北区域未来3个月的物流总费用波动区间。 | C 类必须拒答并解释原因，不能让 LLM 改写边界。 |
| UA-074 | Q079 | unsupported |  | 基于2023–2025历史数据，预测华南区域未来3个月的物流总费用波动区间。 | C 类必须拒答并解释原因，不能让 LLM 改写边界。 |
| UA-075 | Q080 | unsupported |  | 基于2023–2025历史数据，预测华中区域未来3个月的物流总费用波动区间。 | C 类必须拒答并解释原因，不能让 LLM 改写边界。 |
| UA-076 | Q081 | unsupported |  | 预测未来一个季度公路方式的单位成本（元/瓦）是否会上升，并给出主要驱动因素。 | C 类必须拒答并解释原因，不能让 LLM 改写边界。 |
| UA-077 | Q082 | unsupported |  | 预测未来一个季度铁路方式的单位成本（元/瓦）是否会上升，并给出主要驱动因素。 | C 类必须拒答并解释原因，不能让 LLM 改写边界。 |
| UA-078 | Q083 | unsupported |  | 预测未来一个季度水路方式的单位成本（元/瓦）是否会上升，并给出主要驱动因素。 | C 类必须拒答并解释原因，不能让 LLM 改写边界。 |
| UA-079 | Q084 | unsupported |  | 预测未来一个季度汽运方式的单位成本（元/瓦）是否会上升，并给出主要驱动因素。 | C 类必须拒答并解释原因，不能让 LLM 改写边界。 |
| UA-080 | Q085 | unsupported |  | 预测未来一个季度铁运方式的单位成本（元/瓦）是否会上升，并给出主要驱动因素。 | C 类必须拒答并解释原因，不能让 LLM 改写边界。 |
| UA-081 | Q089 | unsupported |  | 若当前在途任务的目的地为苏州，预计到达时间应如何估算？ | C 类必须拒答并解释原因，不能让 LLM 改写边界。 |
| UA-082 | Q090 | unsupported |  | 若当前在途任务的目的地为昭通，预计到达时间应如何估算？ | C 类必须拒答并解释原因，不能让 LLM 改写边界。 |
| UA-083 | FRONTEND-EMPTY | empty_result | frontend_empty_state | 如果接口返回 OK 但 rows 为空，页面必须显示未查到结果说明。 | 空结果态验收，不要求脚本构造真实业务空数据。 |
| UA-084 | FRONTEND-ERROR | execution_error | frontend_error_state | 当接口异常时页面应进入查询失败消息流，不暴露堆栈。 | 错误态验收，通过前端静态检查确认。 |
| UA-085 | FRONTEND-LOADING | loading | frontend_loading_state | 请求过程中应展示正在查询 loading，并防止体验混乱。 | 加载态验收，通过前端静态检查确认。 |

## 三、未通过样例

- 当前无未通过样例。
