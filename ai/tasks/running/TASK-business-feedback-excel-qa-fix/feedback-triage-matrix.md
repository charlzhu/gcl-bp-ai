# 业务反馈逐条核对矩阵

说明：本矩阵基于 `经营计划智能体测试统计.xlsx` 与当前 `reproduction.json`，`状态=OK` 仅表示系统可回答，不代表业务正确。
- 状态统计：{'watch': 1, 'pass_current': 26, 'needs_data_check': 4, 'unsupported_safe': 3, 'fail': 19, 'partial_fail': 2, 'partial': 2, 'needs_business_decision': 2}

## Sheet1-R2 — watch / 口径确认
- 问题：合肥发江苏 17.5 车运费
- 业务反馈：不同时间和地点的车价
- 当前复现 Sheet1-R2#1: status=OK query_key=hist_route_pricing_analysis display=summary_cards chart=None rows=1 summary=2023-2025历史累计合肥发江苏17.5车平均运费为6,163元。
- 核对结论：当前默认 2023-2025 历史累计平均运费并给出 warning；反馈只说“不同时间和地点的车价”，当前答案结构可接受但仍需提示年份/起止地/均价口径。

## Sheet1-R3 — pass_current / 展示
- 问题：23年各区域发运量汇总，以表格形式体现
- 业务反馈：7个大区汇总未以表格形式呈现
- 当前复现 Sheet1-R3#1: status=OK query_key=hist_mw_by_all_regions display=table chart=None rows=7 summary=2023年各区域发运量汇总已按区域拆分返回。
- 核对结论：当前已返回 7 个大区 table，反馈问题已复现为已修复。

## Sheet1-R4 — pass_current / 数值
- 问题：23年合肥发往西北地区的总运量是多少
- 业务反馈：结果不对，正确值为2508.5155MW
- 当前复现 Sheet1-R4#1: status=OK query_key=hist_mw_summary display=summary_cards chart=None rows=1 summary=2023年西北区域合肥基地总发运量为2508.516MW。
- 核对结论：当前 2508.516MW，与反馈 2508.5155MW 四舍五入一致。

## Sheet1-R5 — pass_current / 展示/图表
- 问题：帮我做一个23年每个月的运费对比
- 业务反馈：未按月生成运费总量、折线或者柱状图
- 当前复现 Sheet1-R5#1: status=OK query_key=hist_monthly_total_fee_by_year display=mixed chart=bar rows=12 summary=2023年各月物流总费用已按 year-month 月份粒度返回。
- 核对结论：当前按 12 月返回 mixed+bar，总运费列存在。

## Sheet1-R6 — pass_current / 检索/展示
- 问题：帮我看下23年发往乌鲁木齐13m每车的运费均价是多少
- 业务反馈：未输出单车运价
- 当前复现 Sheet1-R6#1: status=OK query_key=hist_route_pricing_analysis display=summary_cards chart=None rows=1 summary=2023年乌鲁木齐13车平均运费为401,315元。
- 核对结论：当前返回 2023 乌鲁木齐 13 车 avg_fee 401315 元。

## Sheet1-R7 — pass_current / 检索
- 问题：2023年物流发运合计多少量？
- 业务反馈：问答角度不同，出来结果都一样
- 当前复现 Sheet1-R7#1: status=OK query_key=hist_mw_summary display=summary_cards chart=None rows=1 summary=2023年总发运量为8493.604MW。
- 核对结论：当前返回 2023 总发运量 8493.604MW，与承运商/客户问题不再相同。

## Sheet1-R8 — pass_current / 检索/分组
- 问题：2023年各物流承运商年度运输费用各是多少？
- 业务反馈：问答角度不同，出来结果都一样
- 当前复现 Sheet1-R8#1: status=OK query_key=hist_carrier_kpi_by_year display=mixed chart=bar rows=17 summary=2023年各物流承运商年度运输费用已汇总返回。
- 核对结论：当前返回承运商年度运输费用 17 行。

## Sheet1-R9 — pass_current / 检索
- 问题：2023年英赋嘉发运多少量？
- 业务反馈：问答角度不同，出来结果都一样
- 当前复现 Sheet1-R9#1: status=OK query_key=hist_mw_summary display=summary_cards chart=None rows=1 summary=2023年英赋嘉总发运量为1612.679MW。
- 核对结论：当前返回英赋嘉 1612.679MW，与总量不再相同。

## Sheet1-R10 — needs_data_check / 数值
- 问题：帮我查一下23年阜宁基地晶茂物流运输总运费多少钱?
- 业务反馈：统计的总计金额结果数据不对
- 当前复现 Sheet1-R10#1: status=OK query_key=hist_total_fee_by_origin_and_carrier display=summary_cards chart=None rows=1 summary=2023年阜宁基地、承运商晶茂的总运费为7,252,245元。
- 核对结论：当前返回 7,252,245 元；反馈只说不对未给正确值，需要用底表核对承运商/基地匹配口径。

## Sheet1-R11 — pass_current / NLU
- 问题：华润新能源（皮山）有限公司 项目 24年发运量是多少 无回答
- 业务反馈：在问题2中回复，就询问必须增加字段，客户和项目 分不清
- 当前复现 Sheet1-R11#1: status=OK query_key=hist_customer_mw display=summary_cards chart=None rows=1 summary=2024年华润新能源（皮山）有限公司总发运量为480.413MW。
- 当前复现 Sheet1-R11#2: status=OK query_key=hist_customer_mw display=summary_cards chart=None rows=1 summary=2024年华润新能源（皮山）有限公司总发运量为480.413MW。
- 核对结论：“项目/客户”两种问法当前均归到客户华润新能源（皮山）并返回 480.413MW。

## Sheet1-R12 — pass_current / 检索/分组
- 问题：26年招标和询比价，发运量分别是多少
- 业务反馈：26年在《采购类型》中增加采购和询比价 字段，可直接汇总相应字段的统计结果
- 当前复现 Sheet1-R12#1: status=OK query_key=sys_mw_by_procurement_type display=mixed chart=bar rows=3 summary=2026年招标、询比价等采购方式对应的发运量拆分已返回。
- 核对结论：当前按采购类型返回招标/询比价发运量。

## Sheet1-R13 — needs_data_check / 数值
- 问题：帮我统计一下24年合肥基地苏州晶茂物流全年发运量是多少？
- 业务反馈：问题汇总全年发运量合计数据不对
- 当前复现 Sheet1-R13#1: status=OK query_key=hist_mw_by_origin_and_carrier display=summary_cards chart=None rows=1 summary=2024年合肥基地、承运商晶茂的总发运量为1900.468MW。
- 核对结论：当前返回合肥+晶茂 1900.468MW；反馈未给正确值，需要底表核对。

## Sheet1-R14 — unsupported_safe / 能力边界/导出
- 问题：统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并分别列出询比价和招标的发运量
- 业务反馈：无法导出，检索不到地址
- 当前复现 Sheet1-R14#1: status=UNSUPPORTED_QUESTION query_key=None display=unsupported chart=None rows=0 summary=当前历史台账缺少稳定询比价/招标拆分字段，无法可靠回答高运费项目地的采购方式拆分。 可改问方向：可以先改问：24 年创维客户项目地运费超过 20 万的收货地址有哪些？；如需询比价/招标拆分，请先补齐并确认采购方式字段口径。
- 核对结论：当前安全拒绝高运费地址+采购方式拆分，因历史台账缺采购方式稳定字段；可作为后续能力，不应硬答。

## Sheet1-R15 — pass_current / NLU
- 问题：025年始发地合肥，车型 17.5 ，发出了多少车？
- 业务反馈：相关数据较少，请联系客服 朱长超
- 当前复现 Sheet1-R15#1: status=OK query_key=hist_vehicle_type_trip_count display=summary_cards chart=None rows=1 summary=2025年合肥基地17.5车合计发运9,816车次。
- 核对结论：“025年”当前解析为 2025，返回合肥17.5车 9816 车次。

## Sheet1-R16 — pass_current / 数值/时间
- 问题：2024年1月份发运总量是多少MW？
- 业务反馈：24年1月正确的发运总量为364.12MW，两次回答都错误9,164.757 MW、278.047 MW，且答案只显示了年份没有月份
- 当前复现 Sheet1-R16#1: status=OK query_key=hist_mw_summary display=summary_cards chart=None rows=1 summary=2024年1月总发运量为364.123MW。
- 核对结论：当前 2024年1月 364.123MW，与反馈 364.12MW 一致，摘要含月份。

## Sheet1-R17 — fail / NLU/时间过滤
- 问题：2024年1月份客户华阳的总发运量是多少MW？
- 业务反馈：结果比较接近，正确值为200.18712MW，答案只显示了年份没有月份
- 当前复现 Sheet1-R17#1: status=OK query_key=hist_customer_mw display=summary_cards chart=None rows=1 summary=2024年华阳的总发运量为0MW。
- 核对结论：客户槽抽成“华阳的”且 hist_customer_mw 未带 months，当前 0MW；应识别客户华阳并按 2024-01 返回约 200.18712MW。

## Sheet1-R18 — fail / 检索/口径
- 问题：26年经营计划用车运费是多少？
- 业务反馈：实际《经营计划》或（经营计划部》  统计结果应为13581元，回答的车次和当期总运费是不对的
- 当前复现 Sheet1-R18#1: status=OK query_key=sys_special_total_fee display=summary_cards chart=None rows=1 summary=2026年经营计划用车按锁定口径统计的总运费为134,378.00元。
- 当前复现 Sheet1-R18#2: status=OK query_key=sys_special_total_fee display=summary_cards chart=None rows=1 summary=2026年经营计划用车按锁定口径统计的总运费为134,378.00元。
- 核对结论：经营计划/经营计划部用车当前 special_scope=planning 返回 134,378 元；反馈期望约 13,581 元，疑似使用部门/发货类型/申请人字段口径过宽。

## Sheet1-R19 — partial_fail / 上下文/复合问句/计算
- 问题：2026年1月份总发运量是多少MW？
- 业务反馈：答非所问
- 当前复现 Sheet1-R19#1: status=OK query_key=sys_mw_and_trip_count display=summary_cards chart=None rows=1 summary=2026年1月合计发运量为432.364MW。
- 当前复现 Sheet1-R19#2: status=CLARIFICATION_REQUIRED query_key=None display=clarification chart=None rows=0 summary=当前问题还不够明确，需先补充口径。
- 核对结论：第一个子问返回 432.364MW，但反馈另处给 466.571820MW；第二个“总共发了多少车次”丢失上一子问 2026年1月上下文而澄清。

## Sheet1-R20 — needs_data_check / 数值
- 问题：统计一下阜宁基地2026年辅料送样总计运费是多少钱?
- 当前复现 Sheet1-R20#1: status=OK query_key=sys_total_fee_by_filters display=summary_cards chart=None rows=1 summary=2026年阜宁基地按当前系统口径统计的总运费为105,399.00元。
- 核对结论：阜宁基地2026辅料送样当前 105,399 元，Excel无备注正确值，需保留复现。

## Sheet1-R21 — fail / NLU/个人申请人过滤
- 问题：26年 经营计划 刘娟 用车总费用是多少
- 业务反馈：输出为  经营计划  用车总费用，后面个人申请费用无法单独调出 ，真实结果是：
1.使用部门：经营计划和计划  都纳入一起
2.增加个人的检索，费用为13621
- 当前复现 Sheet1-R21#1: status=OK query_key=sys_special_total_fee display=summary_cards chart=None rows=1 summary=2026年经营计划用车按锁定口径统计的总运费为134,378.00元。
- 核对结论：“刘娟”未抽取为申请人/联系人过滤，仍返回经营计划总额 134,378；反馈期望 13,621。

## Sheet1-R22 — fail / 计算/展示颗粒度
- 问题：24年 1-12月 每个月的江苏省的17.5均价是多少？
- 业务反馈：需要检索的是月度使用车型的总运量和总费用，相除得到单瓦价
- 当前复现 Sheet1-R22#1: status=OK query_key=hist_route_pricing_analysis display=mixed chart=bar rows=12 summary=2024年江苏17.5车每月平均运费已按月份返回。
- 当前复现 Sheet1-R22#2: status=OK query_key=hist_unit_fee_per_watt display=summary_cards chart=None rows=1 summary=2024年江苏单瓦运输成本为0.00563350元/瓦。
- 核对结论：“1-12月江苏单瓦价”当前返回全年汇总 summary_cards，业务要求按月总运量+总费用相除得到月度单瓦价；17.5均价问法也需避免误解释。

## Sheet1-R23 — unsupported_safe / 能力边界
- 问题：项目名称：国科新能源有限公司 已发出总运量是多少？江苏苏美达电力运营有限公司 项目 总发运量是多少
- 业务反馈：询问单个项目发运量，结果相同，错误了
- 当前复现 Sheet1-R23#1: status=UNSUPPORTED_QUESTION query_key=None display=unsupported chart=None rows=0 summary=当前项目名称尚未沉淀为稳定可复用统计维度，直接按项目名称汇总容易误导。 可改问方向：可以改问：某客户在某一年的总发运量是多少 MW？；如果必须按项目名称统计，请先确认项目名称归一规则和数据 owner 口径。
- 核对结论：项目名称维度尚未稳定，当前安全拒绝，不能用客户总量替代。

## Sheet1-R24 — partial / 计数口径
- 问题：帮我看一下26年2月客户：广东粤电阳西新能源有限公司总运费多少
- 业务反馈：实际发运10车，运费140600
- 当前复现 Sheet1-R24#1: status=OK query_key=sys_total_fee_by_filters display=summary_cards chart=None rows=1 summary=2026年2月客户广东粤电阳西新能源有限公司按当前系统口径统计的总运费为140,600.00元。
- 核对结论：总运费 140600 正确，但 task_count=4 与反馈发运10车不一致；若展示车次需明确分派/车辆/任务口径。

## Sheet1-R25 — pass_current / 基地过滤
- 问题：帮我看一下从合肥基地始发，26年1-2月客户：海南创维新能源投资有限公司 总运费多少
- 业务反馈：未能区分各基地数据
- 当前复现 Sheet1-R25#1: status=OK query_key=sys_total_fee_by_filters display=summary_cards chart=None rows=1 summary=2026年1月、2月合肥基地客户海南创维新能源投资有限公司按当前系统口径统计的总运费为38,294.00元。
- 核对结论：当前 filters 含 base_code=1 合肥基地，已区分基地。

## Sheet1-R26 — pass_current / 对比展示
- 问题：对比24年和25年合肥发广州 17.5运价？
- 业务反馈：问题2和3能回答，单项解决，但两个对比就不能呈现；问题1回答的是问题3的结果
- 当前复现 Sheet1-R26#1: status=OK query_key=hist_route_pricing_analysis display=mixed chart=bar rows=2 summary=2024年与2025年合肥发广州17.5车运价对比已按年份返回。
- 当前复现 Sheet1-R26#2: status=OK query_key=hist_route_pricing_analysis display=summary_cards chart=None rows=1 summary=2025年合肥发广州17.5车平均运费为52,400元。
- 当前复现 Sheet1-R26#3: status=OK query_key=hist_route_pricing_analysis display=summary_cards chart=None rows=1 summary=2024年合肥发广州17.5车平均运费为11,442元。
- 核对结论：当前 24/25 年合肥-广州17.5 运价对比返回 2 行。

## Sheet1-R27 — fail / 数值/价格解析
- 问题：帮我查一下2026年阜宁基地1月份晶茂物流总计运费是多少钱
- 业务反馈：实际费用为236985，统计数据有误
- 当前复现 Sheet1-R27#1: status=OK query_key=sys_total_fee_by_filters display=summary_cards chart=None rows=1 summary=2026年1月阜宁基地承运商晶茂物流按当前系统口径统计的总运费为234,202.00元。
- 核对结论：当前阜宁基地1月晶茂物流 234,202 元，反馈 236,985，差 2,783；需查缺失/解析价格或承运商匹配。

## Sheet1-R28 — fail / 计算/发货类型过滤/功率解析
- 问题：2月份单W运输成本是多少（（2月运费总价格+额外费用）/运输组件总W数）
- 业务反馈：未输出结果。正确值：“发货类型”只看正常发货，不看辅料送样，2月正常发货总运输价格+额外费用=1914325元，总运输W数（功率*分派数量）为129922225W，单W成本0.014元/W，若功率列有“720W”类的字样，不是纯数字，则取“W”前面的数字段720
- 当前复现 Sheet1-R28#1: status=OK query_key=sys_unit_fee_per_watt display=summary_cards chart=None rows=1 summary=2026年2月按（总运费+额外费用）/总发运瓦数口径统计的单瓦运输成本为0.014598元/瓦。
- 核对结论：当前 0.014598；反馈要求仅正常发货、总价+额外费=1,914,325、W=129,922,225、单W约0.014；当前未显式过滤正常发货且总价差 17,755。

## Sheet1-R29 — fail / 运输方式/功率计算
- 问题：2026年1月份总共发货多少MW？
- 业务反馈：不同的问题回答的结果却一样；1~2月铁路运输实际问题实际为23.78MW
- 当前复现 Sheet1-R29#1: status=OK query_key=sys_mw_and_trip_count display=summary_cards chart=None rows=1 summary=2026年1月合计发运量为432.364MW。
- 当前复现 Sheet1-R29#2: status=OK query_key=sys_mw_and_trip_count display=summary_cards chart=None rows=1 summary=2026年1月、2月铁路方式合计发运量为0MW。
- 核对结论：1-2月铁路当前 0MW 且 power_missing=4；反馈为 23.78MW，疑似运输方式或 product 功率/数量关联口径错误。

## Sheet1-R30 — pass_current / PlanBOM检索
- 问题：订单00104的的玻璃、间隙贴膜，焊带、汇流条、接线盒的规格描述？
- 业务反馈：未输出该订单BOM配置
- 当前复现 Sheet1-R30#1: status=OK query_key=None display=table chart=None rows=14 summary=已查询订单 NT12R/66GDF(法国-2026-00104)Bill of materials 的 14 条 BOM 材料规格。
- 核对结论：订单00104当前返回14条核心材料规格。

## Sheet1-R31 — needs_business_decision / PlanBOM消歧
- 问题：订单00067和订单00106玻璃、间隙贴膜，焊带、汇流条、接线盒的规格描述有什么不一样，并用表格统计出来
- 业务反馈：为了更准确查询，请补充产品型号或规格（如 GCL-M10/72H-555、550W）。
- 当前复现 Sheet1-R31#1: status=CLARIFICATION_REQUIRED query_key=None display=clarification chart=None rows=0 summary=当前问题缺少或存在歧义的槽位：order_identity。请补充订单、版本、材料或查询范围。
- 核对结论：00067/00106 都有多候选时当前澄清，反馈本身也是让补充型号；不应硬选。

## Sheet1-R32 — pass_current / PlanBOM检索
- 问题：哥伦比亚COEXITO -2026-00067，NT10/78GDF的线盒物料描述
- 业务反馈：正确答案：接线盒\GCL\GCL-N1xyz\GCL-02\+300/-200mm\1500V\25A\GCL4045\三分体含连接器线长\-\有价值
- 当前复现 Sheet1-R32#1: status=OK query_key=None display=table chart=None rows=1 summary=已查询订单 NT10/78GDF（哥伦比亚COEXITO -2026-00067） 的 1 条 BOM 材料规格。
- 核对结论：线盒描述与反馈正确答案一致。

## Sheet1-R33 — pass_current / PlanBOM检索
- 问题：NT12R/66GDF（法国Synapsun-2026-00114）订单的玻璃，焊带，汇流条，间隙贴膜线盒的规格
- 业务反馈：可以输出单
- 当前复现 Sheet1-R33#1: status=OK query_key=None display=table chart=None rows=10 summary=已查询订单 NT12R/66GDF（法国Synapsun-2026-00114） 的 10 条 BOM 材料规格。
- 核对结论：法国Synapsun-00114可输出单。

## Sheet1-R34 — fail / PlanBOM展示
- 问题：NT12R/66GDF（法国Synapsun-2026-00114）订单的玻璃，焊带，汇流条，间隙贴膜线盒的规格，并生成表格
- 业务反馈：输出的明细是对的，但是输出的数据较多，表格太大，展示不开
- 当前复现 Sheet1-R34#1: status=OK query_key=None display=table chart=None rows=10 summary=已查询订单 NT12R/66GDF（法国Synapsun-2026-00114） 的 10 条 BOM 材料规格。
- 核对结论：数据正确但表太宽；需面向业务隐藏来源/版本/SAP等低频字段或提供简洁视图。

## Sheet1-R35 — needs_business_decision / PlanBOM输入
- 问题：NT12R/66GDF（法国Synapsun-2026-00114）和NT12R/66GDF（法国Synapsun-2026-00114）订单的玻璃，焊带，汇流条，间隙贴膜线盒的规格对比
- 业务反馈：只能输出一个订单的配置，另一个清单的显示不出，无法做对比
- 当前复现 Sheet1-R35#1: status=CLARIFICATION_REQUIRED query_key=None display=clarification chart=None rows=0 summary=当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。
- 核对结论：同一个订单与自身对比当前澄清；业务反馈说只能输出一个订单但输入确实重复，需明确是否允许自对比。

## Sheet1-R36 — fail / PlanBOM展示
- 问题：NT12R/66GDF（法国Synapsun-2026-00114）和NT12R/66GDF(法国-2026-00104)Bill of materials订单的玻璃，焊带，汇流条，间隙贴膜线盒的规格对比
- 业务反馈：1、输出的结果是对的，像来源和版本和SAP号是不是都可以去掉，太多了。
2、玻璃有好几款，每个玻璃可不可以有分段落，现在是全部集中在一起，比较难找，不明显
- 当前复现 Sheet1-R36#1: status=OK query_key=None display=comparison_table chart=None rows=12 summary=已完成 BOM 差异对比，变化 8 条，仅左侧 0 条，仅右侧 4 条。
- 核对结论：结果正确但列太多，玻璃多款集中；需按材料类别/描述分组展示，默认隐藏 source/version/SAP。

## Sheet1-R37 — unsupported_safe / PlanBOM澄清
- 问题：针对现有的订单把玻璃，焊带，汇流条，间隙贴膜线盒的规格并用表格的形式呈现
- 业务反馈：没有用表格的形式展现
- 当前复现 Sheet1-R37#1: status=CLARIFICATION_REQUIRED query_key=None display=clarification chart=None rows=0 summary=当前问题缺少或存在歧义的槽位：order_id。请补充订单、版本、材料或查询范围。
- 核对结论：“现有订单”无订单标识，当前澄清合理。

## Sheet1-R38 — partial_fail / PlanBOM展示/导出
- 问题：NT12/66GDF（苏格兰-2026-00048），NT10/78GDF（泰州中来 -2026-00127）NT12R/66GDF（意大利-2026-00097），订单的玻璃，间隙贴膜，接线盒，汇流条，焊带规格 并用EXCEL表格形式展现出来
- 当前复现 Sheet1-R38#1: status=OK query_key=None display=table chart=None rows=35 summary=已按当前条件生成 35 条计划 BOM 材料清单。
- 核对结论：多订单Excel表可生成35行，但 source_file 乱码且列过宽；需简洁导出列。

## Sheet1-R39 — fail / PlanPower no-BOM
- 问题：创维210N—00106，0.24+0.26焊带+高透玻璃+间隙铝膜+300/200线长，计量院基准，单一需求720功率，各个供应商厂家从什么电池效率可以满足
- 业务反馈：这个是没有上传BOM，显示的也是无法检索
- 当前复现 Sheet1-R39#1: status=CLARIFICATION_REQUIRED query_key=None display=clarification chart=None rows=0 summary=当前订单条件命中 3 个 BOM 候选，请先确认订单或文件实例后再做功率预测。候选包括：1. NT10/78GDF(江苏汉腾-2026-00106)Bill of materials（GCL-XXJC-JSPS-2026-00106，版本 A0）；2. NT10/78GDF(石家庄科林-2026-00106)Bill of materials（GCL-XXJC-JSPS-2026-00106，版本 A0）；3. NT12/66GDF(创维-A2026-00106)Bill of materials（GCL-XXJC-JSPS(A)-2026-00106，版本 A0）。你输入的“创维210N”未匹配当前候选名称，请确认是否为同一订单/项目。
- 核对结论：显式材料配置足够但因订单尾号00106多候选先澄清；应在无明确BOM且显式配置完整时走无BOM功率推荐，不能被尾号阻断。

## Sheet1-R40 — pass_current / PlanPower检索
- 问题：NT12R/66GDF（深圳建融-2025-01073）0.24焊带+双镀玻璃+300/200线长，北德基准，615功率，各个供应商厂家从什么电池效率可以满足
- 业务反馈：无法检索
- 当前复现 Sheet1-R40#1: status=OK query_key=None display=table chart=None rows=6 summary=已按订单 GCL-XXJC-JSPS-2025-01073 的 BOM 配置和目标功率比例完成供应商推荐，当前最高匹配供应商为 中润。
- 核对结论：深圳建融01073 615功率供应商效率已返回。

## Sheet1-R41 — pass_current / 线路极值
- 问题：25年 合肥发广州 17.5报价
- 业务反馈：问题1有回复，问题2无回复，检索不到最高和最低值
- 当前复现 Sheet1-R41#1: status=OK query_key=hist_route_pricing_analysis display=summary_cards chart=None rows=1 summary=2025年合肥发广州17.5车平均运费为52,400元。
- 当前复现 Sheet1-R41#2: status=OK query_key=hist_route_pricing_analysis display=summary_cards chart=None rows=1 summary=2025年合肥发广州17.5车最高价为52,400元，最低价为52,400元。
- 核对结论：2025合肥-广州17.5最高/最低已返回。

## Sheet1-R42 — partial / 线路跨年展示
- 问题：帮我查下23年、24年和25年，合肥发广州17.5的分别运价
- 业务反馈：检索3年的同车型数据，需求是单价，后续是对比，不是总价
- 当前复现 Sheet1-R42#1: status=OK query_key=hist_route_pricing_analysis display=mixed chart=bar rows=2 summary=2023年与2024年与2025年合肥发广州17.5车运价对比已按年份返回。
- 核对结论：当前返回 2024/2025 两行，2023无数据未显式展示；需决定是否补“无数据”行。

## Sheet1-R43 — pass_current / 线路极值
- 问题：25年 合肥发广州 17.5报价，最高价和最低价是多少
- 业务反馈：上诉第40行问题，显示的均价不统一
- 当前复现 Sheet1-R43#1: status=OK query_key=hist_route_pricing_analysis display=summary_cards chart=None rows=1 summary=2025年合肥发广州17.5车最高价为52,400元，最低价为52,400元。
- 核对结论：最高/最低均价一致因仅1条样本，当前说明 row_count=1。

## Sheet1-R44 — needs_data_check / 基地/始发地过滤
- 问题：25年合肥发广东省，17.5车，每月平均运费是多少
- 业务反馈：查询的出发地：合肥，统计的结果是三个基地之和，且三个基地之和仅只有10月数据63是对的，其他都不对；正确存在合肥发出统计应该是173行数据，已将各月统计放在图片内
- 当前复现 Sheet1-R44#1: status=OK query_key=hist_avg_fee_by_month display=mixed chart=bar rows=11 summary=2025年合肥基地发往广东的17.5车，整体样本平均运费约为13,089元，月均值再平均约为13,851元。
- 核对结论：当前 filters 有 origin_place=合肥并返回11个月；反馈称应173行，需核对合肥基地/合肥始发地与月份均值分母。

## Sheet1-R45 — fail / 额外费用
- 问题：2026年1月份额外费用产生多少金额，分别是什么项目？什么原因产生的？
- 业务反馈：答非所问，正确答案：1月异常费用29610元
- 当前复现 Sheet1-R45#1: status=UNSUPPORTED_QUESTION query_key=None display=unsupported chart=None rows=0 summary=当前系统只固化了额外费用总额口径，尚未固化额外费用项目、原因和明细拆分口径。 可改问方向：可以改问：2026 年 1 月额外费用总额是多少？；如果需要项目/原因明细，请先由数据 owner 确认明细字段和归因口径。
- 核对结论：问项目/原因时当前整体 unsupported，但反馈至少要求1月异常费用29610；可先返回总额+提示明细口径未固化。

## Sheet1-R46 — fail / 系统发运量/车次口径
- 问题：2026年1月份总发运量是多少MW？
- 业务反馈：1月发运总量回答正确：466,571,820 瓦
1月发运车辆数回答错误1,690，报表为1027行，需要确认是否可以从系统直接读取数据
- 当前复现 Sheet1-R46#1: status=OK query_key=sys_mw_and_trip_count display=summary_cards chart=None rows=1 summary=2026年1月合计发运量为432.364MW。
- 当前复现 Sheet1-R46#2: status=CLARIFICATION_REQUIRED query_key=None display=clarification chart=None rows=0 summary=当前问题还不够明确，需先补充口径。
- 核对结论：反馈称1月MW正确值466.571820MW、车次应1027行；当前 432.364MW/282，疑似按产品明细/取货日期严格口径导致漏计。

## Sheet1-R47 — pass_current / 车型槽
- 问题：25年全年17.5共发运多少车？
- 业务反馈：系统认为关键词是：共，没分清主体是17.5车，问题2就回答出来
- 当前复现 Sheet1-R47#1: status=OK query_key=hist_vehicle_type_trip_count display=summary_cards chart=None rows=1 summary=2025年17.5车合计发运13,861车次。
- 当前复现 Sheet1-R47#2: status=OK query_key=hist_vehicle_type_trip_count display=summary_cards chart=None rows=1 summary=2025年17.5车合计发运13,861车次。
- 核对结论：两种17.5车问法当前均返回13861车次。

## Sheet1-R48 — pass_current / 区域省份分组
- 问题：华东区域2025年各省发运量分别是多少
- 业务反馈：华东区域各省发运量，仅提示江苏，其他各省无统计
- 当前复现 Sheet1-R48#1: status=OK query_key=hist_mw_by_region_province display=mixed chart=bar rows=7 summary=2025年华东区域各省发运量已拆分返回。
- 核对结论：华东区域各省返回7行。

## Sheet1-R49 — pass_current / 区域汇总/省份分组
- 问题：25年发往华东区域发运量是多少？
- 业务反馈：问题1和问题2 都是无回答，和第47行问题一致
- 当前复现 Sheet1-R49#1: status=OK query_key=hist_mw_summary display=summary_cards chart=None rows=1 summary=2025年华东区域总发运量为3583.648MW。
- 当前复现 Sheet1-R49#2: status=OK query_key=hist_mw_by_region_province display=mixed chart=bar rows=7 summary=2025年华东区域各省发运量已拆分返回。
- 核对结论：华东总量和各省分组均返回。

## Sheet1-R50 — fail / NLU承运商分组
- 问题：25年物流公司发货量分别是多少？
- 业务反馈：问题1和问题2，涉及物流公司都没有结论
- 当前复现 Sheet1-R50#1: status=OK query_key=hist_mw_summary display=summary_cards chart=None rows=1 summary=2025年总发运量为17374.913MW。
- 当前复现 Sheet1-R50#2: status=OK query_key=hist_carrier_kpi_by_year display=mixed chart=bar rows=20 summary=2025年各物流承运商的发运量、占比和运费总额已汇总返回。
- 核对结论：“25年物流公司发货量分别是多少”被路由为全年总量；应识别物流公司/分别为承运商分组。

## Sheet1-R51 — fail / 城市排名
- 问题：25年华东区域发货量排名前5的城市是哪些，发货量分别是多少
- 业务反馈：无城市发运量统计
- 当前复现 Sheet1-R51#1: status=OK query_key=hist_mw_summary display=summary_cards chart=None rows=1 summary=2025年华东区域总发运量为3583.648MW。
- 核对结论：华东区域城市Top5被路由为区域总量；缺历史城市发运量排名 query_key。

## Sheet1-R52 — fail / 城市排名/省份槽
- 问题：请列出2025年安徽各城市发运量TOP5及具体数值
- 业务反馈：无城市发运量统计
- 当前复现 Sheet1-R52#1: status=OK query_key=hist_mw_summary display=summary_cards chart=None rows=1 summary=2025年总发运量为17374.913MW。
- 核对结论：安徽各城市TOP5被路由为全年总量；缺省份城市排名。

## Sheet1-R53 — fail / 城市排名/省份槽
- 问题：2024年安徽省各城市发运量排名前五？
- 业务反馈：无城市发运量统计
- 当前复现 Sheet1-R53#1: status=OK query_key=hist_mw_summary display=summary_cards chart=None rows=1 summary=2024年总发运量为13457.796MW。
- 核对结论：安徽省各城市排名前五被路由为全年总量。

## Sheet1-R54 — pass_current / PlanPower供应商过滤
- 问题：NT12R/66GDF（深圳建融-2025-01073）0.24焊带+双镀玻璃+300/200线长，北德基准，615功率，芜湖供应需要从什么电池效率可以满足
- 业务反馈：无法检索
- 当前复现 Sheet1-R54#1: status=OK query_key=None display=table chart=None rows=1 summary=已按订单 GCL-XXJC-JSPS-2025-01073 的 BOM 配置和目标功率比例完成供应商推荐，当前最高匹配供应商为 芜湖。
- 核对结论：芜湖供应商效率推荐已返回1行。

## Sheet1-R55 — fail / PlanBOM展示/导出
- 问题：NT12R/66GDF（深圳建融-2025-01073）玻璃焊带线长汇流条是什么搭配并生成表格可导出版本
- 业务反馈：展示的不全，不能导出
- 当前复现 Sheet1-R55#1: status=OK query_key=None display=table chart=None rows=13 summary=已按当前条件生成 13 条计划 BOM 材料清单。
- 核对结论：当前 need_excel=true 但展示列仍过宽，需确认可导出URL/隐藏冗余列/材料完整性。

## Sheet1-R56 — pass_current / PlanPower no-BOM
- 问题：NT12-66GDF，0.24+0.26焊带+超高透玻璃+6*0.35+4*0.35反光+400/-200mm（4mm²）+计量院基准，满足单一功率720，分别需要哪些供应商多少效率起投
- 业务反馈：没有BOM的情况下，根据材料搭配知道该版型满足需求功率，对应的电池效率档位。
- 当前复现 Sheet1-R56#1: status=OK query_key=None display=table chart=None rows=6 summary=已按显式输入配置和目标功率比例完成供应商推荐，当前最高匹配供应商为 通威。
- 核对结论：无BOM显式配置720功率已返回供应商效率。

## Sheet1-R57 — fail / 承运商区域过滤
- 问题：2025年各家物流承运商的承运量分别是多少？
- 业务反馈：问题1回答无问题，问题2涉及区域承运量不对
- 当前复现 Sheet1-R57#1: status=OK query_key=hist_carrier_kpi_by_year display=mixed chart=bar rows=20 summary=2025年各物流承运商的发运量、占比和运费总额已汇总返回。
- 当前复现 Sheet1-R57#2: status=OK query_key=hist_carrier_kpi_by_year display=mixed chart=bar rows=20 summary=2025年各物流承运商的发运量、占比和运费总额已汇总返回。
- 核对结论：“各家物流承运商在西北区域”当前 filters 未带 region，结果与全局相同；应支持承运商×区域分组/过滤。

## Sheet1-R58 — pass_current / 承运商区域分布
- 问题：2025年苏州晶茂物流 在各区域的承运量分别是多少
- 业务反馈：有提示但无回答
- 当前复现 Sheet1-R58#1: status=OK query_key=hist_mw_by_all_regions display=mixed chart=bar rows=7 summary=2025年晶茂各区域发运量汇总已按区域拆分返回。
- 核对结论：晶茂各区域承运量已返回7行。

## Sheet1-R59 — pass_current / 承运商多区域过滤
- 问题：2025年苏州晶茂物流 在华东、华北、华南各区域的承运量分别是多少
- 业务反馈：有提示但无回答
- 当前复现 Sheet1-R59#1: status=OK query_key=hist_mw_by_all_regions display=mixed chart=bar rows=3 summary=2025年晶茂华东、华北、华南发运量汇总已按区域拆分返回。
- 核对结论：晶茂指定华东/华北/华南已返回3行。

## Sheet1-R60 — fail / 线路承运商排名/季度
- 问题：2025年合肥至马鞍山17.5米车的平均运费（按提示2025年Q1合肥—马鞍山线路中，各承运商17.5米车的单票平均运费排名，也无回答）
- 业务反馈：有提示但无回答
- 当前复现 Sheet1-R60#1: status=CLARIFICATION_REQUIRED query_key=None display=clarification chart=None rows=0 summary=当前问题还不够明确，需先补充口径。
- 核对结论：合肥至马鞍山17.5平均运费/Q1承运商排名仍澄清；需解析季度+线路+车型+承运商排名。
