# PLAN_BOM_QUESTION_LEDGER

- 问题总数：`129`
- 正式问题文件：`BOM问题.xlsx`
- 问题文件类型：`xlsx`
- 读取 sheet：`全部问题汇总`
- A：`86`
- B：`40`
- C：`3`
- D：`0`

| 序号 | 状态 | intent | 问题 | 原因 |
| --- | --- | --- | --- | --- |
| ORG001 | B | cross_order_material_compare | 订单A-00001和订单B-00002材料对比，有哪些材料不一致？ | 当前问题缺少或存在歧义的槽位：material_category。请补充订单、版本、材料或查询范围。 |
| ORG002 | C | single_order_material_specs | 订单00001的玻璃、间隙贴膜，焊带、汇流条、接线盒的规格描述？ | 当前已导入 BOM 数据中没有找到可支撑该问题的结果。原因：未找到匹配的 BOM 订单。 |
| ORG003 | C | multi_order_material_table | 查找订单00001/00002/00003/00004/00005这几个订单的玻璃、间隙贴膜，焊带、汇流条、接线盒的规格描述并生成表格？ | 当前已导入 BOM 数据中没有找到可支撑该问题的结果。原因：未找到匹配订单范围。 |
| ORG004 | C | power_cell_requirement | 使用功率预测来问询BOM配置的情况下需要什么样的电池可以满足订单需求功率 | 当前结构化 BOM 只包含订单、版本、材料和规格等事实数据，缺少功率预测模型、电池片功率档位规则、组件版型约束和业务选型规则，不能据此倒推“需要什么样的电池”。 |
| ORG005 | A | single_order_material_specs | 订单00104的的玻璃、间隙贴膜，焊带、汇流条、接线盒的规格描述？ | 已查询订单 NT12R/66GDF(法国-2026-00104)Bill of materials 的 14 条 BOM 材料规格。 |
| ORG006 | B | cross_order_material_compare | 订单00067和订单00106玻璃、间隙贴膜，焊带、汇流条、接线盒的规格描述有什么不一样，并用表格统计出来 | 当前问题缺少或存在歧义的槽位：order_identity。请补充订单、版本、材料或查询范围。 |
| ORG007 | A | single_order_material_specs | 哥伦比亚COEXITO -2026-00067，NT10/78GDF的线盒物料描述 | 已查询订单 NT10/78GDF（哥伦比亚COEXITO -2026-00067） 的 1 条 BOM 材料规格。 |
| ORG008 | A | single_order_material_specs | NT12R/66GDF（法国Synapsun-2026-00114）订单的玻璃，焊带，汇流条，间隙贴膜线盒的规格 | 已查询订单 NT12R/66GDF（法国Synapsun-2026-00114） 的 10 条 BOM 材料规格。 |
| ORG009 | A | single_order_material_specs | NT12R/66GDF（法国Synapsun-2026-00114）订单的玻璃，焊带，汇流条，间隙贴膜线盒的规格，并生成表格 | 已查询订单 NT12R/66GDF（法国Synapsun-2026-00114） 的 10 条 BOM 材料规格。 |
| ORG010 | B | material_consistency_check | NT12R/66GDF（法国Synapsun-2026-00114）和NT12R/66GDF（法国Synapsun-2026-00114）订单的玻璃，焊带，汇流条，间隙贴膜线盒的规格对比 | 当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。 |
| ORG011 | A | cross_order_material_compare | NT12R/66GDF（法国Synapsun-2026-00114）和NT12R/66GDF(法国-2026-00104)Bill of materials订单的玻璃，焊带，汇流条，间隙贴膜线盒的规格对比 | 已完成 BOM 差异对比，变化 8 条，仅左侧 0 条，仅右侧 4 条。 |
| ORG012 | B | specific_material_query | 针对现有的订单把玻璃，焊带，汇流条，间隙贴膜线盒的规格并用表格的形式呈现 | 当前问题缺少或存在歧义的槽位：order_id。请补充订单、版本、材料或查询范围。 |
| ORG013 | A | multi_order_material_table | NT12/66GDF（苏格兰-2026-00048），NT10/78GDF（泰州中来 -2026-00127）NT12R/66GDF（意大利-2026-00097），订单的玻璃，间隙贴膜，接线盒，汇流条，焊带规格 并用EXCEL表格形式展现出来 | 已按当前条件生成 35 条计划 BOM 材料清单。 |
| EXT001 | A | single_order_material_specs | 帮我把NT10/78GDF(哥伦比亚COEXITO -2026-00067)这单的玻璃、间隙贴膜、焊带、汇流条、接线盒规格整理出来。 | 已查询订单 NT10/78GDF（哥伦比亚COEXITO -2026-00067） 的 14 条 BOM 材料规格。 |
| EXT002 | B | single_order_material_specs | NT10/78GDF(江苏汉腾-2026-00106)这个订单的核心辅材规格给我拉一下，我要跟客户确认。 | 当前问题缺少或存在歧义的槽位：order_identity。请补充订单、版本、材料或查询范围。 |
| EXT003 | A | single_order_material_specs | 请查一下NT10/78GDF(泰州中来 -2026-00127)这份BOM里玻璃、间隙贴膜、焊带、汇流条、接线盒分别用的什么规格。 | 已查询订单 NT10/78GDF（泰州中来 -2026-00127） 的 11 条 BOM 材料规格。 |
| EXT004 | B | single_order_material_specs | NT10/78GDF(石家庄科林-2026-00106)这单我准备下发采购，先把五类关键材料规格发我。 | 当前问题缺少或存在歧义的槽位：order_identity。请补充订单、版本、材料或查询范围。 |
| EXT005 | A | single_order_material_specs | 把NT12/66GDF(国科华鑫仙居-2025-01063)对应BOM里的玻璃、间隙贴膜、焊带、汇流条、接线盒做成一行给我看。 | 已查询订单 NT12/66GDF（国科华鑫仙居--2025-01063） 的 14 条 BOM 材料规格。 |
| EXT006 | A | single_order_material_specs | NT12/66GDF(多米尼加Sistemi-2026-00099)这单客户催得急，麻烦直接告诉我五类关键材料的规格描述。 | 已查询订单 NT12/66GDF（多米尼加Sistemi-2026-00099） 的 14 条 BOM 材料规格。 |
| EXT007 | A | single_order_material_specs | 帮我把NT12/66GDF(天合富家新-2025-00844)这单的玻璃、间隙贴膜、焊带、汇流条、接线盒规格整理出来。 | 已查询订单 NT12/66GDF（天合富家新-2025-00844） 的 19 条 BOM 材料规格。 |
| EXT008 | A | single_order_material_specs | NT12/66GDF(柬埔寨太阳花-2026-00082)这个订单的核心辅材规格给我拉一下，我要跟客户确认。 | 已查询订单 NT12/66GDF（柬埔寨太阳花-2026-00082） 的 20 条 BOM 材料规格。 |
| EXT009 | A | single_order_material_specs | 请查一下NT12/66GDF(苏州康达尔-2026-00087)这份BOM里玻璃、间隙贴膜、焊带、汇流条、接线盒分别用的什么规格。 | 已查询订单 NT12/66GDF（苏州康达尔-2026-00087） 的 35 条 BOM 材料规格。 |
| EXT010 | A | single_order_material_specs | NT12/66GDF(苏格兰-2026-00048)这单我准备下发采购，先把五类关键材料规格发我。 | 已查询订单 NT12/66GDF（苏格兰-2026-00048） 的 11 条 BOM 材料规格。 |
| EXT011 | A | single_order_material_specs | 把NT12/66GDF(萨尔瓦多Compania-2026-00103)对应BOM里的玻璃、间隙贴膜、焊带、汇流条、接线盒做成一行给我看。 | 已查询订单 NT12/66GDF（萨尔瓦多Compania-2026-00103） 的 29 条 BOM 材料规格。 |
| EXT012 | A | single_order_material_specs | NT12R/66GDF(印尼Hijau-2026-00117)这单客户催得急，麻烦直接告诉我五类关键材料的规格描述。 | 已查询订单 NT12R/66GDF（印尼Hijau-2026-00117） 的 9 条 BOM 材料规格。 |
| EXT013 | A | single_order_material_specs | 帮我把NT12R/66GDF(印尼宾坦岛-2026-00096)这单的玻璃、间隙贴膜、焊带、汇流条、接线盒规格整理出来。 | 已查询订单 NT12R/66GDF(印尼宾坦岛-2026-00096)Bill of materials 的 11 条 BOM 材料规格。 |
| EXT014 | A | single_order_material_specs | NT12R/66GDF(危地马拉ECOLUMEN-2026-00121)这个订单的核心辅材规格给我拉一下，我要跟客户确认。 | 已查询订单 NT12R/66GDF（危地马拉ECOLUMEN-2026-00121） 的 11 条 BOM 材料规格。 |
| EXT015 | A | single_order_material_specs | 请查一下NT12R/66GDF(哥伦比亚Amara-2026-00115)这份BOM里玻璃、间隙贴膜、焊带、汇流条、接线盒分别用的什么规格。 | 已查询订单 NT12R/66GDF(哥伦比亚Amara-2026-00115)Bill of materials 的 11 条 BOM 材料规格。 |
| EXT016 | A | single_order_material_specs | NT12R/66GDF(多米尼加Escala-2026-00107)这单我准备下发采购，先把五类关键材料规格发我。 | 已查询订单 NT12R/66GDF（多米尼加Escala-2026-00107） 的 12 条 BOM 材料规格。 |
| EXT017 | A | single_order_material_specs | 把NT12R/66GDF(德国Anumar-2026-00077)对应BOM里的玻璃、间隙贴膜、焊带、汇流条、接线盒做成一行给我看。 | 已查询订单 NT12R/66GDF(德国Anumar-2026-00077)Bill of materials 的 14 条 BOM 材料规格。 |
| EXT018 | A | single_order_material_specs | NT12R/66GDF(德国Kumandra芜湖电池-2026-00113)这单客户催得急，麻烦直接告诉我五类关键材料的规格描述。 | 已查询订单 NT12R/66GDF（德国Kumandra-2026-00113） 的 10 条 BOM 材料规格。 |
| EXT019 | A | single_order_material_specs | 帮我把NT12R/66GDF(意大利-2026-00097)这单的玻璃、间隙贴膜、焊带、汇流条、接线盒规格整理出来。 | 已查询订单 NT12R/66GDF（意大利-2026-00097） 的 13 条 BOM 材料规格。 |
| EXT020 | A | single_order_material_specs | NT12R/66GDF(日本Krannich-2026-00109)这个订单的核心辅材规格给我拉一下，我要跟客户确认。 | 已查询订单 NT12R/66GDF（日本Krannich-2026-00109） 的 11 条 BOM 材料规格。 |
| EXT021 | A | single_order_material_specs | 请查一下NT12R/66GDF(法国-2026-00104)这份BOM里玻璃、间隙贴膜、焊带、汇流条、接线盒分别用的什么规格。 | 已查询订单 NT12R/66GDF(法国-2026-00104)Bill of materials 的 14 条 BOM 材料规格。 |
| EXT022 | A | single_order_material_specs | NT12R/66GDF(法国Synapsun-2026-00114)这单我准备下发采购，先把五类关键材料规格发我。 | 已查询订单 NT12R/66GDF（法国Synapsun-2026-00114） 的 10 条 BOM 材料规格。 |
| EXT023 | A | single_order_material_specs | 把NT12R/66GDF(深圳建融钢边框-2025-01073)对应BOM里的玻璃、间隙贴膜、焊带、汇流条、接线盒做成一行给我看。 | 已查询订单 NT12R/66GDF（深圳建融-2025-01073） 的 15 条 BOM 材料规格。 |
| EXT024 | A | single_order_material_specs | NT12R/66GDF(突尼斯MIM2A-2026-00061)这单客户催得急，麻烦直接告诉我五类关键材料的规格描述。 | 已查询订单 NT12R/66GDF(突尼斯MIM2A-2026-00061)Bill of materials 的 9 条 BOM 材料规格。 |
| EXT025 | B | single_order_material_specs | 帮我把NT12R/66GDF(肯尼亚Nationwide-2026-00120)这单的玻璃、间隙贴膜、焊带、汇流条、接线盒规格整理出来。 | 当前问题缺少或存在歧义的槽位：file_instance。请补充订单、版本、材料或查询范围。 |
| EXT026 | A | single_order_material_specs | NT12R/66GDF(菲律宾LUCA-2026-00102)这个订单的核心辅材规格给我拉一下，我要跟客户确认。 | 已查询订单 NT12R/66GDF（菲律宾LUCA-2026-00102） 的 13 条 BOM 材料规格。 |
| EXT027 | A | single_order_material_specs | 请查一下NT12R/66GDF(西班牙SII-2026-00111)这份BOM里玻璃、间隙贴膜、焊带、汇流条、接线盒分别用的什么规格。 | 已查询订单 NT12R/66GDF(西班牙SII-2026-00111)Bill of materials 的 11 条 BOM 材料规格。 |
| EXT028 | A | single_order_material_specs | NT12R/78GDF(华电南通-2025-01220)这单我准备下发采购，先把五类关键材料规格发我。 | 已查询订单 NT12R/78GDF(华电南通-2025-01220)Bill of materials 的 14 条 BOM 材料规格。 |
| EXT029 | B | material_consistency_check | 帮我对比一下NT10/78GDF(哥伦比亚COEXITO -2026-00067)的A0版和A1版，玻璃、间隙贴膜、焊带、汇流条、接线盒哪些地方变了？ | 当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。 |
| EXT030 | A | material_presence_check | NT10/78GDF(哥伦比亚COEXITO -2026-00067)从A0到A1版本，五类关键材料有没有换料？帮我列出来。 | 已完成 28 个当前 BOM 版本的物料存在性检查，返回 0 条匹配记录。 |
| EXT031 | B | material_consistency_check | 请把NT10/78GDF(哥伦比亚COEXITO -2026-00067) A0/A1两个版本的核心材料差异做成对比表。 | 当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。 |
| EXT032 | A | material_presence_check | NT10/78GDF(哥伦比亚COEXITO -2026-00067)这个订单版本升级后，先帮我看玻璃、焊带、汇流条、接线盒有没有调整。 | 已完成 28 个当前 BOM 版本的物料存在性检查，返回 0 条匹配记录。 |
| EXT033 | B | material_consistency_check | 帮我对比一下NT12/66GDF(苏格兰-2026-00048)的A0版和A1版，玻璃、间隙贴膜、焊带、汇流条、接线盒哪些地方变了？ | 当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。 |
| EXT034 | A | material_presence_check | NT12/66GDF(苏格兰-2026-00048)从A0到A1版本，五类关键材料有没有换料？帮我列出来。 | 已完成 28 个当前 BOM 版本的物料存在性检查，返回 0 条匹配记录。 |
| EXT035 | B | material_consistency_check | 请把NT12/66GDF(苏格兰-2026-00048) A0/A1两个版本的核心材料差异做成对比表。 | 当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。 |
| EXT036 | A | material_presence_check | NT12/66GDF(苏格兰-2026-00048)这个订单版本升级后，先帮我看玻璃、焊带、汇流条、接线盒有没有调整。 | 已完成 28 个当前 BOM 版本的物料存在性检查，返回 0 条匹配记录。 |
| EXT037 | B | material_consistency_check | 帮我对比一下NT12R/66GDF(德国Anumar-2026-00077)的A1版和A2版，玻璃、间隙贴膜、焊带、汇流条、接线盒哪些地方变了？ | 当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。 |
| EXT038 | A | material_presence_check | NT12R/66GDF(德国Anumar-2026-00077)从A1到A2版本，五类关键材料有没有换料？帮我列出来。 | 已完成 28 个当前 BOM 版本的物料存在性检查，返回 0 条匹配记录。 |
| EXT039 | B | material_consistency_check | 请把NT12R/66GDF(德国Anumar-2026-00077) A1/A2两个版本的核心材料差异做成对比表。 | 当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。 |
| EXT040 | A | material_presence_check | NT12R/66GDF(德国Anumar-2026-00077)这个订单版本升级后，先帮我看玻璃、焊带、汇流条、接线盒有没有调整。 | 已完成 28 个当前 BOM 版本的物料存在性检查，返回 0 条匹配记录。 |
| EXT041 | B | material_consistency_check | 帮我对比一下NT12R/66GDF(意大利-2026-00097)的A1版和A2版，玻璃、间隙贴膜、焊带、汇流条、接线盒哪些地方变了？ | 当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。 |
| EXT042 | A | material_presence_check | NT12R/66GDF(意大利-2026-00097)从A1到A2版本，五类关键材料有没有换料？帮我列出来。 | 已完成 28 个当前 BOM 版本的物料存在性检查，返回 0 条匹配记录。 |
| EXT043 | B | material_consistency_check | 请把NT12R/66GDF(意大利-2026-00097) A1/A2两个版本的核心材料差异做成对比表。 | 当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。 |
| EXT044 | A | material_presence_check | NT12R/66GDF(意大利-2026-00097)这个订单版本升级后，先帮我看玻璃、焊带、汇流条、接线盒有没有调整。 | 已完成 28 个当前 BOM 版本的物料存在性检查，返回 0 条匹配记录。 |
| EXT045 | B | material_consistency_check | 帮我对比一下NT12R/66GDF(日本Krannich-2026-00109)的A0版和A1版，玻璃、间隙贴膜、焊带、汇流条、接线盒哪些地方变了？ | 当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。 |
| EXT046 | A | material_presence_check | NT12R/66GDF(日本Krannich-2026-00109)从A0到A1版本，五类关键材料有没有换料？帮我列出来。 | 已完成 28 个当前 BOM 版本的物料存在性检查，返回 0 条匹配记录。 |
| EXT047 | B | material_consistency_check | 请把NT12R/66GDF(日本Krannich-2026-00109) A0/A1两个版本的核心材料差异做成对比表。 | 当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。 |
| EXT048 | A | material_presence_check | NT12R/66GDF(日本Krannich-2026-00109)这个订单版本升级后，先帮我看玻璃、焊带、汇流条、接线盒有没有调整。 | 已完成 28 个当前 BOM 版本的物料存在性检查，返回 0 条匹配记录。 |
| EXT049 | B | cross_order_material_compare | 把NT10/78GDF(哥伦比亚COEXITO -2026-00067)和NT10/78GDF(江苏汉腾-2026-00106)这两单的玻璃、间隙贴膜、焊带、汇流条、接线盒做个差异对比。 | 当前问题缺少或存在歧义的槽位：order_identity。请补充订单、版本、材料或查询范围。 |
| EXT050 | B | cross_order_material_compare | NT10/78GDF(哥伦比亚COEXITO -2026-00067)和NT10/78GDF(江苏汉腾-2026-00106)同型号但客户不一样，核心材料规格有没有差别？ | 当前问题缺少或存在歧义的槽位：order_identity。请补充订单、版本、材料或查询范围。 |
| EXT051 | B | cross_order_material_compare | 请帮我把NT10/78GDF(哥伦比亚COEXITO -2026-00067)、NT10/78GDF(江苏汉腾-2026-00106)两份BOM的五类关键材料拉成对比表。 | 当前问题缺少或存在歧义的槽位：order_identity。请补充订单、版本、材料或查询范围。 |
| EXT052 | B | cross_order_material_compare | 把NT10/78GDF(哥伦比亚COEXITO -2026-00067)和NT10/78GDF(石家庄科林-2026-00106)这两单的玻璃、间隙贴膜、焊带、汇流条、接线盒做个差异对比。 | 当前问题缺少或存在歧义的槽位：order_identity。请补充订单、版本、材料或查询范围。 |
| EXT053 | B | cross_order_material_compare | NT10/78GDF(哥伦比亚COEXITO -2026-00067)和NT10/78GDF(石家庄科林-2026-00106)同型号但客户不一样，核心材料规格有没有差别？ | 当前问题缺少或存在歧义的槽位：order_identity。请补充订单、版本、材料或查询范围。 |
| EXT054 | B | cross_order_material_compare | 请帮我把NT10/78GDF(哥伦比亚COEXITO -2026-00067)、NT10/78GDF(石家庄科林-2026-00106)两份BOM的五类关键材料拉成对比表。 | 当前问题缺少或存在歧义的槽位：order_identity。请补充订单、版本、材料或查询范围。 |
| EXT055 | B | cross_order_material_compare | 把NT10/78GDF(江苏汉腾-2026-00106)和NT10/78GDF(泰州中来 -2026-00127)这两单的玻璃、间隙贴膜、焊带、汇流条、接线盒做个差异对比。 | 当前问题缺少或存在歧义的槽位：order_identity。请补充订单、版本、材料或查询范围。 |
| EXT056 | B | cross_order_material_compare | NT10/78GDF(江苏汉腾-2026-00106)和NT10/78GDF(泰州中来 -2026-00127)同型号但客户不一样，核心材料规格有没有差别？ | 当前问题缺少或存在歧义的槽位：order_identity。请补充订单、版本、材料或查询范围。 |
| EXT057 | B | cross_order_material_compare | 请帮我把NT10/78GDF(江苏汉腾-2026-00106)、NT10/78GDF(泰州中来 -2026-00127)两份BOM的五类关键材料拉成对比表。 | 当前问题缺少或存在歧义的槽位：order_identity。请补充订单、版本、材料或查询范围。 |
| EXT058 | A | cross_order_material_compare | 把NT12/66GDF(苏格兰-2026-00048)和NT12/66GDF(柬埔寨太阳花-2026-00082)这两单的玻璃、间隙贴膜、焊带、汇流条、接线盒做个差异对比。 | 已完成 BOM 差异对比，变化 3 条，仅左侧 7 条，仅右侧 16 条。 |
| EXT059 | A | cross_order_material_compare | NT12/66GDF(苏格兰-2026-00048)和NT12/66GDF(柬埔寨太阳花-2026-00082)同型号但客户不一样，核心材料规格有没有差别？ | 已完成 BOM 差异对比，变化 3 条，仅左侧 7 条，仅右侧 16 条。 |
| EXT060 | A | cross_order_material_compare | 请帮我把NT12/66GDF(苏格兰-2026-00048)、NT12/66GDF(柬埔寨太阳花-2026-00082)两份BOM的五类关键材料拉成对比表。 | 已完成 BOM 差异对比，变化 3 条，仅左侧 7 条，仅右侧 16 条。 |
| EXT061 | A | cross_order_material_compare | 把NT12/66GDF(苏州康达尔-2026-00087)和NT12/66GDF(多米尼加Sistemi-2026-00099)这两单的玻璃、间隙贴膜、焊带、汇流条、接线盒做个差异对比。 | 已完成 BOM 差异对比，变化 3 条，仅左侧 31 条，仅右侧 10 条。 |
| EXT062 | A | cross_order_material_compare | NT12/66GDF(苏州康达尔-2026-00087)和NT12/66GDF(多米尼加Sistemi-2026-00099)同型号但客户不一样，核心材料规格有没有差别？ | 已完成 BOM 差异对比，变化 3 条，仅左侧 31 条，仅右侧 10 条。 |
| EXT063 | A | cross_order_material_compare | 请帮我把NT12/66GDF(苏州康达尔-2026-00087)、NT12/66GDF(多米尼加Sistemi-2026-00099)两份BOM的五类关键材料拉成对比表。 | 已完成 BOM 差异对比，变化 3 条，仅左侧 31 条，仅右侧 10 条。 |
| EXT064 | A | cross_order_material_compare | 把NT12/66GDF(国科华鑫仙居-2025-01063)和NT12/66GDF(萨尔瓦多Compania-2026-00103)这两单的玻璃、间隙贴膜、焊带、汇流条、接线盒做个差异对比。 | 已完成 BOM 差异对比，变化 1 条，仅左侧 7 条，仅右侧 22 条。 |
| EXT065 | A | cross_order_material_compare | NT12/66GDF(国科华鑫仙居-2025-01063)和NT12/66GDF(萨尔瓦多Compania-2026-00103)同型号但客户不一样，核心材料规格有没有差别？ | 已完成 BOM 差异对比，变化 1 条，仅左侧 7 条，仅右侧 22 条。 |
| EXT066 | A | cross_order_material_compare | 请帮我把NT12/66GDF(国科华鑫仙居-2025-01063)、NT12/66GDF(萨尔瓦多Compania-2026-00103)两份BOM的五类关键材料拉成对比表。 | 已完成 BOM 差异对比，变化 1 条，仅左侧 7 条，仅右侧 22 条。 |
| EXT067 | A | cross_order_material_compare | 把NT12R/66GDF(法国-2026-00104)和NT12R/66GDF(法国Synapsun-2026-00114)这两单的玻璃、间隙贴膜、焊带、汇流条、接线盒做个差异对比。 | 已完成 BOM 差异对比，变化 8 条，仅左侧 4 条，仅右侧 0 条。 |
| EXT068 | A | cross_order_material_compare | NT12R/66GDF(法国-2026-00104)和NT12R/66GDF(法国Synapsun-2026-00114)同型号但客户不一样，核心材料规格有没有差别？ | 已完成 BOM 差异对比，变化 8 条，仅左侧 4 条，仅右侧 0 条。 |
| EXT069 | A | cross_order_material_compare | 请帮我把NT12R/66GDF(法国-2026-00104)、NT12R/66GDF(法国Synapsun-2026-00114)两份BOM的五类关键材料拉成对比表。 | 已完成 BOM 差异对比，变化 8 条，仅左侧 4 条，仅右侧 0 条。 |
| EXT070 | A | cross_order_material_compare | 把NT12R/66GDF(意大利-2026-00097)和NT12R/66GDF(德国Anumar-2026-00077)这两单的玻璃、间隙贴膜、焊带、汇流条、接线盒做个差异对比。 | 已完成 BOM 差异对比，变化 7 条，仅左侧 1 条，仅右侧 2 条。 |
| EXT071 | A | cross_order_material_compare | NT12R/66GDF(意大利-2026-00097)和NT12R/66GDF(德国Anumar-2026-00077)同型号但客户不一样，核心材料规格有没有差别？ | 已完成 BOM 差异对比，变化 7 条，仅左侧 1 条，仅右侧 2 条。 |
| EXT072 | A | cross_order_material_compare | 请帮我把NT12R/66GDF(意大利-2026-00097)、NT12R/66GDF(德国Anumar-2026-00077)两份BOM的五类关键材料拉成对比表。 | 已完成 BOM 差异对比，变化 7 条，仅左侧 1 条，仅右侧 2 条。 |
| EXT073 | A | cross_order_material_compare | 把NT12R/66GDF(印尼Hijau-2026-00117)和NT12R/66GDF(印尼宾坦岛-2026-00096)这两单的玻璃、间隙贴膜、焊带、汇流条、接线盒做个差异对比。 | 已完成 BOM 差异对比，变化 4 条，仅左侧 3 条，仅右侧 5 条。 |
| EXT074 | A | cross_order_material_compare | NT12R/66GDF(印尼Hijau-2026-00117)和NT12R/66GDF(印尼宾坦岛-2026-00096)同型号但客户不一样，核心材料规格有没有差别？ | 已完成 BOM 差异对比，变化 4 条，仅左侧 3 条，仅右侧 5 条。 |
| EXT075 | A | cross_order_material_compare | 把NT12R/66GDF(日本Krannich-2026-00109)和NT12R/66GDF(西班牙SII-2026-00111)这两单的玻璃、间隙贴膜、焊带、汇流条、接线盒做个差异对比。 | 已完成 BOM 差异对比，变化 0 条，仅左侧 1 条，仅右侧 1 条。 |
| EXT076 | A | cross_order_material_compare | NT12R/66GDF(日本Krannich-2026-00109)和NT12R/66GDF(西班牙SII-2026-00111)同型号但客户不一样，核心材料规格有没有差别？ | 已完成 BOM 差异对比，变化 0 条，仅左侧 1 条，仅右侧 1 条。 |
| EXT077 | A | cross_order_material_compare | 把NT12R/66GDF(哥伦比亚Amara-2026-00115)和NT12R/66GDF(危地马拉ECOLUMEN-2026-00121)这两单的玻璃、间隙贴膜、焊带、汇流条、接线盒做个差异对比。 | 已完成 BOM 差异对比，变化 0 条，仅左侧 0 条，仅右侧 0 条。 |
| EXT078 | A | cross_order_material_compare | NT12R/66GDF(哥伦比亚Amara-2026-00115)和NT12R/66GDF(危地马拉ECOLUMEN-2026-00121)同型号但客户不一样，核心材料规格有没有差别？ | 已完成 BOM 差异对比，变化 0 条，仅左侧 0 条，仅右侧 0 条。 |
| EXT079 | B | cross_order_material_compare | 把NT12R/66GDF(德国Kumandra芜湖电池-2026-00113)和NT12R/66GDF(肯尼亚Nationwide-2026-00120)这两单的玻璃、间隙贴膜、焊带、汇流条、接线盒做个差异对比。 | 当前问题缺少或存在歧义的槽位：file_instance。请补充订单、版本、材料或查询范围。 |
| EXT080 | B | cross_order_material_compare | NT12R/66GDF(德国Kumandra芜湖电池-2026-00113)和NT12R/66GDF(肯尼亚Nationwide-2026-00120)同型号但客户不一样，核心材料规格有没有差别？ | 当前问题缺少或存在歧义的槽位：file_instance。请补充订单、版本、材料或查询范围。 |
| EXT081 | A | single_order_material_specs | NT10/78GDF(哥伦比亚COEXITO -2026-00067)这单的接线盒规格单独给我拎出来，我这边要先确认。 | 已查询订单 NT10/78GDF（哥伦比亚COEXITO -2026-00067） 的 1 条 BOM 材料规格。 |
| EXT082 | A | single_order_material_specs | 只看NT12R/66GDF(法国Synapsun-2026-00114)的玻璃，麻烦把物料描述发我。 | 已查询订单 NT12R/66GDF（法国Synapsun-2026-00114） 的 2 条 BOM 材料规格。 |
| EXT083 | A | single_order_material_specs | NT12R/66GDF(法国Synapsun-2026-00114)这份BOM里间隙贴膜用的是什么规格？ | 已查询订单 NT12R/66GDF（法国Synapsun-2026-00114） 的 3 条 BOM 材料规格。 |
| EXT085 | A | single_order_material_specs | NT12R/66GDF(法国Synapsun-2026-00114)这单的汇流条规格单独给我拎出来，我这边要先确认。 | 已查询订单 NT12R/66GDF（法国Synapsun-2026-00114） 的 2 条 BOM 材料规格。 |
| EXT086 | A | single_order_material_specs | 只看NT12R/66GDF(法国Synapsun-2026-00114)的接线盒，麻烦把物料描述发我。 | 已查询订单 NT12R/66GDF（法国Synapsun-2026-00114） 的 1 条 BOM 材料规格。 |
| EXT087 | B | clarification | NT12/66GDF(苏格兰-2026-00048)这份BOM里电池片用的是什么规格？ | 当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。 |
| EXT089 | B | clarification | NT12/66GDF(苏格兰-2026-00048)这单的EVA胶膜规格单独给我拎出来，我这边要先确认。 | 当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。 |
| EXT090 | A | single_order_material_specs | 只看NT12R/66GDF(日本Krannich-2026-00109)的接线盒，麻烦把物料描述发我。 | 已查询订单 NT12R/66GDF（日本Krannich-2026-00109） 的 1 条 BOM 材料规格。 |
| EXT091 | A | single_order_material_specs | NT12R/66GDF(日本Krannich-2026-00109)这份BOM里玻璃用的是什么规格？ | 已查询订单 NT12R/66GDF（日本Krannich-2026-00109） 的 2 条 BOM 材料规格。 |
| EXT093 | A | single_order_material_specs | NT12R/66GDF(深圳建融钢边框-2025-01073)这单的汇流条规格单独给我拎出来，我这边要先确认。 | 已查询订单 NT12R/66GDF（深圳建融-2025-01073） 的 7 条 BOM 材料规格。 |
| EXT094 | A | single_order_material_specs | 只看NT12R/78GDF(华电南通-2025-01220)的玻璃，麻烦把物料描述发我。 | 已查询订单 NT12R/78GDF(华电南通-2025-01220)Bill of materials 的 4 条 BOM 材料规格。 |
| EXT095 | B | clarification | NT12R/78GDF(华电南通-2025-01220)这份BOM里电池片用的是什么规格？ | 当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。 |
| EXT097 | B | single_order_material_specs | NT10/78GDF(江苏汉腾-2026-00106)这单的汇流条规格单独给我拎出来，我这边要先确认。 | 当前问题缺少或存在歧义的槽位：order_identity。请补充订单、版本、材料或查询范围。 |
| EXT098 | B | single_order_material_specs | 只看NT10/78GDF(石家庄科林-2026-00106)的焊带，麻烦把物料描述发我。 | 当前问题缺少或存在歧义的槽位：order_identity。请补充订单、版本、材料或查询范围。 |
| EXT099 | B | single_order_material_specs | NT12R/66GDF(肯尼亚Nationwide-2026-00120)这份BOM里接线盒用的是什么规格？ | 当前问题缺少或存在歧义的槽位：file_instance。请补充订单、版本、材料或查询范围。 |
| EXT102 | A | multi_order_material_table | 这几单 NT12/66GDF(苏格兰-2026-00048)、NT10/78GDF(泰州中来 -2026-00127)、NT12R/66GDF(意大利-2026-00097) 我想一次性看核心材料规格，帮我拉个表。 | 已按当前条件生成 35 条计划 BOM 材料清单。 |
| EXT106 | A | multi_order_material_table | 这几单 NT12R/66GDF(法国-2026-00104)、NT12R/66GDF(法国Synapsun-2026-00114)、NT12R/66GDF(日本Krannich-2026-00109) 我想一次性看核心材料规格，帮我拉个表。 | 已按当前条件生成 35 条计划 BOM 材料清单。 |
| EXT110 | A | multi_order_material_table | 这几单 NT10/78GDF(哥伦比亚COEXITO -2026-00067)、NT10/78GDF(江苏汉腾-2026-00106)、NT10/78GDF(石家庄科林-2026-00106) 我想一次性看核心材料规格，帮我拉个表。 | 已按当前条件生成 83 条计划 BOM 材料清单。 |
| EXT114 | A | multi_order_material_table | 这几单 NT12/66GDF(苏州康达尔-2026-00087)、NT12/66GDF(多米尼加Sistemi-2026-00099)、NT12/66GDF(萨尔瓦多Compania-2026-00103) 我想一次性看核心材料规格，帮我拉个表。 | 已按当前条件生成 78 条计划 BOM 材料清单。 |
| EXT118 | A | multi_order_material_table | 这几单 NT12R/66GDF(德国Anumar-2026-00077)、NT12R/66GDF(意大利-2026-00097)、NT12R/66GDF(哥伦比亚Amara-2026-00115) 我想一次性看核心材料规格，帮我拉个表。 | 已按当前条件生成 38 条计划 BOM 材料清单。 |
| EXT122 | A | multi_order_material_table | 这几单 NT12R/66GDF(西班牙SII-2026-00111)、NT12R/66GDF(德国Kumandra芜湖电池-2026-00113)、NT12R/66GDF(肯尼亚Nationwide-2026-00120) 我想一次性看核心材料规格，帮我拉个表。 | 已按当前条件生成 33 条计划 BOM 材料清单。 |
| EXT125 | B | material_consistency_check | 现在NT12R/66GDF这批订单里，哪些订单的接线盒规格不一样？帮我按订单列出来。 | 当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。 |
| EXT126 | A | scope_material_list | 把所有NT10/78GDF订单的玻璃规格和供应商放一起看，我想判断能不能合并采购。 | 已按当前条件生成 60 条计划 BOM 材料清单。 |
| EXT127 | A | multi_order_material_table | 苏格兰00048和柬埔寨太阳花00082这两单，哪些核心材料可以直接复用？ | 已按当前条件生成 31 条计划 BOM 材料清单。 |
| EXT129 | A | material_presence_check | 日本Krannich00109的A0和A1版本，接线盒有没有变更？ | 已完成 28 个当前 BOM 版本的物料存在性检查，返回 0 条匹配记录。 |
| EXT130 | A | material_presence_check | 把哥伦比亚、危地马拉、萨尔瓦多这几单的接线盒规格拉出来，我要看海外项目有没有统一。 | 已完成 28 个当前 BOM 版本的物料存在性检查，返回 0 条匹配记录。 |
| EXT131 | B | clarification | 苏格兰00048这单的POE胶膜和EVA胶膜分别是什么方案？ | 当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。 |
| EXT132 | B | clarification | 华电南通2025-01220这单用的是什么电池片方案？ | 当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。 |
| EXT134 | A | material_presence_check | COEXITO00067从A0到A1，先看下玻璃和接线盒有没有变化。 | 已完成 28 个当前 BOM 版本的物料存在性检查，返回 0 条匹配记录。 |
| EXT135 | B | single_order_material_specs | 石家庄科林00106这单的焊带和汇流条规格发我，我要跟客户核一下。 | 当前问题缺少或存在歧义的槽位：order_identity。请补充订单、版本、材料或查询范围。 |
| EXT136 | A | multi_order_material_table | NT12/66GDF和NT12R/66GDF两类订单，玻璃尺寸是不是一样？先拿苏格兰00048和意大利00097做个样例给我。 | 已按当前条件生成 4 条计划 BOM 材料清单。 |
| EXT137 | A | scope_material_list | 把2026年所有带接线盒的订单列出来，并把接线盒规格带上。 | 已按当前条件生成 24 条计划 BOM 材料清单。 |
| EXT138 | A | material_presence_check | 现有BOM里哪些订单没有接线盒材料，先帮我列出来。 | 已完成 28 个当前 BOM 版本的物料存在性检查，返回 0 条匹配记录。 |
| EXT140 | B | specific_material_query | 印尼Hijau和印尼宾坦岛这两单的核心材料方案是不是一个口径？ | 当前问题缺少或存在歧义的槽位：order_id。请补充订单、版本、材料或查询范围。 |
| EXT142 | B | clarification | 德国Anumar和德国Kumandra这两单，哪些物料规格一致，可以一起询价？ | 当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。 |
| EXT143 | A | single_order_material_specs | 深圳建融钢边框2025-01073这单的汇流条和电池片规格帮我拎出来。 | 已查询订单 NT12R/66GDF（深圳建融-2025-01073） 的 7 条 BOM 材料规格。 |
