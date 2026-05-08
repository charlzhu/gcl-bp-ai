# E2E QA Phase 0 数据资产画像报告

- 生成时间：2026-05-07T00:30:18
- 执行边界：仅准备数据资产，不计算标准答案，不访问数据库，不修改业务代码。
- 解压目录：`/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/ai/eval/workdir/attachments_extracted`
- 样例题 JSONL：`/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/ai/eval/sample_questions.jsonl`

## 附件清单

| 附件 | 类型 | 大小 | 有效提取文件数 | 过滤项数 | 解析/解压错误 |
| --- | --- | ---: | ---: | ---: | ---: |
| 23 年至 25 年物流源数据.zip | zip | 5.0 MB | 4 | 4 | 0 |
| BOM 源数据.zip | zip | 679.0 KB | 34 | 35 | 0 |
| 物流和 bom样例题.docx | docx | 74.0 KB | 0 | 0 | 0 |

过滤规则：跳过路径中包含 `__MACOSX` 的成员，以及文件名以 `._` 开头的 macOS 资源分叉文件。

## 物流 Excel 文件画像

- 文件数：4；sheet 数：5；非空数据行数合计：24235

| 文件 | 年份猜测 | sheet 数 | 数据行合计 | 解析错误 |
| --- | --- | ---: | ---: | ---: |
| 2023年安徽合肥发运台账.xlsx | [2023] | 1 | 3490 | 0 |
| 2023年安徽阜宁物流发运台账.xlsx | [2023] | 1 | 867 | 0 |
| 2024年物流发运总台账.xlsx | [2024] | 1 | 7049 | 0 |
| 2025年物流发运总台账.xlsx | [2025] | 2 | 12829 | 0 |

### 2023年安徽合肥发运台账.xlsx

| Sheet | 表头行 | 数据行 | 字段数 | 年份猜测 | 关键字段 | 字段预览 |
| --- | ---: | ---: | ---: | --- | --- | --- |
| Sheet1 | 1 | 3490 | 31 | [2023] | date=发货日期；region=区域；province=省份；city=城市；origin=始发地；customer=客户名称（标准名称；最终客户）；product_spec=规格；product_spec=要求中标车辆型号；等 22 项 | 发货日期、客户名称（标准名称；最终客户）、合同编号、询比价编号、地址、省份、城市、路程/KM、规格、功率、日计划发运件数、日实际发运件数 等 31 个字段 |

### 2023年安徽阜宁物流发运台账.xlsx

| Sheet | 表头行 | 数据行 | 字段数 | 年份猜测 | 关键字段 | 字段预览 |
| --- | ---: | ---: | ---: | --- | --- | --- |
| Sheet1 | 1 | 867 | 31 | [2023] | date=发货日期；region=区域；province=省份；city=城市；origin=始发地；customer=客户名称（标准名称；最终客户）；product_spec=规格；product_spec=要求中标车辆型号；等 23 项 | 发货日期、客户名称（标准名称；最终客户）、合同编号、询比价编号、地址、省份、城市、路程/KM、规格、功率、日计划发运件数、日实际发运件数 等 31 个字段 |

### 2024年物流发运总台账.xlsx

| Sheet | 表头行 | 数据行 | 字段数 | 年份猜测 | 关键字段 | 字段预览 |
| --- | ---: | ---: | ---: | --- | --- | --- |
| Sheet1 | 1 | 7049 | 30 | [2024] | date=发货日期；region=区域；province=省份；city=城市；origin=始发地；customer=客户名称（标准名称；最终客户）；product_spec=规格；product_spec=要求中标车辆型号；等 22 项 | 发货日期、客户名称（标准名称；最终客户）、合同编号、询比价编号、地址、省份、城市、路程/KM、规格、功率、日计划发运件数、日实际发运件数 等 30 个字段 |

### 2025年物流发运总台账.xlsx

| Sheet | 表头行 | 数据行 | 字段数 | 年份猜测 | 关键字段 | 字段预览 |
| --- | ---: | ---: | ---: | --- | --- | --- |
| Sheet1 | 1 | 12829 | 30 | [2025] | date=发货日期；region=区域；province=省份；city=城市；origin=始发地；customer=客户名称（标准名称； 最终客户）；product_spec=规格；product_spec=要求中标车辆型号；等 23 项 | 发货日期、客户名称（标准名称； 最终客户）、合同编号、询比价编号、地址、省份、城市、路程/KM、规格、功率、日计划发运件数、日实际发运件数 等 30 个字段 |
| Sheet2 | 1 | 0 | 30 | [2025] | date=发货日期；region=区域；province=省份；city=城市；origin=始发地；customer=客户名称（标准名称； 最终客户）；product_spec=规格；product_spec=要求中标车辆型号；等 23 项 | 发货日期、客户名称（标准名称； 最终客户）、合同编号、询比价编号、地址、省份、城市、路程/KM、规格、功率、日计划发运件数、日实际发运件数 等 30 个字段 |

## BOM xls 文件画像

- 文件数：34；sheet 数：34；非空数据行数合计：7676

| 文件 | 订单号猜测 | 型号猜测 | 版本 | sheet 数 | 数据行合计 | 关键物料命中 | 解析错误 |
| --- | --- | --- | --- | ---: | ---: | --- | ---: |
| NT1078GDF(哥伦比亚COEXITO-2026-00067)Billofmaterials-A.xls | 2026-00067 | NT1078GDF | A | 1 | 308 | 玻璃:7；间隙贴膜:1；汇流条:8；接线盒:3；线盒:5 | 0 |
| NT1078GDF(哥伦比亚COEXITO-2026-00067)Billofmaterials-B.xls | 2026-00067 | NT1078GDF | B | 1 | 310 | 玻璃:7；间隙贴膜:1；焊带:1；汇流条:8；接线盒:3；线盒:5 | 0 |
| NT1078GDF(江苏汉腾-2026-00106)Billofmaterials-A.xls | 2026-00106 | NT1078GDF | A | 1 | 253 | 玻璃:72；汇流条:8；接线盒:3；线盒:5 | 0 |
| NT1078GDF(泰州中来-2026-00127)Billofmaterials-B.xls | 2026-00127 | NT1078GDF | B | 1 | 280 | 玻璃:7；间隙贴膜:1；汇流条:4；接线盒:3；线盒:6 | 0 |
| NT1078GDF(石家庄科林-2026-00106)Billofmaterials-A (2).xls | 2026-00106 | NT1078GDF | A | 1 | 328 | 玻璃:64；汇流条:7；接线盒:3；线盒:5 | 0 |
| NT1266GDF(国科华鑫仙居-2025-01063)Billofmaterials-E.xls | 2025-01063 | NT1266GDF | E | 1 | 248 | 玻璃:12；间隙贴膜:1；汇流条:5；接线盒:3；线盒:5 | 0 |
| NT1266GDF(多米尼加Sistemi-2026-00099)Billofmaterials-A.xls | 2026-00099 | NT1266GDF | A | 1 | 265 | 玻璃:8；间隙贴膜:2；汇流条:8；接线盒:5；线盒:7 | 0 |
| NT1266GDF(天合富家新-2025-00844)Billofmaterials-C.xls | 2025-00844 | NT1266GDF | C | 1 | 156 | 玻璃:32；焊带:7；汇流条:10；接线盒:3；线盒:5 | 0 |
| NT1266GDF(柬埔寨太阳花-2026-00082)Billofmaterials-C.xls | 2026-00082 | NT1266GDF | C | 1 | 180 | 玻璃:26；焊带:1；汇流条:9；接线盒:3；线盒:5 | 0 |
| NT1266GDF(苏州康达尔-2026-00087)Billofmaterials-B.xls | 2026-00087 | NT1266GDF | B | 1 | 276 | 玻璃:50；焊带:2；汇流条:12；接线盒:3；线盒:5 | 0 |
| NT1266GDF(苏格兰-2026-00048)Billofmaterials-A.xls | 2026-00048 | NT1266GDF | A | 1 | 100 | 玻璃:9；间隙贴膜:1；汇流条:4；接线盒:4；线盒:9 | 0 |
| NT1266GDF(苏格兰-2026-00048)Billofmaterials-B(2).xls | 2026-00048 | NT1266GDF | B | 1 | 96 | 玻璃:9；间隙贴膜:1；汇流条:4；接线盒:4；线盒:7 | 0 |
| NT1266GDF(萨尔瓦多Compania-2026-00103)Billofmaterials-A.xls | 2026-00103 | NT1266GDF | A | 1 | 268 | 玻璃:50；汇流条:4；接线盒:3；线盒:5 | 0 |
| NT12R66GDF(印尼Hijau-2026-00117)Billofmaterials-A.xls | 2026-00117 | NT12R66GDF | A | 1 | 90 | 玻璃:7；间隙贴膜:1；汇流条:4；接线盒:5；线盒:7 | 0 |
| NT12R66GDF(印尼宾坦岛-2026-00096)Billofmaterials-A.xls | 2026-00096 | NT12R66GDF | A | 1 | 130 | 玻璃:7；间隙贴膜:1；汇流条:4；接线盒:3；线盒:5 | 0 |
| NT12R66GDF(危地马拉ECOLUMEN-2026-00121)Billofmaterials-B.xls | 2026-00121 | NT12R66GDF | B | 1 | 298 | 玻璃:7；间隙贴膜:1；汇流条:4；接线盒:5；线盒:7 | 0 |
| NT12R66GDF(哥伦比亚Amara-2026-00115)Billofmaterials-A (1).xls | 2026-00115 | NT12R66GDF | A | 1 | 299 | 玻璃:7；间隙贴膜:1；汇流条:5；接线盒:5；线盒:7 | 0 |
| NT12R66GDF(多米尼加Escala-2026-00107)Billofmaterials-B.xls | 2026-00107 | NT12R66GDF | B | 1 | 204 | 玻璃:7；间隙贴膜:1；焊带:2；汇流条:4；接线盒:3；线盒:5 | 0 |
| NT12R66GDF(德国Anumar-2026-00077)Billofmaterials-B.xls | 2026-00077 | NT12R66GDF | B | 1 | 132 | 玻璃:8；间隙贴膜:1；汇流条:9；接线盒:6；线盒:8 | 0 |
| NT12R66GDF(德国Anumar-2026-00077)Billofmaterials-C.xls | 2026-00077 | NT12R66GDF | C | 1 | 135 | 玻璃:8；间隙贴膜:1；焊带:1；汇流条:9；接线盒:6；线盒:8 | 0 |
| NT12R66GDF(德国Kumandra芜湖电池-2026-00113)Billofmaterials-B.xls | 2026-00113 | NT12R66GDF | B | 1 | 308 | 玻璃:7；汇流条:4；接线盒:3；线盒:5 | 0 |
| NT12R66GDF(意大利-2026-00097)Billofmaterials-B.xls | 2026-00097 | NT12R66GDF | B | 1 | 103 | 玻璃:8；间隙贴膜:1；汇流条:4；接线盒:6；线盒:8 | 0 |
| NT12R66GDF(意大利-2026-00097)Billofmaterials-C.xls | 2026-00097 | NT12R66GDF | C | 1 | 106 | 玻璃:8；间隙贴膜:1；汇流条:9；接线盒:6；线盒:8 | 0 |
| NT12R66GDF(日本Krannich-2026-00109)Billofmaterials-A.xls | 2026-00109 | NT12R66GDF | A | 1 | 299 | 玻璃:7；间隙贴膜:1；汇流条:4；接线盒:5；线盒:7 | 0 |
| NT12R66GDF(日本Krannich-2026-00109)Billofmaterials-B.xls | 2026-00109 | NT12R66GDF | B | 1 | 303 | 玻璃:7；间隙贴膜:1；汇流条:4；接线盒:5；线盒:7 | 0 |
| NT12R66GDF(法国-2026-00104)Billofmaterials-B (2).xls | 2026-00104 | NT12R66GDF | B | 1 | 133 | 玻璃:11；焊带:1；汇流条:5；接线盒:5；线盒:7 | 0 |
| NT12R66GDF(法国Synapsun-2026-00114)Billofmaterials-A.xls | 2026-00114 | NT12R66GDF | A | 1 | 120 | 玻璃:9；汇流条:4；接线盒:4；线盒:4 | 0 |
| NT12R66GDF(深圳建融钢边框-2025-01073)Billofmaterials-D(1).xls | 2025-01073 | NT12R66GDF | D | 1 | 413 | 玻璃:7；间隙贴膜:1；焊带:6；汇流条:15；接线盒:3；线盒:5 | 0 |
| NT12R66GDF(突尼斯MIM2A-2026-00061)Billofmaterials-B.xls | 2026-00061 | NT12R66GDF | B | 1 | 196 | 玻璃:11；间隙贴膜:1；汇流条:4；接线盒:3；线盒:5 | 0 |
| NT12R66GDF(肯尼亚Nationwide-2026-00120)Billofmaterials-A (2).xls | 2026-00120 | NT12R66GDF | A | 1 | 301 | 玻璃:8；间隙贴膜:3；汇流条:8；接线盒:5；线盒:7 | 0 |
| NT12R66GDF(肯尼亚Nationwide-2026-00120)Billofmaterials-A (3).xls | 2026-00120 | NT12R66GDF | A | 1 | 298 | 玻璃:10；汇流条:7；接线盒:5；线盒:7 | 0 |
| NT12R66GDF(菲律宾LUCA-2026-00102)Billofmaterials-B.xls | 2026-00102 | NT12R66GDF | B | 1 | 194 | 玻璃:12；间隙贴膜:1；汇流条:4；接线盒:3；线盒:5 | 0 |
| NT12R66GDF(西班牙SII-2026-00111)Billofmaterials-A.xls | 2026-00111 | NT12R66GDF | A | 1 | 299 | 玻璃:7；间隙贴膜:1；汇流条:4；接线盒:5；线盒:7 | 0 |
| NT12R78GDF(华电南通-2025-01220)Billofmaterials-D.xls | 2025-01220 | NT12R78GDF | D | 1 | 247 | 玻璃:12；间隙贴膜:3；汇流条:5；接线盒:3；线盒:5 | 0 |

### BOM 字段与关键物料可能字段

- `NT1078GDF(哥伦比亚COEXITO-2026-00067)Billofmaterials-A.xls`
  - Sheet `材料清单`：字段 8 个，数据行 308，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:7；间隙贴膜:1；汇流条:8；接线盒:3；线盒:5
- `NT1078GDF(哥伦比亚COEXITO-2026-00067)Billofmaterials-B.xls`
  - Sheet `材料清单`：字段 8 个，数据行 310，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:7；间隙贴膜:1；焊带:1；汇流条:8；接线盒:3；线盒:5
- `NT1078GDF(江苏汉腾-2026-00106)Billofmaterials-A.xls`
  - Sheet `材料清单`：字段 8 个，数据行 253，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:72；汇流条:8；接线盒:3；线盒:5
- `NT1078GDF(泰州中来-2026-00127)Billofmaterials-B.xls`
  - Sheet `材料清单`：字段 8 个，数据行 280，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:7；间隙贴膜:1；汇流条:4；接线盒:3；线盒:6
- `NT1078GDF(石家庄科林-2026-00106)Billofmaterials-A (2).xls`
  - Sheet `材料清单`：字段 8 个，数据行 328，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:64；汇流条:7；接线盒:3；线盒:5
- `NT1266GDF(国科华鑫仙居-2025-01063)Billofmaterials-E.xls`
  - Sheet `材料清单`：字段 8 个，数据行 248，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:12；间隙贴膜:1；汇流条:5；接线盒:3；线盒:5
- `NT1266GDF(多米尼加Sistemi-2026-00099)Billofmaterials-A.xls`
  - Sheet `材料清单`：字段 8 个，数据行 265，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:8；间隙贴膜:2；汇流条:8；接线盒:5；线盒:7
- `NT1266GDF(天合富家新-2025-00844)Billofmaterials-C.xls`
  - Sheet `材料清单`：字段 8 个，数据行 156，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:32；焊带:7；汇流条:10；接线盒:3；线盒:5
- `NT1266GDF(柬埔寨太阳花-2026-00082)Billofmaterials-C.xls`
  - Sheet `材料清单`：字段 8 个，数据行 180，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:26；焊带:1；汇流条:9；接线盒:3；线盒:5
- `NT1266GDF(苏州康达尔-2026-00087)Billofmaterials-B.xls`
  - Sheet `材料清单`：字段 8 个，数据行 276，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:50；焊带:2；汇流条:12；接线盒:3；线盒:5
- `NT1266GDF(苏格兰-2026-00048)Billofmaterials-A.xls`
  - Sheet `材料清单`：字段 8 个，数据行 100，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:9；间隙贴膜:1；汇流条:4；接线盒:4；线盒:9
- `NT1266GDF(苏格兰-2026-00048)Billofmaterials-B(2).xls`
  - Sheet `材料清单`：字段 8 个，数据行 96，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:9；间隙贴膜:1；汇流条:4；接线盒:4；线盒:7
- `NT1266GDF(萨尔瓦多Compania-2026-00103)Billofmaterials-A.xls`
  - Sheet `材料清单`：字段 8 个，数据行 268，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:50；汇流条:4；接线盒:3；线盒:5
- `NT12R66GDF(印尼Hijau-2026-00117)Billofmaterials-A.xls`
  - Sheet `材料清单`：字段 8 个，数据行 90，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:7；间隙贴膜:1；汇流条:4；接线盒:5；线盒:7
- `NT12R66GDF(印尼宾坦岛-2026-00096)Billofmaterials-A.xls`
  - Sheet `材料清单`：字段 8 个，数据行 130，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:7；间隙贴膜:1；汇流条:4；接线盒:3；线盒:5
- `NT12R66GDF(危地马拉ECOLUMEN-2026-00121)Billofmaterials-B.xls`
  - Sheet `材料清单`：字段 8 个，数据行 298，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:7；间隙贴膜:1；汇流条:4；接线盒:5；线盒:7
- `NT12R66GDF(哥伦比亚Amara-2026-00115)Billofmaterials-A (1).xls`
  - Sheet `材料清单`：字段 8 个，数据行 299，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:7；间隙贴膜:1；汇流条:5；接线盒:5；线盒:7
- `NT12R66GDF(多米尼加Escala-2026-00107)Billofmaterials-B.xls`
  - Sheet `材料清单`：字段 8 个，数据行 204，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:7；间隙贴膜:1；焊带:2；汇流条:4；接线盒:3；线盒:5
- `NT12R66GDF(德国Anumar-2026-00077)Billofmaterials-B.xls`
  - Sheet `材料清单`：字段 8 个，数据行 132，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:8；间隙贴膜:1；汇流条:9；接线盒:6；线盒:8
- `NT12R66GDF(德国Anumar-2026-00077)Billofmaterials-C.xls`
  - Sheet `材料清单`：字段 8 个，数据行 135，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:8；间隙贴膜:1；焊带:1；汇流条:9；接线盒:6；线盒:8
- `NT12R66GDF(德国Kumandra芜湖电池-2026-00113)Billofmaterials-B.xls`
  - Sheet `材料清单`：字段 8 个，数据行 308，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:7；汇流条:4；接线盒:3；线盒:5
- `NT12R66GDF(意大利-2026-00097)Billofmaterials-B.xls`
  - Sheet `材料清单`：字段 8 个，数据行 103，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:8；间隙贴膜:1；汇流条:4；接线盒:6；线盒:8
- `NT12R66GDF(意大利-2026-00097)Billofmaterials-C.xls`
  - Sheet `材料清单`：字段 8 个，数据行 106，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:8；间隙贴膜:1；汇流条:9；接线盒:6；线盒:8
- `NT12R66GDF(日本Krannich-2026-00109)Billofmaterials-A.xls`
  - Sheet `材料清单`：字段 8 个，数据行 299，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:7；间隙贴膜:1；汇流条:4；接线盒:5；线盒:7
- `NT12R66GDF(日本Krannich-2026-00109)Billofmaterials-B.xls`
  - Sheet `材料清单`：字段 8 个，数据行 303，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:7；间隙贴膜:1；汇流条:4；接线盒:5；线盒:7
- `NT12R66GDF(法国-2026-00104)Billofmaterials-B (2).xls`
  - Sheet `材料清单`：字段 8 个，数据行 133，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:11；焊带:1；汇流条:5；接线盒:5；线盒:7
- `NT12R66GDF(法国Synapsun-2026-00114)Billofmaterials-A.xls`
  - Sheet `材料清单`：字段 8 个，数据行 120，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:9；汇流条:4；接线盒:4；线盒:4
- `NT12R66GDF(深圳建融钢边框-2025-01073)Billofmaterials-D(1).xls`
  - Sheet `材料清单`：字段 8 个，数据行 413，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:7；间隙贴膜:1；焊带:6；汇流条:15；接线盒:3；线盒:5
- `NT12R66GDF(突尼斯MIM2A-2026-00061)Billofmaterials-B.xls`
  - Sheet `材料清单`：字段 8 个，数据行 196，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:11；间隙贴膜:1；汇流条:4；接线盒:3；线盒:5
- `NT12R66GDF(肯尼亚Nationwide-2026-00120)Billofmaterials-A (2).xls`
  - Sheet `材料清单`：字段 8 个，数据行 301，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:8；间隙贴膜:3；汇流条:8；接线盒:5；线盒:7
- `NT12R66GDF(肯尼亚Nationwide-2026-00120)Billofmaterials-A (3).xls`
  - Sheet `材料清单`：字段 8 个，数据行 298，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:10；汇流条:7；接线盒:5；线盒:7
- `NT12R66GDF(菲律宾LUCA-2026-00102)Billofmaterials-B.xls`
  - Sheet `材料清单`：字段 8 个，数据行 194，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:12；间隙贴膜:1；汇流条:4；接线盒:3；线盒:5
- `NT12R66GDF(西班牙SII-2026-00111)Billofmaterials-A.xls`
  - Sheet `材料清单`：字段 8 个，数据行 299，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:7；间隙贴膜:1；汇流条:4；接线盒:5；线盒:7
- `NT12R78GDF(华电南通-2025-01220)Billofmaterials-D.xls`
  - Sheet `材料清单`：字段 8 个，数据行 247，可能字段：material_name=物料名称；spec_desc=描述；quantity=标准用量；unit=单位，关键物料命中：玻璃:12；间隙贴膜:3；汇流条:5；接线盒:3；线盒:5

## 样例题统计

- 样例题总数：1391
- 领域分布：`{"bom": 12, "logistics": 1377, "unknown": 2}`
- 年份分布：`{"2023": 343, "2024": 345, "2025": 480, "2026": 167, "未识别": 344}`
- 可能需要 2026 MySQL 的物流题：160

| 分类 | 数量 |
| --- | ---: |
| logistics_other | 408 |
| logistics_shipment_watt | 305 |
| logistics_vehicle_count | 175 |
| logistics_cost_sort | 174 |
| logistics_company_unit_price | 78 |
| logistics_ambiguous_or_current | 52 |
| logistics_total_fee | 42 |
| logistics_topn | 36 |
| logistics_procurement_task | 34 |
| logistics_count | 26 |
| logistics_transport_mode_count | 18 |
| logistics_loading_efficiency | 9 |
| logistics_distance | 7 |
| logistics_plan_actual_variance | 5 |
| logistics_driver_consistency | 5 |
| bom_material_compare | 4 |
| bom_material_spec | 4 |
| bom_material_table | 4 |
| logistics_rate_statistics | 3 |
| unknown | 2 |

### 样例题首尾检查

- `Q0001` 订单A-00001和订单B-00002材料对比,有哪些材料不一致?
- `Q0002` 订单00001的玻璃、间隙贴膜,焊带、汇流条、接线盒的规格描述?
- `Q0003` 查找订单00001/00002/00003/00004/00005这几个订单的玻璃、间隙贴膜,焊带、汇流条、接线盒的规格描述并生成表格?
- `Q0004` 订单00104的的玻璃、间隙贴膜,焊带、汇流条、接线盒的规格描述?
- `Q0005` 订单00067和订单00106玻璃、间隙贴膜,焊带、汇流条、接线盒的规格描述有什么不一样,并用表格统计出来
- `...` ...
- `Q1387` 请统计2025年江苏久鼎供应链管理有限公司按月份和区域组合后的发运量、总费用和费用占比？
- `Q1388` 请统计2025年浙江英赋嘉供应链科技股份有限公司按月份和区域组合后的发运量、总费用和费用占比？
- `Q1389` 请统计2025年江苏鲲越国际物流有限公司按月份和区域组合后的发运量、总费用和费用占比？
- `Q1390` 请统计2025年常州安提物流有限公司按月份和区域组合后的发运量、总费用和费用占比？
- `Q1391` 请统计2025年宿迁市昆仑物流有限公司按月份和区域组合后的发运量、总费用和费用占比？

## 解析失败

- 未发现 Excel sheet 解析失败或 zip 解压失败。
