# 当前系统复现记录

## Sheet1-R2#1 / logistics
- 问题：合肥发江苏 17.5 车运费
- 业务反馈：不同时间和地点的车价
- 状态：OK；intent/query_key：aggregate/hist_route_pricing_analysis
- filters/slots：`{"years": [2023, 2024, 2025], "vehicle_type": "17.5", "view_mode": "avg_fee", "default_year_scope_label": "2023-2025历史累计", "origin_place": "合肥", "province": "江苏"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['avg_fee', 'row_count']；rows=1
- 摘要：2023-2025历史累计合肥发江苏17.5车平均运费为6,163元。
- 前几行：`[{"avg_fee": 6163.0, "row_count": 532}]`
- warnings：['当前题目未明确统计年份与指标口径，系统默认按2023-2025历史累计平均运费返回。']

## Sheet1-R3#1 / logistics
- 问题：23年各区域发运量汇总，以表格形式体现
- 业务反馈：7个大区汇总未以表格形式呈现
- 状态：OK；intent/query_key：detail_list/hist_mw_by_all_regions
- filters/slots：`{"year": 2023}`
- 展示：display_type=table；chart_type=None；columns=['region_name', 'shipment_mw']；rows=7
- 摘要：2023年各区域发运量汇总已按区域拆分返回。
- 前几行：`[{"region_name": "西北", "shipment_mw": 3448.851}, {"region_name": "华东", "shipment_mw": 1664.396}]`

## Sheet1-R4#1 / logistics
- 问题：23年合肥发往西北地区的总运量是多少
- 业务反馈：结果不对，正确值为2508.5155MW
- 状态：OK；intent/query_key：aggregate/hist_mw_summary
- filters/slots：`{"year": 2023, "months": [], "region_name": "西北", "origin_place": "合肥"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['shipment_mw']；rows=1
- 摘要：2023年西北区域合肥基地总发运量为2508.516MW。
- 前几行：`[{"shipment_mw": 2508.516}]`

## Sheet1-R5#1 / logistics
- 问题：帮我做一个23年每个月的运费对比
- 业务反馈：未按月生成运费总量、折线或者柱状图
- 状态：OK；intent/query_key：compare/hist_monthly_total_fee_by_year
- filters/slots：`{"year": 2023}`
- 展示：display_type=mixed；chart_type=bar；columns=['biz_month', 'total_fee']；rows=12
- 摘要：2023年各月物流总费用已按 year-month 月份粒度返回。
- 前几行：`[{"biz_month": "2023-01", "total_fee": 170400.0}, {"biz_month": "2023-02", "total_fee": 737412.0}]`

## Sheet1-R6#1 / logistics
- 问题：帮我看下23年发往乌鲁木齐13m每车的运费均价是多少
- 业务反馈：未输出单车运价
- 状态：OK；intent/query_key：aggregate/hist_route_pricing_analysis
- filters/slots：`{"years": [2023], "vehicle_type": "13", "view_mode": "avg_fee", "city": "乌鲁木齐"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['avg_fee', 'row_count']；rows=1
- 摘要：2023年乌鲁木齐13车平均运费为401,315元。
- 前几行：`[{"avg_fee": 401315.0, "row_count": 89}]`

## Sheet1-R7#1 / logistics
- 问题：2023年物流发运合计多少量？
- 业务反馈：问答角度不同，出来结果都一样
- 状态：OK；intent/query_key：aggregate/hist_mw_summary
- filters/slots：`{"year": 2023, "months": null}`
- 展示：display_type=summary_cards；chart_type=None；columns=['shipment_mw']；rows=1
- 摘要：2023年总发运量为8493.604MW。
- 前几行：`[{"shipment_mw": 8493.604}]`

## Sheet1-R8#1 / logistics
- 问题：2023年各物流承运商年度运输费用各是多少？
- 业务反馈：问答角度不同，出来结果都一样
- 状态：OK；intent/query_key：ranking/hist_carrier_kpi_by_year
- filters/slots：`{"year": 2023, "region_name": null, "view_mode": "fee_only"}`
- 展示：display_type=mixed；chart_type=bar；columns=['carrier_name', 'shipment_mw', 'shipment_share_pct', 'total_fee']；rows=17
- 摘要：2023年各物流承运商年度运输费用已汇总返回。
- 前几行：`[{"carrier_name": "江苏久鼎供应链管理有限公司", "shipment_mw": 1753.17, "shipment_share_pct": 20.68, "total_fee": 66532138.0}, {"carrier_name": "苏州晶茂物流有限公司", "shipment_mw": 1660.485, "shipment_share_pct": 19.58, "total_fee": 34694444.0}]`

## Sheet1-R9#1 / logistics
- 问题：2023年英赋嘉发运多少量？
- 业务反馈：问答角度不同，出来结果都一样
- 状态：OK；intent/query_key：aggregate/hist_mw_summary
- filters/slots：`{"year": 2023, "months": null, "carrier_name": "英赋嘉"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['shipment_mw']；rows=1
- 摘要：2023年英赋嘉总发运量为1612.679MW。
- 前几行：`[{"shipment_mw": 1612.679}]`

## Sheet1-R10#1 / logistics
- 问题：帮我查一下23年阜宁基地晶茂物流运输总运费多少钱?
- 业务反馈：统计的总计金额结果数据不对
- 状态：OK；intent/query_key：aggregate/hist_total_fee_by_origin_and_carrier
- filters/slots：`{"year": 2023, "origin_place": "阜宁", "carrier_name": "晶茂"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['total_fee']；rows=1
- 摘要：2023年阜宁基地、承运商晶茂的总运费为7,252,245元。
- 前几行：`[{"total_fee": 7252245.0}]`

## Sheet1-R11#1 / logistics
- 问题：华润新能源（皮山）有限公司 项目 24年发运量是多少 无回答
- 业务反馈：在问题2中回复，就询问必须增加字段，客户和项目 分不清
- 状态：OK；intent/query_key：aggregate/hist_customer_mw
- filters/slots：`{"year": 2024, "months": null, "customer_name": "华润新能源（皮山）有限公司"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['shipment_mw']；rows=1
- 摘要：2024年华润新能源（皮山）有限公司总发运量为480.413MW。
- 前几行：`[{"shipment_mw": 480.413, "matched_customer_names": ["华润新能源（皮山）有限公司", "华润新能源（皮山）有限公司客诉组件"], "scope_label": "2024年"}]`
- warnings：['当前按客户名前缀归并，命中了 2 个客户名变体。']

## Sheet1-R11#2 / logistics
- 问题：客户：华润新能源（皮山）有限公司 24年发运量是多少  就有回复了
- 业务反馈：在问题2中回复，就询问必须增加字段，客户和项目 分不清
- 状态：OK；intent/query_key：aggregate/hist_customer_mw
- filters/slots：`{"year": 2024, "months": null, "customer_name": "华润新能源（皮山）有限公司"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['shipment_mw']；rows=1
- 摘要：2024年华润新能源（皮山）有限公司总发运量为480.413MW。
- 前几行：`[{"shipment_mw": 480.413, "matched_customer_names": ["华润新能源（皮山）有限公司", "华润新能源（皮山）有限公司客诉组件"], "scope_label": "2024年"}]`
- warnings：['当前按客户名前缀归并，命中了 2 个客户名变体。']

## Sheet1-R12#1 / logistics
- 问题：26年招标和询比价，发运量分别是多少
- 业务反馈：26年在《采购类型》中增加采购和询比价 字段，可直接汇总相应字段的统计结果
- 状态：OK；intent/query_key：detail_list/sys_mw_by_procurement_type
- filters/slots：`{"year": 2026}`
- 展示：display_type=mixed；chart_type=bar；columns=['procurement_type', 'shipment_mw', 'task_count']；rows=3
- 摘要：2026年招标、询比价等采购方式对应的发运量拆分已返回。
- 前几行：`[{"procurement_type": "招标", "shipment_mw": 1007.819, "task_count": 308}, {"procurement_type": "询比价", "shipment_mw": 672.02, "task_count": 917}]`

## Sheet1-R13#1 / logistics
- 问题：帮我统计一下24年合肥基地苏州晶茂物流全年发运量是多少？
- 业务反馈：问题汇总全年发运量合计数据不对
- 状态：OK；intent/query_key：aggregate/hist_mw_by_origin_and_carrier
- filters/slots：`{"year": 2024, "origin_place": "合肥", "carrier_name": "晶茂"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['shipment_mw']；rows=1
- 摘要：2024年合肥基地、承运商晶茂的总发运量为1900.468MW。
- 前几行：`[{"shipment_mw": 1900.468}]`

## Sheet1-R14#1 / logistics
- 问题：统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并分别列出询比价和招标的发运量
- 业务反馈：无法导出，检索不到地址
- 状态：UNSUPPORTED_QUESTION；intent/query_key：unsupported/None
- filters/slots：`{}`
- 展示：display_type=unsupported；chart_type=None；columns=[]；rows=0
- 摘要：当前历史台账缺少稳定询比价/招标拆分字段，无法可靠回答高运费项目地的采购方式拆分。 可改问方向：可以先改问：24 年创维客户项目地运费超过 20 万的收货地址有哪些？；如需询比价/招标拆分，请先补齐并确认采购方式字段口径。
- warnings：['当前历史台账缺少稳定询比价/招标拆分字段，无法可靠回答高运费项目地的采购方式拆分。', '可以先改问：24 年创维客户项目地运费超过 20 万的收货地址有哪些？', '如需询比价/招标拆分，请先补齐并确认采购方式字段口径。']

## Sheet1-R15#1 / logistics
- 问题：025年始发地合肥，车型 17.5 ，发出了多少车？
- 业务反馈：相关数据较少，请联系客服 朱长超
- 状态：OK；intent/query_key：aggregate/hist_vehicle_type_trip_count
- filters/slots：`{"year": 2025, "vehicle_type": "17.5", "origin_place": "合肥"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['shipment_trip_count']；rows=1
- 摘要：2025年合肥基地17.5车合计发运9,816车次。
- 前几行：`[{"shipment_trip_count": 9816.0}]`

## Sheet1-R16#1 / logistics
- 问题：2024年1月份发运总量是多少MW？
- 业务反馈：24年1月正确的发运总量为364.12MW，两次回答都错误9,164.757 MW、278.047 MW，且答案只显示了年份没有月份
- 状态：OK；intent/query_key：aggregate/hist_mw_summary
- filters/slots：`{"year": 2024, "months": [1]}`
- 展示：display_type=summary_cards；chart_type=None；columns=['shipment_mw']；rows=1
- 摘要：2024年1月总发运量为364.123MW。
- 前几行：`[{"shipment_mw": 364.123}]`

## Sheet1-R17#1 / logistics
- 问题：2024年1月份客户华阳的总发运量是多少MW？
- 业务反馈：结果比较接近，正确值为200.18712MW，答案只显示了年份没有月份
- 状态：OK；intent/query_key：aggregate/hist_customer_mw
- filters/slots：`{"year": 2024, "months": [1], "customer_name": "华阳"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['shipment_mw']；rows=1
- 摘要：2024年1月华阳总发运量为86.506MW。
- 前几行：`[{"shipment_mw": 86.506, "matched_customer_names": ["华阳集团（阳泉）新能源销售有限公司", "华阳集团（阳泉）新能源销售有限公司(常规包装", "华阳集团（阳泉）新能源销售有限公司（常规包装）", "华阳集团（阳泉）新能源销售有限公司(鑫阳光包装）"], "scope_label": "2024年1月"}]`
- warnings：['当前按客户名前缀归并，命中了 4 个客户名变体。']

## Sheet1-R18#1 / logistics
- 问题：26年经营计划用车运费是多少？
- 业务反馈：实际《经营计划》或（经营计划部》  统计结果应为13581元，回答的车次和当期总运费是不对的
- 状态：OK；intent/query_key：aggregate/sys_special_total_fee
- filters/slots：`{"year": 2026, "special_scope": "planning"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['total_fee', 'parse_fail_count', 'price_missing_count']；rows=1
- 摘要：2026年经营计划用车按锁定口径统计的总运费为134,378.00元。
- 前几行：`[{"total_fee": 134378.0, "parse_fail_count": 0.0, "price_missing_count": 0.0}]`

## Sheet1-R18#2 / logistics
- 问题：26年 经营计划 运费是多少？
- 业务反馈：实际《经营计划》或（经营计划部》  统计结果应为13581元，回答的车次和当期总运费是不对的
- 状态：OK；intent/query_key：aggregate/sys_special_total_fee
- filters/slots：`{"year": 2026, "special_scope": "planning"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['total_fee', 'parse_fail_count', 'price_missing_count']；rows=1
- 摘要：2026年经营计划用车按锁定口径统计的总运费为134,378.00元。
- 前几行：`[{"total_fee": 134378.0, "parse_fail_count": 0.0, "price_missing_count": 0.0}]`

## Sheet1-R19#1 / logistics
- 问题：2026年1月份总发运量是多少MW？
- 业务反馈：答非所问
- 状态：OK；intent/query_key：aggregate/sys_mw_and_trip_count
- filters/slots：`{"year": 2026, "months": [1], "transport_mode": null, "base_code": null, "base_name": null, "monthly_breakdown": false}`
- 展示：display_type=summary_cards；chart_type=None；columns=['shipment_mw', 'power_missing_count', 'pickup_date_missing_count', 'strict_scope_task_count', 'pickup_date_available_count']；rows=1
- 摘要：2026年1月合计发运量为432.364MW。
- 前几行：`[{"shipment_mw": 432.364, "shipment_trip_count": 282, "power_missing_count": 49, "pickup_date_missing_count": 0, "strict_scope_task_count": 368, "year_task_count": 1233, "pickup_date_available_count": 1233, "region_coverage": {"direct_area_count": 368, "province_fallback_count": 0, "other_count": 0}, "year_region_coverage": {"direct_area_count": 1233, "province_fallback_count": 0, "other_count": 0}}]`
- warnings：['共有 49 条 product 记录 power 缺失，未纳入 MW 统计。', '区域口径优先使用 delivery_area；为空时用 delivery_province 映射七大区域，异常值归入“其他”。', '当前统计范围区域覆盖率：delivery_area 直接命中 1233 条，省份兜底 0 条，归入其他 0 条。']

## Sheet1-R19#2 / logistics
- 问题：总共发了多少车次？
- 业务反馈：答非所问
- 状态：CLARIFICATION_REQUIRED；intent/query_key：clarification/None
- filters/slots：`{}`
- 展示：display_type=clarification；chart_type=None；columns=[]；rows=0
- 摘要：当前问题还不够明确，需先补充口径。
- warnings：['当前问题需要澄清后才能继续查询。']

## Sheet1-R20#1 / logistics
- 问题：统计一下阜宁基地2026年辅料送样总计运费是多少钱?
- 状态：OK；intent/query_key：aggregate/sys_total_fee_by_filters
- filters/slots：`{"year": 2026, "months": [], "base_code": "2", "base_name": "阜宁基地", "special_scope": "sample"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['total_fee', 'task_count', 'parse_fail_count', 'price_missing_count']；rows=1
- 摘要：2026年阜宁基地按当前系统口径统计的总运费为105,399.00元。
- 前几行：`[{"total_fee": 105399.0, "task_count": 60, "parse_fail_count": 0.0, "price_missing_count": 0.0}]`

## Sheet1-R21#1 / logistics
- 问题：26年 经营计划 刘娟 用车总费用是多少
- 业务反馈：输出为  经营计划  用车总费用，后面个人申请费用无法单独调出 ，真实结果是：
1.使用部门：经营计划和计划  都纳入一起
2.增加个人的检索，费用为13621
- 状态：OK；intent/query_key：aggregate/sys_special_total_fee
- filters/slots：`{"year": 2026, "special_scope": "planning"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['total_fee', 'parse_fail_count', 'price_missing_count']；rows=1
- 摘要：2026年经营计划用车按锁定口径统计的总运费为134,378.00元。
- 前几行：`[{"total_fee": 134378.0, "parse_fail_count": 0.0, "price_missing_count": 0.0}]`

## Sheet1-R22#1 / logistics
- 问题：24年 1-12月 每个月的江苏省的17.5均价是多少？
- 业务反馈：需要检索的是月度使用车型的总运量和总费用，相除得到单瓦价
- 状态：OK；intent/query_key：aggregate/hist_route_pricing_analysis
- filters/slots：`{"years": [2024], "vehicle_type": "17.5", "view_mode": "monthly_avg", "province": "江苏", "year": 2024}`
- 展示：display_type=mixed；chart_type=bar；columns=['biz_month', 'avg_fee', 'row_count']；rows=12
- 摘要：2024年江苏17.5车每月平均运费已按月份返回。
- 前几行：`[{"biz_month": "2024-01", "avg_fee": 8087.0, "row_count": 33}, {"biz_month": "2024-02", "avg_fee": 5417.0, "row_count": 7}]`

## Sheet1-R22#2 / logistics
- 问题：24年 1-12月 目的地是江苏省的单瓦价是多少
- 业务反馈：需要检索的是月度使用车型的总运量和总费用，相除得到单瓦价
- 状态：OK；intent/query_key：aggregate/hist_unit_fee_per_watt
- filters/slots：`{"year": 2024, "province": "江苏", "months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "include_extra_fee": false, "monthly_breakdown": true}`
- 展示：display_type=mixed；chart_type=bar；columns=['biz_month', 'total_fee_amount', 'extra_fee_amount', 'shipment_mw', 'unit_fee_per_watt']；rows=12
- 摘要：2024年江苏按月单瓦运输成本已返回。
- 前几行：`[{"biz_month": "2024-01", "total_fee_amount": 541677.0, "extra_fee_amount": 0.0, "shipment_mw": 78.272, "unit_fee_per_watt": 0.00692045}, {"biz_month": "2024-02", "total_fee_amount": 125397.0, "extra_fee_amount": 0.0, "shipment_mw": 19.006, "unit_fee_per_watt": 0.00659759}]`

## Sheet1-R23#1 / logistics
- 问题：项目名称：国科新能源有限公司 已发出总运量是多少？江苏苏美达电力运营有限公司 项目 总发运量是多少
- 业务反馈：询问单个项目发运量，结果相同，错误了
- 状态：UNSUPPORTED_QUESTION；intent/query_key：unsupported/None
- filters/slots：`{}`
- 展示：display_type=unsupported；chart_type=None；columns=[]；rows=0
- 摘要：当前项目名称尚未沉淀为稳定可复用统计维度，直接按项目名称汇总容易误导。 可改问方向：可以改问：某客户在某一年的总发运量是多少 MW？；如果必须按项目名称统计，请先确认项目名称归一规则和数据 owner 口径。
- warnings：['当前项目名称尚未沉淀为稳定可复用统计维度，直接按项目名称汇总容易误导。', '可以改问：某客户在某一年的总发运量是多少 MW？', '如果必须按项目名称统计，请先确认项目名称归一规则和数据 owner 口径。']

## Sheet1-R24#1 / logistics
- 问题：帮我看一下26年2月客户：广东粤电阳西新能源有限公司总运费多少
- 业务反馈：实际发运10车，运费140600
- 状态：OK；intent/query_key：aggregate/sys_total_fee_by_filters
- filters/slots：`{"year": 2026, "months": [2], "customer_name": "广东粤电阳西新能源有限公司"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['total_fee', 'task_count', 'parse_fail_count', 'price_missing_count']；rows=1
- 摘要：2026年2月客户广东粤电阳西新能源有限公司按当前系统口径统计的总运费为140,600.00元。
- 前几行：`[{"total_fee": 140600.0, "task_count": 4, "parse_fail_count": 0.0, "price_missing_count": 0.0}]`

## Sheet1-R25#1 / logistics
- 问题：帮我看一下从合肥基地始发，26年1-2月客户：海南创维新能源投资有限公司 总运费多少
- 业务反馈：未能区分各基地数据
- 状态：OK；intent/query_key：aggregate/sys_total_fee_by_filters
- filters/slots：`{"year": 2026, "months": [1, 2], "base_code": "1", "base_name": "合肥基地", "customer_name": "海南创维新能源投资有限公司"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['total_fee', 'task_count', 'parse_fail_count', 'price_missing_count']；rows=1
- 摘要：2026年1月、2月合肥基地客户海南创维新能源投资有限公司按当前系统口径统计的总运费为38,294.00元。
- 前几行：`[{"total_fee": 38294.0, "task_count": 4, "parse_fail_count": 0.0, "price_missing_count": 0.0}]`

## Sheet1-R26#1 / logistics
- 问题：对比24年和25年合肥发广州 17.5运价？
- 业务反馈：问题2和3能回答，单项解决，但两个对比就不能呈现；问题1回答的是问题3的结果
- 状态：OK；intent/query_key：compare/hist_route_pricing_analysis
- filters/slots：`{"years": [2024, 2025], "vehicle_type": "17.5", "view_mode": "year_compare", "origin_place": "合肥", "city": "广州"}`
- 展示：display_type=mixed；chart_type=bar；columns=['biz_year', 'avg_fee', 'row_count']；rows=2
- 摘要：2024年与2025年合肥发广州17.5车运价对比已按年份返回。
- 前几行：`[{"biz_year": 2024, "avg_fee": 11442.0, "row_count": 2}, {"biz_year": 2025, "avg_fee": 52400.0, "row_count": 1}]`

## Sheet1-R26#2 / logistics
- 问题：25年合肥发广州 17.5运价？
- 业务反馈：问题2和3能回答，单项解决，但两个对比就不能呈现；问题1回答的是问题3的结果
- 状态：OK；intent/query_key：aggregate/hist_route_pricing_analysis
- filters/slots：`{"years": [2025], "vehicle_type": "17.5", "view_mode": "avg_fee", "origin_place": "合肥", "city": "广州"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['avg_fee', 'row_count']；rows=1
- 摘要：2025年合肥发广州17.5车平均运费为52,400元。
- 前几行：`[{"avg_fee": 52400.0, "row_count": 1}]`

## Sheet1-R26#3 / logistics
- 问题：24年合肥发广州 17.5运价
- 业务反馈：问题2和3能回答，单项解决，但两个对比就不能呈现；问题1回答的是问题3的结果
- 状态：OK；intent/query_key：aggregate/hist_route_pricing_analysis
- filters/slots：`{"years": [2024], "vehicle_type": "17.5", "view_mode": "avg_fee", "origin_place": "合肥", "city": "广州"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['avg_fee', 'row_count']；rows=1
- 摘要：2024年合肥发广州17.5车平均运费为11,442元。
- 前几行：`[{"avg_fee": 11442.0, "row_count": 2}]`

## Sheet1-R27#1 / logistics
- 问题：帮我查一下2026年阜宁基地1月份晶茂物流总计运费是多少钱
- 业务反馈：实际费用为236985，统计数据有误
- 状态：OK；intent/query_key：aggregate/sys_total_fee_by_filters
- filters/slots：`{"year": 2026, "months": [1], "base_code": "2", "base_name": "阜宁基地", "company_name": "晶茂物流"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['total_fee', 'task_count', 'parse_fail_count', 'price_missing_count']；rows=1
- 摘要：2026年1月阜宁基地承运商晶茂物流按当前系统口径统计的总运费为234,202.00元。
- 前几行：`[{"total_fee": 234202.0, "task_count": 25, "parse_fail_count": 0.0, "price_missing_count": 0.0}]`

## Sheet1-R28#1 / logistics
- 问题：2月份单W运输成本是多少（（2月运费总价格+额外费用）/运输组件总W数）
- 业务反馈：未输出结果。正确值：“发货类型”只看正常发货，不看辅料送样，2月正常发货总运输价格+额外费用=1914325元，总运输W数（功率*分派数量）为129922225W，单W成本0.014元/W，若功率列有“720W”类的字样，不是纯数字，则取“W”前面的数字段720
- 状态：OK；intent/query_key：aggregate/sys_unit_fee_per_watt
- filters/slots：`{"year": 2026, "months": [2], "company_name": null, "include_extra_cost": true, "default_year_scope": true, "default_year_scope_label": "2026正式系统"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['unit_fee_per_watt', 'total_fee', 'extra_fee_amount', 'shipment_mw', 'task_count', 'parse_fail_count', 'price_missing_count', 'power_missing_count']；rows=1
- 摘要：2026年2月按（总运费+额外费用）/总发运瓦数口径统计的单瓦运输成本为0.014598元/瓦。
- 前几行：`[{"total_fee": 1893970.0, "extra_fee_amount": 2600.0, "task_count": 135, "parse_fail_count": 1.0, "price_missing_count": 0.0, "shipment_mw": 129.922, "power_missing_count": 29.0, "unit_fee_per_watt": 0.014598}]`
- warnings：['当前题目未给统计年份，系统默认按2026正式系统月份口径计算。', '共有 1 条任务的 project_name 无法解析总车数，未纳入总运费统计。', '共有 29 条 product 记录 power 缺失，未纳入单瓦成本统计。']

## Sheet1-R29#1 / logistics
- 问题：2026年1月份总共发货多少MW？
- 业务反馈：不同的问题回答的结果却一样；1~2月铁路运输实际问题实际为23.78MW
- 状态：OK；intent/query_key：aggregate/sys_mw_and_trip_count
- filters/slots：`{"year": 2026, "months": [1], "transport_mode": null, "base_code": null, "base_name": null, "monthly_breakdown": false}`
- 展示：display_type=summary_cards；chart_type=None；columns=['shipment_mw', 'power_missing_count', 'pickup_date_missing_count', 'strict_scope_task_count', 'pickup_date_available_count']；rows=1
- 摘要：2026年1月合计发运量为432.364MW。
- 前几行：`[{"shipment_mw": 432.364, "shipment_trip_count": 282, "power_missing_count": 49, "pickup_date_missing_count": 0, "strict_scope_task_count": 368, "year_task_count": 1233, "pickup_date_available_count": 1233, "region_coverage": {"direct_area_count": 368, "province_fallback_count": 0, "other_count": 0}, "year_region_coverage": {"direct_area_count": 1233, "province_fallback_count": 0, "other_count": 0}}]`
- warnings：['共有 49 条 product 记录 power 缺失，未纳入 MW 统计。', '区域口径优先使用 delivery_area；为空时用 delivery_province 映射七大区域，异常值归入“其他”。', '当前统计范围区域覆盖率：delivery_area 直接命中 1233 条，省份兜底 0 条，归入其他 0 条。']

## Sheet1-R29#2 / logistics
- 问题：2026年1月份、2月份运输方式为铁路的运输总量是多少MW？
- 业务反馈：不同的问题回答的结果却一样；1~2月铁路运输实际问题实际为23.78MW
- 状态：OK；intent/query_key：aggregate/sys_mw_and_trip_count
- filters/slots：`{"year": 2026, "months": [1, 2], "transport_mode": "铁路", "base_code": null, "base_name": null, "monthly_breakdown": false}`
- 展示：display_type=summary_cards；chart_type=None；columns=['shipment_mw', 'power_missing_count', 'pickup_date_missing_count', 'strict_scope_task_count', 'pickup_date_available_count']；rows=1
- 摘要：2026年1月、2月铁路方式合计发运量为0MW。
- 前几行：`[{"shipment_mw": null, "shipment_trip_count": 0, "power_missing_count": 4, "pickup_date_missing_count": 0, "strict_scope_task_count": 4, "year_task_count": 1233, "pickup_date_available_count": 1233, "region_coverage": {"direct_area_count": 4, "province_fallback_count": 0, "other_count": 0}, "year_region_coverage": {"direct_area_count": 1233, "province_fallback_count": 0, "other_count": 0}}]`
- warnings：['共有 4 条 product 记录 power 缺失，未纳入 MW 统计。', '区域口径优先使用 delivery_area；为空时用 delivery_province 映射七大区域，异常值归入“其他”。', '当前统计范围区域覆盖率：delivery_area 直接命中 1233 条，省份兜底 0 条，归入其他 0 条。']

## Sheet1-R30#1 / plan_bom
- 问题：订单00104的的玻璃、间隙贴膜，焊带、汇流条、接线盒的规格描述？
- 业务反馈：未输出该订单BOM配置
- 状态：OK；intent/query_key：single_order_material_specs/None
- filters/slots：`{"order_tail_no": ["00104"], "compare_orders": ["00104"], "order_name_hint": null, "material_category": ["glass", "gap_film", "interconnect_bar", "busbar", "junction_box"], "non_core_material_category": [], "material_alias": ["玻璃", "间隙贴膜", "焊带", "汇流条", "接线盒", "线盒"], "bom_version": [], "model": null, "year": null, "country": null, "target_power_ratio": {}, "supplier_name": null, "benchmark": null, "explicit_power_configuration": {}, "need_table": false, "need_excel": false, "output_format": "narrative"}`
- 展示：display_type=table；chart_type=None；columns=['material_category', 'material_name', 'description', 'standard_usage', 'unit']；rows=14
- 摘要：已查询订单 NT12R/66GDF(法国-2026-00104)Bill of materials 的 14 条 BOM 材料规格。
- 前几行：`[{"order_no": "GCL-XXJC-JSPS-2026-00104", "order_name": null, "version_no": "A1", "material_category": "玻璃", "material_name": "光伏玻璃", "description": "光伏玻璃\\彩虹\\2376*1128*2mm\\压花\\半钢化\\双镀膜\\CG01超高透,透光率≥94.5%\\有价值", "sap_code": "1000537640", "standard_usage": "1000.000000", "unit": "片", "source_file": "manual_import_source"}, {"order_no": "GCL-XXJC-JSPS-2026-00104", "order_name": null, "version_no": "A1", "material_category": "玻璃", "material_name": "光伏玻璃", "description": "光伏玻璃\\彩虹\\2376*1128*2mm\\压花\\半钢化\\非镀膜\\GCL/XXJC/2-RD-5682无涂釉\\有价值", "sap_code": "1000448708", "standard_usage": "1000.000000", "unit": "片", "source_file": "manual_import_source"}]`

## Sheet1-R31#1 / plan_bom
- 问题：订单00067和订单00106玻璃、间隙贴膜，焊带、汇流条、接线盒的规格描述有什么不一样，并用表格统计出来
- 业务反馈：为了更准确查询，请补充产品型号或规格（如 GCL-M10/72H-555、550W）。
- 状态：CLARIFICATION_REQUIRED；intent/query_key：cross_order_material_compare/None
- filters/slots：`{"order_tail_no": ["00067", "00106"], "compare_orders": ["00067", "00106"], "order_name_hint": null, "material_category": ["glass", "gap_film", "interconnect_bar", "busbar", "junction_box"], "non_core_material_category": [], "material_alias": ["玻璃", "间隙贴膜", "焊带", "汇流条", "接线盒", "线盒"], "bom_version": [], "model": null, "year": null, "country": null, "target_power_ratio": {}, "supplier_name": null, "benchmark": null, "explicit_power_configuration": {}, "need_table": true, "need_excel": false, "output_format": "table"}`
- 展示：display_type=clarification；chart_type=None；columns=[]；rows=0
- 摘要：当前问题缺少或存在歧义的槽位：order_identity。请补充订单、版本、材料或查询范围。

## Sheet1-R32#1 / plan_bom
- 问题：哥伦比亚COEXITO -2026-00067，NT10/78GDF的线盒物料描述
- 业务反馈：正确答案：接线盒\GCL\GCL-N1xyz\GCL-02\+300/-200mm\1500V\25A\GCL4045\三分体含连接器线长\-\有价值
- 状态：OK；intent/query_key：single_order_material_specs/None
- filters/slots：`{"order_tail_no": ["00067"], "compare_orders": ["00067"], "order_name_hint": null, "material_category": ["junction_box"], "non_core_material_category": [], "material_alias": ["线盒"], "bom_version": [], "model": "NT10-78GDF", "year": 2026, "country": "哥伦比亚", "target_power_ratio": {}, "supplier_name": null, "benchmark": null, "explicit_power_configuration": {}, "need_table": false, "need_excel": false, "output_format": "narrative"}`
- 展示：display_type=table；chart_type=None；columns=['material_category', 'material_name', 'description', 'standard_usage', 'unit']；rows=1
- 摘要：已查询订单 NT10/78GDF（哥伦比亚COEXITO -2026-00067） 的 1 条 BOM 材料规格。
- 前几行：`[{"order_no": "GCL-XXJC-JSPS-2026-00067", "order_name": null, "version_no": "A1", "material_category": "接线盒", "material_name": "接线盒", "description": "接线盒\\GCL\\GCL-N1xyz\\GCL-02\\+300/-200mm\\1500V\\25A\\GCL4045\\三分体含连接器线长\\-\\有价值", "sap_code": "1000461172", "standard_usage": "1000.000000", "unit": "个", "source_file": "manual_import_source"}]`

## Sheet1-R33#1 / plan_bom
- 问题：NT12R/66GDF（法国Synapsun-2026-00114）订单的玻璃，焊带，汇流条，间隙贴膜线盒的规格
- 业务反馈：可以输出单
- 状态：OK；intent/query_key：single_order_material_specs/None
- filters/slots：`{"order_tail_no": ["00114"], "compare_orders": ["00114"], "order_name_hint": "法国Synapsun-2026-00114", "material_category": ["glass", "gap_film", "interconnect_bar", "busbar", "junction_box"], "non_core_material_category": [], "material_alias": ["玻璃", "间隙贴膜", "焊带", "汇流条", "线盒"], "bom_version": [], "model": "NT12R-66GDF", "year": 2026, "country": "法国", "target_power_ratio": {}, "supplier_name": null, "benchmark": null, "explicit_power_configuration": {}, "need_table": false, "need_excel": false, "output_format": "narrative"}`
- 展示：display_type=table；chart_type=None；columns=['material_category', 'material_name', 'description', 'standard_usage', 'unit']；rows=10
- 摘要：已查询订单 NT12R/66GDF（法国Synapsun-2026-00114） 的 10 条 BOM 材料规格。
- 前几行：`[{"order_no": "GCL-XXJC-JSPS-2026-00114", "order_name": null, "version_no": "A0", "material_category": "玻璃", "material_name": "光伏玻璃", "description": "光伏玻璃\\彩虹\\2376*1128*2mm\\压花\\半钢化\\双镀膜\\CG01超高透,透光率≥94.5%\\有价值", "sap_code": "1000537640", "standard_usage": "1000.000000", "unit": "片", "source_file": "manual_import_source"}, {"order_no": "GCL-XXJC-JSPS-2026-00114", "order_name": null, "version_no": "A0", "material_category": "玻璃", "material_name": "光伏玻璃", "description": "光伏玻璃\\彩虹\\2376*1128*2mm\\压花\\半钢化\\非镀膜\\GCL/XXJC/2-RD-5682无涂釉\\有价值", "sap_code": "1000448708", "standard_usage": "1000.000000", "unit": "片", "source_file": "manual_import_source"}]`

## Sheet1-R34#1 / plan_bom
- 问题：NT12R/66GDF（法国Synapsun-2026-00114）订单的玻璃，焊带，汇流条，间隙贴膜线盒的规格，并生成表格
- 业务反馈：输出的明细是对的，但是输出的数据较多，表格太大，展示不开
- 状态：OK；intent/query_key：single_order_material_specs/None
- filters/slots：`{"order_tail_no": ["00114"], "compare_orders": ["00114"], "order_name_hint": "法国Synapsun-2026-00114", "material_category": ["glass", "gap_film", "interconnect_bar", "busbar", "junction_box"], "non_core_material_category": [], "material_alias": ["玻璃", "间隙贴膜", "焊带", "汇流条", "线盒"], "bom_version": [], "model": "NT12R-66GDF", "year": 2026, "country": "法国", "target_power_ratio": {}, "supplier_name": null, "benchmark": null, "explicit_power_configuration": {}, "need_table": true, "need_excel": false, "output_format": "table"}`
- 展示：display_type=table；chart_type=None；columns=['material_category', 'material_name', 'description', 'standard_usage', 'unit']；rows=10
- 摘要：已查询订单 NT12R/66GDF（法国Synapsun-2026-00114） 的 10 条 BOM 材料规格。
- 前几行：`[{"order_no": "GCL-XXJC-JSPS-2026-00114", "order_name": null, "version_no": "A0", "material_category": "玻璃", "material_name": "光伏玻璃", "description": "光伏玻璃\\彩虹\\2376*1128*2mm\\压花\\半钢化\\双镀膜\\CG01超高透,透光率≥94.5%\\有价值", "sap_code": "1000537640", "standard_usage": "1000.000000", "unit": "片", "source_file": "manual_import_source"}, {"order_no": "GCL-XXJC-JSPS-2026-00114", "order_name": null, "version_no": "A0", "material_category": "玻璃", "material_name": "光伏玻璃", "description": "光伏玻璃\\彩虹\\2376*1128*2mm\\压花\\半钢化\\非镀膜\\GCL/XXJC/2-RD-5682无涂釉\\有价值", "sap_code": "1000448708", "standard_usage": "1000.000000", "unit": "片", "source_file": "manual_import_source"}]`

## Sheet1-R35#1 / plan_bom
- 问题：NT12R/66GDF（法国Synapsun-2026-00114）和NT12R/66GDF（法国Synapsun-2026-00114）订单的玻璃，焊带，汇流条，间隙贴膜线盒的规格对比
- 业务反馈：只能输出一个订单的配置，另一个清单的显示不出，无法做对比
- 状态：CLARIFICATION_REQUIRED；intent/query_key：material_consistency_check/None
- filters/slots：`{"order_tail_no": ["00114"], "compare_orders": ["00114"], "order_name_hint": "法国Synapsun-2026-00114", "material_category": ["glass", "gap_film", "interconnect_bar", "busbar", "junction_box"], "non_core_material_category": [], "material_alias": ["玻璃", "间隙贴膜", "焊带", "汇流条", "线盒"], "bom_version": [], "model": "NT12R-66GDF", "year": 2026, "country": "法国", "target_power_ratio": {}, "supplier_name": null, "benchmark": null, "explicit_power_configuration": {}, "need_table": false, "need_excel": false, "output_format": "narrative"}`
- 展示：display_type=clarification；chart_type=None；columns=[]；rows=0
- 摘要：当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。

## Sheet1-R36#1 / plan_bom
- 问题：NT12R/66GDF（法国Synapsun-2026-00114）和NT12R/66GDF(法国-2026-00104)Bill of materials订单的玻璃，焊带，汇流条，间隙贴膜线盒的规格对比
- 业务反馈：1、输出的结果是对的，像来源和版本和SAP号是不是都可以去掉，太多了。
2、玻璃有好几款，每个玻璃可不可以有分段落，现在是全部集中在一起，比较难找，不明显
- 状态：OK；intent/query_key：cross_order_material_compare/None
- filters/slots：`{"order_tail_no": ["00114", "00104"], "compare_orders": ["00114", "00104"], "order_name_hint": "NT12R/66GDF(法国-2026-00104)Bill of materials", "material_category": ["glass", "gap_film", "interconnect_bar", "busbar", "junction_box"], "non_core_material_category": [], "material_alias": ["玻璃", "间隙贴膜", "焊带", "汇流条", "线盒"], "bom_version": [], "model": "NT12R-66GDF", "year": 2026, "country": "法国", "target_power_ratio": {}, "supplier_name": null, "benchmark": null, "explicit_power_configuration": {}, "need_table": false, "need_excel": false, "output_format": "narrative"}`
- 展示：display_type=comparison_table；chart_type=None；columns=['diff_type', 'material_category', 'left_order', 'left_description', 'right_order', 'right_description', 'changed_fields']；rows=12
- 摘要：已完成 BOM 差异对比，变化 8 条，仅左侧 0 条，仅右侧 4 条。
- 前几行：`[{"diff_type": "字段变化", "material_category": "汇流条", "left_order": "GCL-XXJC-JSPS-2026-00114", "left_description": "汇流条\\0.35*4mm\\反光\\GCL\\轴装\\6040\\-\\有价值", "right_order": "GCL-XXJC-JSPS-2026-00104", "right_description": "汇流条\\0.35*4mm\\反光\\GCL\\轴装\\6040\\-\\有价值", "changed_fields": "remark"}, {"diff_type": "字段变化", "material_category": "汇流条", "left_order": "GCL-XXJC-JSPS-2026-00114", "left_description": "汇流条\\0.4*6mm\\反光\\GCL\\轴装\\6040\\-\\有价值", "right_order": "GCL-XXJC-JSPS-2026-00104", "right_description": "汇流条\\0.4*6mm\\反光\\GCL\\轴装\\6040\\-\\有价值", "changed_fields": "remark"}]`

## Sheet1-R37#1 / plan_bom
- 问题：针对现有的订单把玻璃，焊带，汇流条，间隙贴膜线盒的规格并用表格的形式呈现
- 业务反馈：没有用表格的形式展现
- 状态：CLARIFICATION_REQUIRED；intent/query_key：specific_material_query/None
- filters/slots：`{"order_tail_no": [], "compare_orders": [], "order_name_hint": null, "material_category": ["glass", "gap_film", "interconnect_bar", "busbar", "junction_box"], "non_core_material_category": [], "material_alias": ["玻璃", "间隙贴膜", "焊带", "汇流条", "线盒"], "bom_version": [], "model": null, "year": null, "country": null, "target_power_ratio": {}, "supplier_name": null, "benchmark": null, "explicit_power_configuration": {}, "need_table": true, "need_excel": false, "output_format": "table"}`
- 展示：display_type=clarification；chart_type=None；columns=[]；rows=0
- 摘要：当前问题缺少或存在歧义的槽位：order_id。请补充订单、版本、材料或查询范围。

## Sheet1-R38#1 / plan_bom
- 问题：NT12/66GDF（苏格兰-2026-00048），NT10/78GDF（泰州中来 -2026-00127）NT12R/66GDF（意大利-2026-00097），订单的玻璃，间隙贴膜，接线盒，汇流条，焊带规格 并用EXCEL表格形式展现出来
- 状态：OK；intent/query_key：multi_order_material_table/None
- filters/slots：`{"order_tail_no": ["00048", "00127", "00097"], "compare_orders": ["00048", "00127", "00097"], "order_name_hint": "苏格兰-2026-00048", "material_category": ["glass", "gap_film", "interconnect_bar", "busbar", "junction_box"], "non_core_material_category": [], "material_alias": ["玻璃", "间隙贴膜", "焊带", "汇流条", "接线盒", "线盒"], "bom_version": [], "model": "NT12-66GDF", "year": 2026, "country": "意大利", "target_power_ratio": {}, "supplier_name": null, "benchmark": null, "explicit_power_configuration": {}, "need_table": true, "need_excel": true, "output_format": "excel"}`
- 展示：display_type=table；chart_type=None；columns=['material_category', 'material_name', 'description', 'standard_usage', 'unit']；rows=35
- 摘要：已按当前条件生成 35 条计划 BOM 材料清单。
- 前几行：`[{"order_no": "GCL-XXJC-JSPS-2026-00048", "order_name": "NT12/66GDF（苏格兰-2026-00048）", "version_no": "A1", "material_category": "玻璃", "material_name": "光伏玻璃", "description": "光伏玻璃\\中建材\\2378*1297*2mm\\压花\\半钢化\\双镀膜\\-\\有价值", "sap_code": "1000414301", "standard_usage": "1000.000000", "unit": "片", "source_file": "NT1266GDF(ΦïÅµá╝σà░-2026-00048)Billofmaterials-B(2).xls"}, {"order_no": "GCL-XXJC-JSPS-2026-00048", "order_name": "NT12/66GDF（苏格兰-2026-00048）", "version_no": "A1", "material_category": "玻璃", "material_name": "光伏玻璃", "description": "光伏玻璃\\中建材\\2378*1297*2mm\\压花\\半钢化\\非镀膜\\GCL/XXJC/2-RD-5684无涂釉\\有价值", "sap_code": "1000448881", "standard_usage": "1000.000000", "unit": "片", "source_file": "NT1266GDF(ΦïÅµá╝σà░-2026-00048)Billofmaterials-B(2).xls"}]`

## Sheet1-R39#1 / plan_bom
- 问题：创维210N—00106，0.24+0.26焊带+高透玻璃+间隙铝膜+300/200线长，计量院基准，单一需求720功率，各个供应商厂家从什么电池效率可以满足
- 业务反馈：这个是没有上传BOM，显示的也是无法检索
- 状态：CLARIFICATION_REQUIRED；intent/query_key：plan_power_supplier_recommendation/None
- filters/slots：`{"order_tail_no": ["00106"], "compare_orders": ["00106"], "order_name_hint": null, "material_category": ["glass", "interconnect_bar", "junction_box"], "non_core_material_category": ["cell"], "material_alias": ["玻璃", "焊带", "线长", "电池"], "bom_version": [], "model": null, "year": null, "country": null, "target_power_ratio": {"720": 1.0}, "supplier_name": null, "benchmark": "中国计量院", "explicit_power_configuration": {"ribbon": "0.24+0.26", "glass": "高透+间隙铝膜", "cable": "300/200线长", "benchmark": "中国计量院"}, "need_table": false, "need_excel": false, "output_format": "narrative"}`
- 展示：display_type=clarification；chart_type=None；columns=[]；rows=0
- 摘要：当前订单条件命中 3 个 BOM 候选，请先确认订单或文件实例后再做功率预测。候选包括：1. NT10/78GDF(江苏汉腾-2026-00106)Bill of materials（GCL-XXJC-JSPS-2026-00106，版本 A0）；2. NT10/78GDF(石家庄科林-2026-00106)Bill of materials（GCL-XXJC-JSPS-2026-00106，版本 A0）；3. NT12/66GDF(创维-A2026-00106)Bill of materials（GCL-XXJC-JSPS(A)-2026-00106，版本 A0）。你输入的“创维210N”未匹配当前候选名称，请确认是否为同一订单/…

## Sheet1-R40#1 / plan_bom
- 问题：NT12R/66GDF（深圳建融-2025-01073）0.24焊带+双镀玻璃+300/200线长，北德基准，615功率，各个供应商厂家从什么电池效率可以满足
- 业务反馈：无法检索
- 状态：OK；intent/query_key：plan_power_supplier_recommendation/None
- filters/slots：`{"order_tail_no": ["01073"], "compare_orders": ["01073"], "order_name_hint": "深圳建融-2025-01073", "material_category": ["glass", "interconnect_bar", "junction_box"], "non_core_material_category": ["cell"], "material_alias": ["玻璃", "焊带", "线长", "电池"], "bom_version": [], "model": "NT12R-66GDF", "year": 2025, "country": null, "target_power_ratio": {"615": 1.0}, "supplier_name": null, "benchmark": "新北德", "explicit_power_configuration": {"ribbon": "0.24", "glass": "双镀", "cable": "300/200线长", "benchmark": "新北德"}, "need_table": false, "need_excel": false, "output_format": "narrative"}`
- 展示：display_type=table；chart_type=None；columns=['供应商', '目标功率档', '目标比例', '预测比例', 'CTM 值', '中心功率', '建议效率段', '落档比例预估']；rows=6
- 摘要：已按订单 GCL-XXJC-JSPS-2025-01073 的 BOM 配置和目标功率比例完成供应商推荐，当前最高匹配供应商为 中润。
- 前几行：`[{"供应商": "中润", "目标功率档": "615W", "目标比例": 100.0, "预测比例": 1.5869, "CTM 值": "96.94%", "中心功率": 620.55, "建议效率段": "25.5%、25.6%", "落档比例预估": "25.5%→615W 12.98%、620W 82.08%\n25.6%→615W 2.59%、620W 77.17%"}, {"供应商": "和光同程", "目标功率档": "615W", "目标比例": 100.0, "预测比例": 1.9728, "CTM 值": "97.01%", "中心功率": 620.95, "建议效率段": "25.5%、25.6%", "落档比例预估": "25.5%→615W 8.84%、620W 83.48%\n25.6%→615W 1.50%、620W 71.37%"}]`

## Sheet1-R41#1 / logistics
- 问题：25年 合肥发广州 17.5报价
- 业务反馈：问题1有回复，问题2无回复，检索不到最高和最低值
- 状态：OK；intent/query_key：aggregate/hist_route_pricing_analysis
- filters/slots：`{"years": [2025], "vehicle_type": "17.5", "view_mode": "avg_fee", "origin_place": "合肥", "city": "广州"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['avg_fee', 'row_count']；rows=1
- 摘要：2025年合肥发广州17.5车平均运费为52,400元。
- 前几行：`[{"avg_fee": 52400.0, "row_count": 1}]`

## Sheet1-R41#2 / logistics
- 问题：25年 合肥发广州 17.5报价，最高价和最低价是多少
- 业务反馈：问题1有回复，问题2无回复，检索不到最高和最低值
- 状态：OK；intent/query_key：aggregate/hist_route_pricing_analysis
- filters/slots：`{"years": [2025], "vehicle_type": "17.5", "view_mode": "fee_extremes", "origin_place": "合肥", "city": "广州"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['min_fee', 'max_fee', 'avg_fee', 'row_count']；rows=1
- 摘要：2025年合肥发广州17.5车最高价为52,400元，最低价为52,400元。
- 前几行：`[{"min_fee": 52400.0, "max_fee": 52400.0, "avg_fee": 52400.0, "row_count": 1}]`

## Sheet1-R42#1 / logistics
- 问题：帮我查下23年、24年和25年，合肥发广州17.5的分别运价
- 业务反馈：检索3年的同车型数据，需求是单价，后续是对比，不是总价
- 状态：OK；intent/query_key：compare/hist_route_pricing_analysis
- filters/slots：`{"years": [2023, 2024, 2025], "vehicle_type": "17.5", "view_mode": "year_compare", "origin_place": "合肥", "city": "广州"}`
- 展示：display_type=mixed；chart_type=bar；columns=['biz_year', 'avg_fee', 'row_count']；rows=2
- 摘要：2023年与2024年与2025年合肥发广州17.5车运价对比已按年份返回。
- 前几行：`[{"biz_year": 2024, "avg_fee": 11442.0, "row_count": 2}, {"biz_year": 2025, "avg_fee": 52400.0, "row_count": 1}]`

## Sheet1-R43#1 / logistics
- 问题：25年 合肥发广州 17.5报价，最高价和最低价是多少
- 业务反馈：上诉第40行问题，显示的均价不统一
- 状态：OK；intent/query_key：aggregate/hist_route_pricing_analysis
- filters/slots：`{"years": [2025], "vehicle_type": "17.5", "view_mode": "fee_extremes", "origin_place": "合肥", "city": "广州"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['min_fee', 'max_fee', 'avg_fee', 'row_count']；rows=1
- 摘要：2025年合肥发广州17.5车最高价为52,400元，最低价为52,400元。
- 前几行：`[{"min_fee": 52400.0, "max_fee": 52400.0, "avg_fee": 52400.0, "row_count": 1}]`

## Sheet1-R44#1 / logistics
- 问题：25年合肥发广东省，17.5车，每月平均运费是多少
- 业务反馈：查询的出发地：合肥，统计的结果是三个基地之和，且三个基地之和仅只有10月数据63是对的，其他都不对；正确存在合肥发出统计应该是173行数据，已将各月统计放在图片内
- 状态：OK；intent/query_key：aggregate/hist_avg_fee_by_month
- filters/slots：`{"year": 2025, "origin_place": "合肥", "province": "广东", "vehicle_type": "17.5"}`
- 展示：display_type=mixed；chart_type=bar；columns=['biz_month', 'avg_fee']；rows=11
- 摘要：2025年合肥基地发往广东的17.5车，整体样本平均运费约为13,089元，月均值再平均约为13,851元。
- 前几行：`[{"biz_month": "2025-01", "avg_fee": 19182.0}, {"biz_month": "2025-03", "avg_fee": 13597.0}]`

## Sheet1-R45#1 / logistics
- 问题：2026年1月份额外费用产生多少金额，分别是什么项目？什么原因产生的？
- 业务反馈：答非所问，正确答案：1月异常费用29610元
- 状态：OK；intent/query_key：aggregate/sys_extra_fee_summary
- filters/slots：`{"year": 2026, "months": [1], "detail_warning": "extra_fee_project_reason_unfixed"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['extra_fee_amount', 'task_count', 'detail_count']；rows=1
- 摘要：2026年1月额外费用总额为157,551.00元。
- 前几行：`[{"extra_fee_amount": 157551.0, "task_count": 368, "detail_count": 1015}]`
- warnings：['额外费用项目/原因明细口径尚未固化，本次先返回可审计的额外费用总额。']

## Sheet1-R46#1 / logistics
- 问题：2026年1月份总发运量是多少MW？
- 业务反馈：1月发运总量回答正确：466,571,820 瓦
1月发运车辆数回答错误1,690，报表为1027行，需要确认是否可以从系统直接读取数据
- 状态：OK；intent/query_key：aggregate/sys_mw_and_trip_count
- filters/slots：`{"year": 2026, "months": [1], "transport_mode": null, "base_code": null, "base_name": null, "monthly_breakdown": false}`
- 展示：display_type=summary_cards；chart_type=None；columns=['shipment_mw', 'power_missing_count', 'pickup_date_missing_count', 'strict_scope_task_count', 'pickup_date_available_count']；rows=1
- 摘要：2026年1月合计发运量为432.364MW。
- 前几行：`[{"shipment_mw": 432.364, "shipment_trip_count": 282, "power_missing_count": 49, "pickup_date_missing_count": 0, "strict_scope_task_count": 368, "year_task_count": 1233, "pickup_date_available_count": 1233, "region_coverage": {"direct_area_count": 368, "province_fallback_count": 0, "other_count": 0}, "year_region_coverage": {"direct_area_count": 1233, "province_fallback_count": 0, "other_count": 0}}]`
- warnings：['共有 49 条 product 记录 power 缺失，未纳入 MW 统计。', '区域口径优先使用 delivery_area；为空时用 delivery_province 映射七大区域，异常值归入“其他”。', '当前统计范围区域覆盖率：delivery_area 直接命中 1233 条，省份兜底 0 条，归入其他 0 条。']

## Sheet1-R46#2 / logistics
- 问题：总共发了多少车次？
- 业务反馈：1月发运总量回答正确：466,571,820 瓦
1月发运车辆数回答错误1,690，报表为1027行，需要确认是否可以从系统直接读取数据
- 状态：CLARIFICATION_REQUIRED；intent/query_key：clarification/None
- filters/slots：`{}`
- 展示：display_type=clarification；chart_type=None；columns=[]；rows=0
- 摘要：当前问题还不够明确，需先补充口径。
- warnings：['当前问题需要澄清后才能继续查询。']

## Sheet1-R47#1 / logistics
- 问题：25年全年17.5共发运多少车？
- 业务反馈：系统认为关键词是：共，没分清主体是17.5车，问题2就回答出来
- 状态：OK；intent/query_key：aggregate/hist_vehicle_type_trip_count
- filters/slots：`{"year": 2025, "vehicle_type": "17.5"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['shipment_trip_count']；rows=1
- 摘要：2025年17.5车合计发运13,861车次。
- 前几行：`[{"shipment_trip_count": 13861.0}]`

## Sheet1-R47#2 / logistics
- 问题：25年全年17.5车发运多少车
- 业务反馈：系统认为关键词是：共，没分清主体是17.5车，问题2就回答出来
- 状态：OK；intent/query_key：aggregate/hist_vehicle_type_trip_count
- filters/slots：`{"year": 2025, "vehicle_type": "17.5"}`
- 展示：display_type=summary_cards；chart_type=None；columns=['shipment_trip_count']；rows=1
- 摘要：2025年17.5车合计发运13,861车次。
- 前几行：`[{"shipment_trip_count": 13861.0}]`

## Sheet1-R48#1 / logistics
- 问题：华东区域2025年各省发运量分别是多少
- 业务反馈：华东区域各省发运量，仅提示江苏，其他各省无统计
- 状态：OK；intent/query_key：detail_list/hist_mw_by_region_province
- filters/slots：`{"year": 2025, "region_name": "华东", "provinces": []}`
- 展示：display_type=mixed；chart_type=bar；columns=['province', 'shipment_mw']；rows=7
- 摘要：2025年华东区域各省发运量已拆分返回。
- 前几行：`[{"province": "江苏", "shipment_mw": 1055.215}, {"province": "浙江", "shipment_mw": 727.412}]`

## Sheet1-R49#1 / logistics
- 问题：25年发往华东区域发运量是多少？
- 业务反馈：问题1和问题2 都是无回答，和第47行问题一致
- 状态：OK；intent/query_key：aggregate/hist_mw_summary
- filters/slots：`{"year": 2025, "months": [], "region_name": "华东", "origin_place": null}`
- 展示：display_type=summary_cards；chart_type=None；columns=['shipment_mw']；rows=1
- 摘要：2025年华东区域总发运量为3583.648MW。
- 前几行：`[{"shipment_mw": 3583.648}]`

## Sheet1-R49#2 / logistics
- 问题：25年 华东区域各省发运量是多少
- 业务反馈：问题1和问题2 都是无回答，和第47行问题一致
- 状态：OK；intent/query_key：detail_list/hist_mw_by_region_province
- filters/slots：`{"year": 2025, "region_name": "华东", "provinces": []}`
- 展示：display_type=mixed；chart_type=bar；columns=['province', 'shipment_mw']；rows=7
- 摘要：2025年华东区域各省发运量已拆分返回。
- 前几行：`[{"province": "江苏", "shipment_mw": 1055.215}, {"province": "浙江", "shipment_mw": 727.412}]`

## Sheet1-R50#1 / logistics
- 问题：25年物流公司发货量分别是多少？
- 业务反馈：问题1和问题2，涉及物流公司都没有结论
- 状态：OK；intent/query_key：ranking/hist_carrier_kpi_by_year
- filters/slots：`{"year": 2025, "region_name": null, "view_mode": "full_kpi"}`
- 展示：display_type=mixed；chart_type=bar；columns=['carrier_name', 'shipment_mw', 'shipment_share_pct', 'total_fee']；rows=20
- 摘要：2025年各物流承运商的发运量、占比和运费总额已汇总返回。
- 前几行：`[{"carrier_name": "苏州晶茂物流有限公司", "shipment_mw": 3730.136, "shipment_share_pct": 21.47, "total_fee": 58250425.0}, {"carrier_name": "浙江英赋嘉供应链科技股份有限公司", "shipment_mw": 3372.578, "shipment_share_pct": 19.41, "total_fee": 81156591.0}]`

## Sheet1-R50#2 / logistics
- 问题：2025年各物流承运商年度运输量各是多少
- 业务反馈：问题1和问题2，涉及物流公司都没有结论
- 状态：OK；intent/query_key：ranking/hist_carrier_kpi_by_year
- filters/slots：`{"year": 2025, "region_name": null, "view_mode": "full_kpi"}`
- 展示：display_type=mixed；chart_type=bar；columns=['carrier_name', 'shipment_mw', 'shipment_share_pct', 'total_fee']；rows=20
- 摘要：2025年各物流承运商的发运量、占比和运费总额已汇总返回。
- 前几行：`[{"carrier_name": "苏州晶茂物流有限公司", "shipment_mw": 3730.136, "shipment_share_pct": 21.47, "total_fee": 58250425.0}, {"carrier_name": "浙江英赋嘉供应链科技股份有限公司", "shipment_mw": 3372.578, "shipment_share_pct": 19.41, "total_fee": 81156591.0}]`

## Sheet1-R51#1 / logistics
- 问题：25年华东区域发货量排名前5的城市是哪些，发货量分别是多少
- 业务反馈：无城市发运量统计
- 状态：OK；intent/query_key：ranking/hist_city_mw_rank
- filters/slots：`{"year": 2025, "top_n": 5, "region_name": "华东"}`
- 展示：display_type=mixed；chart_type=bar；columns=['city', 'shipment_mw']；rows=5
- 摘要：2025年华东区域城市发运量前5名已按 MW 返回。
- 前几行：`[{"city": "金华", "shipment_mw": 344.284}, {"city": "响水", "shipment_mw": 333.225}]`

## Sheet1-R52#1 / logistics
- 问题：请列出2025年安徽各城市发运量TOP5及具体数值
- 业务反馈：无城市发运量统计
- 状态：OK；intent/query_key：ranking/hist_city_mw_rank
- filters/slots：`{"year": 2025, "top_n": 5, "province": "安徽"}`
- 展示：display_type=mixed；chart_type=bar；columns=['city', 'shipment_mw']；rows=5
- 摘要：2025年安徽省城市发运量前5名已按 MW 返回。
- 前几行：`[{"city": "亳州", "shipment_mw": 87.137}, {"city": "淮南市", "shipment_mw": 69.349}]`

## Sheet1-R53#1 / logistics
- 问题：2024年安徽省各城市发运量排名前五？
- 业务反馈：无城市发运量统计
- 状态：OK；intent/query_key：ranking/hist_city_mw_rank
- filters/slots：`{"year": 2024, "top_n": 5, "province": "安徽"}`
- 展示：display_type=mixed；chart_type=bar；columns=['city', 'shipment_mw']；rows=5
- 摘要：2024年安徽省城市发运量前5名已按 MW 返回。
- 前几行：`[{"city": "合肥", "shipment_mw": 126.099}, {"city": "亳州", "shipment_mw": 95.266}]`

## Sheet1-R54#1 / plan_bom
- 问题：NT12R/66GDF（深圳建融-2025-01073）0.24焊带+双镀玻璃+300/200线长，北德基准，615功率，芜湖供应需要从什么电池效率可以满足
- 业务反馈：无法检索
- 状态：OK；intent/query_key：plan_power_supplier_recommendation/None
- filters/slots：`{"order_tail_no": ["01073"], "compare_orders": ["01073"], "order_name_hint": "深圳建融-2025-01073", "material_category": ["glass", "interconnect_bar", "junction_box"], "non_core_material_category": ["cell"], "material_alias": ["玻璃", "焊带", "线长", "电池"], "bom_version": [], "model": "NT12R-66GDF", "year": 2025, "country": null, "target_power_ratio": {"615": 1.0}, "supplier_name": "芜湖", "benchmark": "新北德", "explicit_power_configuration": {"ribbon": "0.24", "glass": "双镀", "cable": "300/200线长", "benchmark": "新北德"}, "need_table": false, "need_excel": false, "output_format": "narrative"}`
- 展示：display_type=table；chart_type=None；columns=['供应商', '目标功率档', '目标比例', '预测比例', 'CTM 值', '中心功率', '建议效率段', '落档比例预估']；rows=1
- 摘要：已按订单 GCL-XXJC-JSPS-2025-01073 的 BOM 配置和目标功率比例完成供应商推荐，当前最高匹配供应商为 芜湖。
- 前几行：`[{"供应商": "芜湖", "目标功率档": "615W", "目标比例": 100.0, "预测比例": 3.4664, "CTM 值": "97.16%", "中心功率": 621.96, "建议效率段": "25.3%、25.4%", "落档比例预估": "25.3%→615W 39.63%、620W 59.66%\n25.4%→615W 13.80%、620W 81.63%"}]`

## Sheet1-R55#1 / plan_bom
- 问题：NT12R/66GDF（深圳建融-2025-01073）玻璃焊带线长汇流条是什么搭配并生成表格可导出版本
- 业务反馈：展示的不全，不能导出
- 状态：OK；intent/query_key：scope_material_list/None
- filters/slots：`{"order_tail_no": ["01073"], "compare_orders": ["01073"], "order_name_hint": "深圳建融-2025-01073", "material_category": ["glass", "interconnect_bar", "busbar", "junction_box"], "non_core_material_category": [], "material_alias": ["玻璃", "焊带", "汇流条", "线长"], "bom_version": [], "model": "NT12R-66GDF", "year": 2025, "country": null, "target_power_ratio": {}, "supplier_name": null, "benchmark": null, "explicit_power_configuration": {}, "need_table": true, "need_excel": true, "output_format": "excel"}`
- 展示：display_type=table；chart_type=None；columns=['material_category', 'material_name', 'description', 'standard_usage', 'unit']；rows=13
- 摘要：已按当前条件生成 13 条计划 BOM 材料清单。
- 前几行：`[{"order_no": "GCL-XXJC-JSPS-2025-01073", "order_name": "NT12R/66GDF（深圳建融-2025-01073）", "version_no": "B2", "material_category": "玻璃", "material_name": "光伏玻璃", "description": "光伏玻璃\\GCL\\2376*1128*2mm\\压花\\半钢化\\双镀膜\\-\\有价值", "sap_code": "1000496680", "standard_usage": "1000.000000", "unit": "片", "source_file": "NT12R66GDF(深圳建融钢边框-2025-01073)Billofmaterials-G.xls"}, {"order_no": "GCL-XXJC-JSPS-2025-01073", "order_name": "NT12R/66GDF（深圳建融-2025-01073）", "version_no": "B2", "material_category": "玻璃", "material_name": "光伏玻璃", "description": "光伏玻璃\\GCL\\2376*1128*2mm\\压花\\半钢化\\非镀膜\\GCL/XXJC/2-RD-5682无涂釉\\有价值", "sap_code": "1000496704", "standard_usage": "1000.000000", "unit": "片", "source_file": "NT12R66GDF(深圳建融钢边框-2025-01073)Billofmaterials-G.xls"}]`

## Sheet1-R56#1 / plan_bom
- 问题：NT12-66GDF，0.24+0.26焊带+超高透玻璃+6*0.35+4*0.35反光+400/-200mm（4mm²）+计量院基准，满足单一功率720，分别需要哪些供应商多少效率起投
- 业务反馈：没有BOM的情况下，根据材料搭配知道该版型满足需求功率，对应的电池效率档位。
- 状态：OK；intent/query_key：plan_power_supplier_recommendation/None
- filters/slots：`{"order_tail_no": [], "compare_orders": [], "order_name_hint": null, "material_category": ["glass", "interconnect_bar"], "non_core_material_category": [], "material_alias": ["玻璃", "焊带"], "bom_version": [], "model": "NT12-66GDF", "year": null, "country": null, "target_power_ratio": {"720": 1.0}, "supplier_name": null, "benchmark": "中国计量院", "explicit_power_configuration": {"ribbon": "0.24+0.26", "glass": "超高透", "busbar": "6*0.35+4*0.35反光", "cable": "+400/-200mm（4mm²）", "benchmark": "中国计量院"}, "need_table": false, "need_excel": false, "output_format": "narrative"}`
- 展示：display_type=table；chart_type=None；columns=['供应商', '目标功率档', '目标比例', '预测比例', 'CTM 值', '中心功率', '建议效率段', '落档比例预估']；rows=6
- 摘要：已按显式输入配置和目标功率比例完成供应商推荐，当前最高匹配供应商为 通威。
- 前几行：`[{"供应商": "通威", "目标功率档": "720W", "目标比例": 100.0, "预测比例": 70.1106, "CTM 值": "97.02%", "中心功率": 717.18, "建议效率段": "25.6%、25.7%", "落档比例预估": "25.6%→720W 61.21%、715W 37.61%\n25.7%→720W 80.89%、715W 11.45%"}, {"供应商": "爱旭", "目标功率档": "720W", "目标比例": 100.0, "预测比例": 68.4523, "CTM 值": "97.07%", "中心功率": 717.58, "建议效率段": "25.6%、25.7%", "落档比例预估": "25.6%→720W 68.22%、715W 29.94%\n25.7%→720W 80.96%、725W 11.19%"}]`

## Sheet1-R57#1 / logistics
- 问题：2025年各家物流承运商的承运量分别是多少？
- 业务反馈：问题1回答无问题，问题2涉及区域承运量不对
- 状态：OK；intent/query_key：ranking/hist_carrier_kpi_by_year
- filters/slots：`{"year": 2025, "region_name": null, "view_mode": "full_kpi"}`
- 展示：display_type=mixed；chart_type=bar；columns=['carrier_name', 'shipment_mw', 'shipment_share_pct', 'total_fee']；rows=20
- 摘要：2025年各物流承运商的发运量、占比和运费总额已汇总返回。
- 前几行：`[{"carrier_name": "苏州晶茂物流有限公司", "shipment_mw": 3730.136, "shipment_share_pct": 21.47, "total_fee": 58250425.0}, {"carrier_name": "浙江英赋嘉供应链科技股份有限公司", "shipment_mw": 3372.578, "shipment_share_pct": 19.41, "total_fee": 81156591.0}]`

## Sheet1-R57#2 / logistics
- 问题：2025年各家物流承运商在西北区域的承运量分别是多少
- 业务反馈：问题1回答无问题，问题2涉及区域承运量不对
- 状态：OK；intent/query_key：ranking/hist_carrier_kpi_by_year
- filters/slots：`{"year": 2025, "region_name": "西北", "view_mode": "full_kpi"}`
- 展示：display_type=mixed；chart_type=bar；columns=['carrier_name', 'shipment_mw', 'shipment_share_pct', 'total_fee']；rows=16
- 摘要：2025年西北区域各物流承运商的发运量、占比和运费总额已汇总返回。
- 前几行：`[{"carrier_name": "西安京东讯成物流有限公司", "shipment_mw": 1946.169, "shipment_share_pct": 35.85, "total_fee": 50332612.0}, {"carrier_name": "浙江英赋嘉供应链科技股份有限公司", "shipment_mw": 1692.536, "shipment_share_pct": 31.17, "total_fee": 43652449.0}]`

## Sheet1-R58#1 / logistics
- 问题：2025年苏州晶茂物流 在各区域的承运量分别是多少
- 业务反馈：有提示但无回答
- 状态：OK；intent/query_key：detail_list/hist_mw_by_all_regions
- filters/slots：`{"year": 2025, "carrier_name": "晶茂"}`
- 展示：display_type=mixed；chart_type=bar；columns=['region_name', 'shipment_mw']；rows=7
- 摘要：2025年晶茂各区域发运量汇总已按区域拆分返回。
- 前几行：`[{"region_name": "华东", "shipment_mw": 1326.274}, {"region_name": "西北", "shipment_mw": 909.25}]`

## Sheet1-R59#1 / logistics
- 问题：2025年苏州晶茂物流 在华东、华北、华南各区域的承运量分别是多少
- 业务反馈：有提示但无回答
- 状态：OK；intent/query_key：detail_list/hist_mw_by_all_regions
- filters/slots：`{"year": 2025, "carrier_name": "晶茂", "regions": ["华东", "华北", "华南"]}`
- 展示：display_type=mixed；chart_type=bar；columns=['region_name', 'shipment_mw']；rows=3
- 摘要：2025年晶茂华东、华北、华南发运量汇总已按区域拆分返回。
- 前几行：`[{"region_name": "华东", "shipment_mw": 1326.274}, {"region_name": "华北", "shipment_mw": 591.333}]`

## Sheet1-R60#1 / logistics
- 问题：2025年合肥至马鞍山17.5米车的平均运费（按提示2025年Q1合肥—马鞍山线路中，各承运商17.5米车的单票平均运费排名，也无回答）
- 业务反馈：有提示但无回答
- 状态：CLARIFICATION_REQUIRED；intent/query_key：clarification/None
- filters/slots：`{}`
- 展示：display_type=clarification；chart_type=None；columns=[]；rows=0
- 摘要：当前问题还不够明确，需先补充口径。
- warnings：['当前问题需要澄清后才能继续查询。']
