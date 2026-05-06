# TRIAL_SAMPLE_QUESTION_LEDGER

- 正式样例题文件：`/Users/zhuchangchao/Downloads/物流和 bom样例题.docx`
- 文件类型：`.docx`
- 有效编号问题总数：1391
- 重点题数量：499
- 原题变体总数：1890

## 业务域分布
- plan_bom: 13
- logistics: 1374
- unknown: 4

## 题型分布
- bom_compare: 4
- bom_material_spec: 5
- bom_batch_table: 4
- aggregate: 314
- grouping: 102
- period_grouping: 279
- derived_metric: 433
- comparison: 56
- topn: 111
- matrix_or_wide_table: 39
- detail_list: 43
- unsupported_or_clarification: 1

## 前 80 条台账样例
| 题号 | 业务域 | 题型 | 重点 | 原始问题 | 变体数 |
| --- | --- | --- | --- | --- | --- |
| 1 | plan_bom | bom_compare | 是 | 订单A-00001和订单B-00002材料对比,有哪些材料不一致? | 2 |
| 2 | plan_bom | bom_material_spec | 是 | 订单00001的玻璃、间隙贴膜,焊带、汇流条、接线盒的规格描述? | 2 |
| 3 | plan_bom | bom_batch_table | 是 | 查找订单00001/00002/00003/00004/00005这几个订单的玻璃、间隙贴膜,焊带、汇流条、接线盒的规格描述并生成表格? | 2 |
| 4 | plan_bom | bom_material_spec | 是 | 订单00104的的玻璃、间隙贴膜,焊带、汇流条、接线盒的规格描述? | 2 |
| 5 | plan_bom | bom_compare | 是 | 订单00067和订单00106玻璃、间隙贴膜,焊带、汇流条、接线盒的规格描述有什么不一样,并用表格统计出来 | 2 |
| 6 | plan_bom | bom_material_spec | 是 | 哥伦比亚COEXITO -2026-00067,NT10/78GDF的线盒物料描述 | 2 |
| 7 | plan_bom | bom_material_spec | 是 | NT12R/66GDF(法国Synapsun-2026-00114)订单的玻璃,焊带,汇流条,间隙贴膜线盒的规格 | 2 |
| 8 | plan_bom | bom_batch_table | 是 | NT12R/66GDF(法国Synapsun-2026-00114)订单的玻璃,焊带,汇流条,间隙贴膜线盒的规格,并生成表格 | 2 |
| 9 | plan_bom | bom_compare | 是 | NT12R/66GDF(法国Synapsun-2026-00114)和NT12R/66GDF(法国Synapsun-2026-00114)订单的玻璃,焊带,汇流条,间隙贴膜线盒的规格对比 | 2 |
| 10 | plan_bom | bom_compare | 是 | NT12R/66GDF(法国Synapsun-2026-00114)和NT12R/66GDF(法国-2026-00104)Bill of materials订单的玻璃,焊带,汇流条,间隙贴膜线盒的规格对比 | 2 |
| 11 | plan_bom | bom_batch_table | 是 | 针对现有的订单把玻璃,焊带,汇流条,间隙贴膜线盒的规格并用表格的形式呈现 | 2 |
| 12 | plan_bom | bom_batch_table | 是 | NT12/66GDF(苏格兰-2026-00048),NT10/78GDF(泰州中来 -2026-00127)NT12R/66GDF(意大利-2026-00097),订单的玻璃,间隙贴膜,接线盒,汇流条,焊带规格 并用EXCEL表格形式展现出来 | 2 |
| 13 | logistics | aggregate | 否 | 华东区域在历史物流台账中的总发运件数是多少? | 1 |
| 14 | logistics | aggregate | 否 | 华中区域在历史物流台账中的总发运件数是多少? | 1 |
| 15 | logistics | aggregate | 否 | 华南区域在历史物流台账中的总发运件数是多少? | 1 |
| 16 | logistics | aggregate | 否 | 华北区域在历史物流台账中的总发运件数是多少? | 1 |
| 17 | logistics | aggregate | 否 | 西南区域在历史物流台账中的总发运件数是多少? | 1 |
| 18 | logistics | aggregate | 否 | 西北区域在历史物流台账中的总发运件数是多少? | 1 |
| 19 | logistics | aggregate | 否 | 东北区域在历史物流台账中的总发运件数是多少? | 1 |
| 20 | logistics | aggregate | 否 | 江苏省历史发运的总费用是多少? | 1 |
| 21 | logistics | aggregate | 否 | 安徽省历史发运的总费用是多少? | 1 |
| 22 | logistics | aggregate | 否 | 广东省历史发运的总费用是多少? | 1 |
| 23 | logistics | aggregate | 否 | 云南省历史发运的总费用是多少? | 1 |
| 24 | logistics | aggregate | 否 | 新疆省历史发运的总费用是多少? | 1 |
| 25 | logistics | aggregate | 否 | 河北省历史发运的总费用是多少? | 1 |
| 26 | logistics | aggregate | 否 | 浙江省历史发运的总费用是多少? | 1 |
| 27 | logistics | aggregate | 否 | 山东省历史发运的总费用是多少? | 1 |
| 28 | logistics | grouping | 否 | 按运输方式统计,公路对应的发运记录数是多少? | 1 |
| 29 | logistics | grouping | 否 | 按运输方式统计,铁路对应的发运记录数是多少? | 1 |
| 30 | logistics | grouping | 否 | 按运输方式统计,水路对应的发运记录数是多少? | 1 |
| 31 | logistics | grouping | 否 | 按运输方式统计,汽运对应的发运记录数是多少? | 1 |
| 32 | logistics | grouping | 否 | 按运输方式统计,铁运对应的发运记录数是多少? | 1 |
| 33 | logistics | aggregate | 否 | 规格为GCL-NT10/78GDF-640W的历史发运总瓦数是多少? | 1 |
| 34 | logistics | aggregate | 否 | 规格为GCL-NT10/72GDF-590W的历史发运总瓦数是多少? | 1 |
| 35 | logistics | aggregate | 否 | 规格为GCL-NT10/72GDF-585W的历史发运总瓦数是多少? | 1 |
| 36 | logistics | aggregate | 否 | 规格为GCL-NT12R/66GDF-620W的历史发运总瓦数是多少? | 1 |
| 37 | logistics | aggregate | 否 | 规格为GCL-NT12/66GDF-710W的历史发运总瓦数是多少? | 1 |
| 38 | logistics | period_grouping | 是 | 2024Q1的物流发运车次或车辆数是多少? | 2 |
| 39 | logistics | period_grouping | 是 | 2024Q2的物流发运车次或车辆数是多少? | 2 |
| 40 | logistics | period_grouping | 是 | 2025Q1的物流发运车次或车辆数是多少? | 2 |
| 41 | logistics | period_grouping | 是 | 2025Q3的物流发运车次或车辆数是多少? | 2 |
| 42 | logistics | period_grouping | 是 | 2025Q4的物流发运车次或车辆数是多少? | 2 |
| 43 | logistics | derived_metric | 否 | 华东区域各运输方式的平均元/瓦分别是多少,并按成本从低到高排序? | 1 |
| 44 | logistics | derived_metric | 否 | 西南区域各运输方式的平均元/瓦分别是多少,并按成本从低到高排序? | 1 |
| 45 | logistics | derived_metric | 否 | 西北区域各运输方式的平均元/瓦分别是多少,并按成本从低到高排序? | 1 |
| 46 | logistics | derived_metric | 否 | 华中区域各运输方式的平均元/瓦分别是多少,并按成本从低到高排序? | 1 |
| 47 | logistics | derived_metric | 否 | 华南区域各运输方式的平均元/瓦分别是多少,并按成本从低到高排序? | 1 |
| 48 | logistics | derived_metric | 否 | 华北区域各运输方式的平均元/瓦分别是多少,并按成本从低到高排序? | 1 |
| 49 | logistics | derived_metric | 否 | 2024-01从合肥始发的订单中,平均每车装载托数是多少? | 1 |
| 50 | logistics | derived_metric | 否 | 2024-06从阜宁始发的订单中,平均每车装载托数是多少? | 1 |
| 51 | logistics | derived_metric | 否 | 2025-03从合肥始发的订单中,平均每车装载托数是多少? | 1 |
| 52 | logistics | derived_metric | 否 | 2025-07从合肥始发的订单中,平均每车装载托数是多少? | 1 |
| 53 | logistics | derived_metric | 否 | 2025-10从阜宁始发的订单中,平均每车装载托数是多少? | 1 |
| 54 | logistics | comparison | 是 | 对比2023年华东区域计划发运件数与实际发运件数的偏差率。 | 2 |
| 55 | logistics | comparison | 是 | 对比2024年西北区域计划发运件数与实际发运件数的偏差率。 | 2 |
| 56 | logistics | comparison | 是 | 对比2025年西南区域计划发运件数与实际发运件数的偏差率。 | 2 |
| 57 | logistics | comparison | 是 | 对比2025年华南区域计划发运件数与实际发运件数的偏差率。 | 2 |
| 58 | logistics | comparison | 是 | 对比2024年华中区域计划发运件数与实际发运件数的偏差率。 | 2 |
| 59 | logistics | grouping | 否 | 江苏省发运记录中,按客户名称统计前5名客户的总费用和总瓦数。 | 1 |
| 60 | logistics | grouping | 否 | 云南省发运记录中,按客户名称统计前5名客户的总费用和总瓦数。 | 1 |
| 61 | logistics | grouping | 否 | 新疆省发运记录中,按客户名称统计前5名客户的总费用和总瓦数。 | 1 |
| 62 | logistics | grouping | 否 | 河北省发运记录中,按客户名称统计前5名客户的总费用和总瓦数。 | 1 |
| 63 | logistics | grouping | 否 | 浙江省发运记录中,按客户名称统计前5名客户的总费用和总瓦数。 | 1 |
| 64 | logistics | grouping | 否 | 山东省发运记录中,按客户名称统计前5名客户的总费用和总瓦数。 | 1 |
| 65 | logistics | grouping | 否 | 贵州省发运记录中,按客户名称统计前5名客户的总费用和总瓦数。 | 1 |
| 66 | logistics | grouping | 否 | 四川省发运记录中,按客户名称统计前5名客户的总费用和总瓦数。 | 1 |
| 67 | logistics | derived_metric | 否 | 苏州城市发运中,不同物流公司的平均单价/车是多少? | 1 |
| 68 | logistics | derived_metric | 否 | 合肥城市发运中,不同物流公司的平均单价/车是多少? | 1 |
| 69 | logistics | derived_metric | 否 | 徐州城市发运中,不同物流公司的平均单价/车是多少? | 1 |
| 70 | logistics | derived_metric | 否 | 昭通城市发运中,不同物流公司的平均单价/车是多少? | 1 |
| 71 | logistics | derived_metric | 否 | 湖州城市发运中,不同物流公司的平均单价/车是多少? | 1 |
| 72 | logistics | derived_metric | 否 | 2023年各区域发运达标率的均值与中位数分别是多少? | 1 |
| 73 | logistics | derived_metric | 否 | 2024年各区域发运达标率的均值与中位数分别是多少? | 1 |
| 74 | logistics | derived_metric | 否 | 2025年各区域发运达标率的均值与中位数分别是多少? | 1 |
| 75 | logistics | aggregate | 否 | 最近物流成本是不是变高了? | 1 |
| 76 | logistics | aggregate | 否 | 帮我看看华东发运有没有异常。 | 1 |
| 77 | logistics | topn | 是 | 当前在途风险最高的是哪几单? | 2 |
| 78 | plan_bom | bom_material_spec | 是 | 把最近几个特殊订单列出来。 | 2 |
| 79 | logistics | aggregate | 否 | 2024年华东区域通过公路发运的总件数是多少? | 1 |
| 80 | logistics | aggregate | 否 | 2025年西南区域通过铁路发运的总费用是多少? | 1 |

## 未识别业务域样例
- 92. 哪些记录出现“每车装在托数偏高但车辆数很少”的装载异常?
- 118. 分别是多少
- 751. 请按月份把2023年至2025年的平均元/瓦做成对比表，并标出每年最高和最低月份？
- 759. 请把2023年至2025年各月总费用同比变化额和变化率做成月份对比表？

## 说明
- 业务域分类只用于测试分批和验收分析，不替代前端真实自动识别。
- 变体用于真实网页输入回归，不作为标准答案来源。
