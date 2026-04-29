# PLAN_BOM_WAVE2_BASELINE_FREEZE

## 基线结论

计划 BOM Wave2 当前基线已冻结，可以进入小范围业务试运行。

## 正式状态

- A：`86`
- B：`40`
- C：`3`
- D：`0`
- Wave2 前基线：`A=67 / B=59 / C=3 / D=0`
- Wave2 新增迁入 A：`19`
- 原 B=59 快照：迁 A `19`，继续 B `40`，转 C `0`

## 正式问题来源

- 文件：`BOM问题.xlsx`
- 有效问题：`129`
- docx 仅作为兼容输入，不是当前正式问题源。

## 正式数据来源

- 文件：`BOM 源数据.zip`
- Excel 文件：`34` 个
- 导入成功：`34` 个
- 标准化材料行：`4034` 条

## 当前支持能力

- Excel 上传：`POST /api/v1/plan-bom/upload`
- 自然语言问答：`POST /api/v1/plan-bom/qa/ask`
- 单订单查询
- 多订单表格
- 跨订单对比
- 指定材料查询
- BOM 版本类追问
- B 类追问
- C 类拒答解释
- qwen-plus NLU 候选
- qwen-plus 答案表达层

## 当前核心五类材料

- `glass`：玻璃
- `gap_film`：间隙贴膜 / 间隙膜
- `interconnect_bar`：焊带 / 互联条
- `busbar`：汇流条
- `junction_box`：接线盒 / 线盒

## 非核心材料处理策略

- 非核心材料不进入核心五类 `detail / compare` schema。
- 当前识别到 `cell / eva_film / frame` 等非核心材料时，返回受控追问或解释。
- API 不抛 500，不把非核心材料硬塞进核心五类材料查询。

## 当前不能承诺的内容

- 不承诺所有 BOM 问题都直接回答。
- 不做功率倒推。
- 不编造物料规格。
- 不编造 BOM 版本。
- 不把 B/C 硬包装成 A。
