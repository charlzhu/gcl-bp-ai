# CURRENT_STATUS.md

## 当前阶段：计划 BOM 功率预测智能问答 M1 审计准备 / 执行阶段

当前已完成上一阶段“全量样例题真实网页 E2E”验收，`3281/3281` 真实网页 E2E 已完成，当前不再有待续跑 E2E 队列。

当前新的正式任务切换为：

```text
计划 BOM 功率预测智能问答 / 功率测试基准能力
```

该能力属于现有 **计划 BOM 业务域** 的子能力，不新建独立业务域。

---

## 一、当前任务定位

当前任务目标不是继续物流后端收口，不是 BOM Wave3，不迁 A，不扩 query_key，不做 mock demo。

当前目标是围绕《GCL功率测试基准》xlsm 文件，完成功率预测模型的结构审计、公式审计、VBA / 宏依赖判断，以及后续与现有计划 BOM 问答链路结合的实施方案设计。

最终能力目标：

```text
业务员在智能助手中自然语言提问
↓
系统识别订单 / 版型 / 配置 / 供应商 / 目标功率 / 目标比例
↓
如涉及订单，则查询现有 BOM 数据
↓
从 BOM 中抽取玻璃、间隙贴膜、焊带、汇流条、接线盒等配置
↓
映射到功率预测模型配置项
↓
调用后端确定性功率预测计算引擎
↓
返回供应商、效率段、功率档位分布、目标比例匹配度
```

---

## 二、当前执行阶段：M1

当前只执行 M1：

```text
功率预测 Excel 结构与公式审计 + 现有计划 BOM 链路梳理 + 后续实施方案设计
```

本阶段只允许输出文档：

```text
docs/PLAN_POWER_EXCEL_FORMULA_AUDIT.md
docs/PLAN_POWER_IMPLEMENTATION_PLAN.md
```

本阶段暂时不允许：

1. 不创建数据库迁移。
2. 不新增正式 ORM 模型。
3. 不新增正式接口。
4. 不修改前端。
5. 不接入 PlanBom QA。
6. 不实现正式功率预测计算引擎。
7. 不 hardcode 样例题。
8. 不把样例题中的假订单号 / 假版型 / 假项目名作为真实测试数据。

完成 M1 后必须停止并输出报告，等待确认后再进入 M2/M3/M4/M5。

---

## 三、当前任务输入

正式任务资料位于：

```text
ai/inbox/requirement.md
ai/inbox/attachments_manifest.md
ai/inbox/attachments/
```

附件包括：

```text
GCL功率测试基准（V2.1）26.03.26 (1).xlsm——副本.xlsm
BOM配置搭配问询：.docx
```

重要说明：

1. `GCL功率测试基准` xlsm 是动态功率预测模型，不是普通静态数据表。
2. `BOM配置搭配问询：.docx` 只作为题型和问法参考。
3. `BOM配置搭配问询：.docx` 中的版型号、订单号、评审号、项目名均为假数据。
4. 不允许 hardcode 样例题答案。
5. 后续正式测试必须基于当前项目真实 BOM 数据自行生成可验证测试题。

---

## 四、上一阶段已完成基线

### 真实网页 E2E 最终结果

- 真实网页入口：`/smart-chat`
- 执行方式：Playwright 打开真实前端页面，输入问题，从 DOM 抓取最终展示答案。
- 当前执行状态：`completed`
- 停止条件：`all_cases_completed`
- 计划执行：`3281`
- 已执行真实网页 E2E：`3281`
- 待执行：`0`
- 前端执行状态：`pass=3281`
- 自动比对结果：`PASS=3281 / FAIL=0`
- B 类正确追问：`1429/1429`
- C 类正确拒答解释：`93/93`
- `failed_cases.json`：空列表。

### 当前能力基线

- 物流：`A=656 / B=178 / C=69 / D=0`
- BOM：`A=86 / B=40 / C=3 / D=0`
- 前端：`npm run build --prefix frontend` 通过。
- 物流 NLU：`122/122`。
- 物流 903 语义回归：`1559/1559`。
- BOM QA API E2E：`30/30`。
- BOM 多问法语义回归：`129/129`。
- 物流 Guardrail bounded check：`10/10`。
- 发布前 readiness check：通过。

---

## 五、计划 BOM 当前基础状态

现有计划 BOM 能力和表结构需要复用。

重点表：

```text
plan_bom_header
plan_bom_material_line
plan_bom_revision
plan_bom_import_batch
plan_bom_export_task
plan_bom_export_file
```

重点接口：

```text
POST /api/v1/plan-bom/upload
POST /api/v1/plan-bom/qa/ask
```

当前功率预测后续必须与现有 BOM 链路结合：

```text
BOM 查询：订单 / 评审号 / 订单名称 → 核心材料配置
功率预测：版型 + 配置 + 供应商效率分布 → 功率档位分布
智能问答：自然语言问题 → BOM 查询 / 功率预测 / 推荐解释
```

---

## 六、当前边界

1. 没有 mock 数据。
2. 没有 hardcode 样例题答案。
3. 不绕过真实业务主链路。
4. 当前 M1 不修改业务主链路。
5. 当前 M1 不修改物流 / BOM A/B/C 边界。
6. 当前 M1 不新增数据库结构。
7. 当前 M1 不新增前端页面。
8. 当前 M1 完成后必须等待确认，不自动进入 M2。
