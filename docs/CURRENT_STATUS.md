# CURRENT_STATUS.md

## 当前阶段：计划 BOM 功率预测智能问答 M1.5 已完成，等待进入 M2 确认

当前正式任务：

```text
计划 BOM 功率预测智能问答 / 功率测试基准能力
```

该能力属于现有 **计划 BOM 业务域** 的子能力，不新建独立业务域。

---

## 一、当前完成状态

### 1. M1 已完成

M1 已完成以下工作：

1. 审计旧版 `GCL功率测试基准（V2.1）26.03.26 (1).xlsm——副本.xlsm`。
2. 梳理计划 BOM 现有导入、查询、QA、智能助手链路。
3. 输出：
   - `docs/PLAN_POWER_EXCEL_FORMULA_AUDIT.md`
   - `docs/PLAN_POWER_IMPLEMENTATION_PLAN.md`

M1 未修改后端业务代码、未新增接口、未新增迁移、未修改前端、未接入 PlanBom QA、未实现正式计算引擎。

### 2. M1.5 已完成

M1.5 已完成：

1. 固化业务口径。
2. 补充审计新版 Excel：
   - `ai/inbox/attachments/GCL功率测试基准（V2.1）TOPCon 26.04.13.xlsm`
3. 判断 M2 开发准入。
4. 新增 / 更新文档：
   - `docs/PLAN_POWER_BUSINESS_CONFIRMATION.md`
   - `docs/PLAN_POWER_EXCEL_FORMULA_AUDIT.md`
   - `docs/PLAN_POWER_IMPLEMENTATION_PLAN.md`
   - `docs/CURRENT_STATUS.md`
   - `docs/NEXT_TASK.md`
   - `ai/inbox/attachments_manifest.md`

M1.5 仍未创建数据库迁移、未新增正式接口、未实现正式计算引擎、未接入 PlanBom QA、未修改前端、未 hardcode 样例题。

---

## 二、当前主分析文件

后续 M2/M3/M4/M5 默认以新版 TOPCon 文件作为目标：

```text
ai/inbox/attachments/GCL功率测试基准（V2.1）TOPCon 26.04.13.xlsm
```

旧版 Excel 仅作为历史审计参考。

新版文件补充审计结论：

1. Sheet 数量未变：仍为 12 个 Sheet。
2. 版型模型页未变：仍为 10 个版型模型页。
3. 配置区位置未变：`A1:Y27`。
4. 功率档位区未变：10 档版型为 `K28:T28`，48/54 系列有效 8 档。
5. 供应商效率分布区未变：`C77:Y96`。
6. 公式结构未发生阻塞性变化：仍以 `NORMSDIST`、`SUM`、固定行列引用和 VBA 写值为核心。
7. `标板基准` 页从 `A1:D10` 变为 `A1:E10`，新增 `功率最优` 列。
8. `更改履历` 更新到 2026.04.13。
9. `R30:R34` 疑似问题未完全消失，新版仍发现 `NT12R-66GDF!R30/R32` 需要语义修正。

---

## 三、已固化业务口径

详见：`docs/PLAN_POWER_BUSINESS_CONFIRMATION.md`。

### 1. 公式策略

```text
formula_policy = semantic_fixed_mode
```

含义：后端计算引擎不完全按 Excel 原疑似错误公式照搬，而是按公式语义修正 `R30:R34` 的疑似复制错误。

### 2. BOM 映射口径

| BOM / 用户问法 | 功率模型标准项 | 默认归一结果 |
|---|---|---|
| 间隙贴膜 | 玻璃选型 | 间隙铝膜 |
| 接线盒 300/200 | 线缆长度 | +300/-200mm |
| 北德 / 新北德 / TÜV北德 | 标板基准 | 新北德 |
| 计量院 | 标板基准 | 中国计量院 |
| 莱茵 | 标板基准 | 莱茵基准 |
| NT12/66GDF | 版型 | NT12-66GDF |
| NT12R/66GDF | 版型 | NT12R-66GDF |

---

## 四、M2 准入判断

建议可以进入 M2：功率模型版本化入库。

准入依据：

1. 新版 Excel 核心结构可解析。
2. Sheet / 配置区 / 功率档位区 / 供应商效率分布区可稳定定位。
3. `formula_policy = semantic_fixed_mode` 已固化。
4. BOM 映射口径已固化。
5. M2 表结构和解析器设计不需要大改。
6. 未发现新的宏 / 公式阻塞项。

M2 范围限制：只做模型版本化入库和解析校验；不要实现正式计算引擎，不接入 QA，不修改前端。

---

## 五、现有能力基线

上一阶段“全量样例题真实网页 E2E”验收已完成：

- 真实网页 E2E：`3281/3281`
- 自动比对：`PASS=3281 / FAIL=0`
- B 类正确追问：`1429/1429`
- C 类正确拒答解释：`93/93`

当前能力基线：

- 物流：`A=656 / B=178 / C=69 / D=0`
- BOM：`A=86 / B=40 / C=3 / D=0`
- BOM QA API E2E：`30/30`
- BOM 多问法语义回归：`129/129`

M1/M1.5 文档工作不应改变上述能力边界。

---

## 六、当前边界

1. 没有 mock 数据。
2. 没有 hardcode 样例题答案。
3. 不绕过真实业务主链路。
4. M1/M1.5 不修改业务主链路。
5. M1/M1.5 不新增数据库结构。
6. M1/M1.5 不新增前端页面。
7. `BOM配置搭配问询：.docx` 只作为题型和问法参考，其中数据为假数据。
8. 后续正式测试必须基于真实 BOM 数据和 active 功率模型自行生成可验证测试题。
