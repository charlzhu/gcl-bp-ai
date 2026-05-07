# NEXT_TASK.md

## 下一步任务：计划 BOM 功率预测智能问答 M1 审计

当前正式进入“计划 BOM 功率预测智能问答 / 功率测试基准能力”任务。

本轮只执行 M1：

```text
功率预测 Excel 结构与公式审计 + 现有计划 BOM 链路梳理 + 后续实施方案设计
```

---

## 一、任务入口

请先读取：

1. `AGENTS.md`
2. `README_WORKSPACE.md`
3. `docs/CURRENT_STATUS.md`
4. `docs/NEXT_TASK.md`
5. `ai/protocols/company_task_protocol.md`
6. `ai/company/roles/technical_manager.md`
7. `ai/hermes_skills/company-code-builder/SKILL.md`
8. `ai/inbox/requirement.md`
9. `ai/inbox/attachments_manifest.md`
10. `ai/inbox/attachments/` 下的附件

附件包括：

```text
GCL功率测试基准（V2.1）26.03.26 (1).xlsm——副本.xlsm
BOM配置搭配问询：.docx
```

---

## 二、本轮目标

只完成以下工作：

1. 审计 `GCL功率测试基准` xlsm 的工作簿结构。
2. 识别所有 Sheet、版型、配置区、电池效率区、功率档位区、供应商效率分布区。
3. 审计 Excel 公式、数据验证、固定单元格依赖、VBA / 宏是否参与核心计算。
4. 梳理现有计划 BOM 域代码链路。
5. 判断功率预测能力应该如何接入现有 BOM / QA / 智能助手。
6. 输出 M2/M3/M4/M5 的后续实施方案。

---

## 三、本轮交付

只输出以下两个文档：

```text
docs/PLAN_POWER_EXCEL_FORMULA_AUDIT.md
docs/PLAN_POWER_IMPLEMENTATION_PLAN.md
```

---

## 四、本轮禁止事项

1. 不创建数据库迁移。
2. 不新增正式 ORM 模型。
3. 不新增正式接口。
4. 不修改前端。
5. 不接入 PlanBom QA。
6. 不实现正式功率预测计算引擎。
7. 不修改物流 / BOM 已有业务边界。
8. 不 hardcode 样例题。
9. 不把 `BOM配置搭配问询：.docx` 中的假订单、假版型、假项目名作为真实验收数据。
10. 不自动进入 M2/M3/M4/M5。

---

## 五、必须注意

`GCL功率测试基准` xlsm 是动态功率预测模型，不是普通静态表。

必须审计：

1. Sheet 结构。
2. 配置区。
3. 配置选项和功率影响值。
4. 电池效率区。
5. 功率档位分布区。
6. 供应商效率分布区。
7. 标板基准。
8. 公式依赖。
9. VBA / 宏是否参与核心计算。
10. 后端是否可以复现计算逻辑。
11. 如何做系统结果与 Excel 结果抽样校验。

`BOM配置搭配问询：.docx` 只用于理解题型和问法，其中数据为假数据。正式测试题必须基于真实 BOM 数据自行生成。

---

## 六、完成后报告要求

完成 M1 后必须输出：

1. 修改了哪些文件。
2. 读取了哪些附件。
3. 解析到哪些 Sheet 和版型。
4. 发现哪些核心公式和 VBA / 宏风险。
5. 后端需要复现哪些计算逻辑。
6. 哪些内容需要业务确认。
7. 与现有计划 BOM 链路如何结合。
8. 后续 M2/M3/M4/M5 怎么做。
9. 本轮是否影响现有 BOM / 物流能力。
10. 运行了哪些检查或测试。

完成 M1 后停止，等待确认。
