# 计划 BOM 资料补齐包清单

## 一、文档目的

本清单用于记录 `计划 BOM` 一期从资料缺口状态推进到开工前文档收口状态的资料齐套情况。

本次收口后，本文件不再用于证明 `plan_bom` 仍是 No-Go，而用于：

1. 说明资料包哪些内容已经补齐；
2. 指向当前权威文档；
3. 为后续规则变更和 SAP 切换提供资料归档入口。

---

## 二、本次收口替换的旧说法

| 旧说法 | 新说法 | 替换依据 |
| --- | --- | --- |
| 当前 plan_bom 为 No-Go，资料未到位 | BOM 一期完整范围建议正式 Go | 本轮业务规则、owner、问题答案、导出、数据源切换已收口 |
| 数据源说明待补 | Excel 开发期数据源和 SAP 后续优先源已成文 | `PLAN_BOM_SOURCE_SWITCH_RULE.md` |
| 字段字典待补 | 字段字典已整理为正式版 | `PLAN_BOM_FIELD_DICTIONARY_TEMPLATE.md` |
| 规则口径待补 | 规则口径已整理为正式版 | `PLAN_BOM_RULES_TEMPLATE.md` |
| 问题集和答案待补 | 问题集和标准答案来源已明确，5 条留空题已剔除 | `PLAN_BOM_QUESTION_SET_TEMPLATE.md` |
| 负责人待补 | owner 已落实 | `PLAN_BOM_OWNER_CONFIRMATION.md` |

---

## 三、资料补齐总览

| 分类 | 资料项 | 当前状态 | 权威文档 / 资料 | 负责人 |
| --- | --- | --- | --- | --- |
| 业务输入 | 域范围说明 | 已补齐 | `PLAN_BOM_RULES_TEMPLATE.md` | 刘娟 |
| 业务输入 | 规则口径说明 | 已补齐 | `PLAN_BOM_RULES_TEMPLATE.md` | 刘娟 |
| 业务输入 | 当前版本规则 | 已补齐 | `PLAN_BOM_RULES_TEMPLATE.md` | 刘娟 |
| 业务输入 | 替代料边界 | 已补齐 | `PLAN_BOM_RULES_TEMPLATE.md` | 刘娟 |
| 数据输入 | 数据源说明 | 已补齐 | `PLAN_BOM_SOURCE_SWITCH_RULE.md` | 刘娟 |
| 数据输入 | 字段字典 | 已补齐 | `PLAN_BOM_FIELD_DICTIONARY_TEMPLATE.md` | 刘娟 |
| 数据输入 | 样例数据 | 已提供 | `bom参考资料.zip` | 刘娟 |
| 测试输入 | 问题集 | 已补齐 | `PLAN_BOM_QUESTION_SET_TEMPLATE.md`、`BOM问题.xlsx` | 刘娟 |
| 测试输入 | 标准答案 | 已补齐 | `BOM问题_答案.xlsx` | 刘娟 |
| 测试输入 | 留空题边界 | 已补齐 | `PLAN_BOM_QUESTION_SET_TEMPLATE.md` | 刘娟 |
| 组织输入 | 业务确认人 | 已补齐 | `PLAN_BOM_OWNER_CONFIRMATION.md` | 刘娟 |
| 组织输入 | 数据确认人 | 已补齐 | `PLAN_BOM_OWNER_CONFIRMATION.md` | 刘娟 |
| 组织输入 | 文档归口人 | 已补齐 | `PLAN_BOM_OWNER_CONFIRMATION.md` | 刘娟 |
| 技术输入 | 技术对接人 | 已补齐 | `PLAN_BOM_OWNER_CONFIRMATION.md` | 朱长超 |
| 平台输入 | 数据源切换规则 | 已补齐 | `PLAN_BOM_SOURCE_SWITCH_RULE.md` | 刘娟 / 朱长超 |
| 平台输入 | 导出规范 | 已补齐 | `PLAN_BOM_EXPORT_SPEC.md` | 刘娟 / 朱长超 |

---

## 四、当前仍需后续工程细化但不阻塞 Go 的事项

| 事项 | 当前状态 | 后续处理 |
| --- | --- | --- |
| SAP 视图字段 | 权限和正式字段尚未下发 | SAP 接入前补字段映射 |
| 评审号候选列表交互 | 规则已定，工程协议未定 | 代码设计阶段定义返回上限、排序、展示字段 |
| 异步导出任务状态机 | 规则已定，接口未实现 | 代码设计阶段定义任务表、状态、文件路径 |
| 替代料展示方式 | 一期只原样展示 | 展示层可增加高亮或提示 |

---

## 五、当前结论

资料补齐维度当前结论：

> **已满足 BOM 一期完整范围正式 Go 的资料条件。**

说明：

- 该结论只代表一期完整范围可进入代码设计和最小实现；
- 不代表 SAP 正式接入已经完成；
- 不代表二期功率预测、电池配置能力已经纳入。
