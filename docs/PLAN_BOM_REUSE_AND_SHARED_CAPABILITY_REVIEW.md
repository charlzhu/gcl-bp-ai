# PLAN_BOM_REUSE_AND_SHARED_CAPABILITY_REVIEW

## 共用与复用结论

- LLM 配置共用：BOM 直接读取全局 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`；表达层模型优先 `LLM_ANSWER_PRESENTATION_MODEL`，否则兜底 `LLM_MODEL`。
- 上传解析复用：BOM 上传接口复用已有 `PlanBomExcelImportService`，没有另写 Excel parser。
- 查询主链路复用：自然语言 QA 最终调用已有 `PlanBomQueryService.detail()` 和 `compare()`。
- 数据模型复用：仍使用现有 `plan_bom_header / material_line / revision / import_batch`。
- 回归输出复用物流风格：JSON 放 `tmp/plan_bom/`，文档放 `docs/PLAN_BOM_*.md`。
- 输入源治理复用既有脚本报告风格：正式问题源为 `BOM问题.xlsx`，路径通过 `--question-file` 传入，报告记录实际路径、文件类型、sheet 和问题数量。

## 本轮没有强行抽公共代码的原因

- 物流表达层 schema 与 BOM 语义不同：物流包含图表、指标卡、费用/运量字段；BOM 主要是材料规格、版本和对比表。
- 物流 Guardrail 白名单绑定 query_key；BOM 必须绑定 intent、slot、订单索引和材料别名。
- 前端物流 data-qa 页面已进入试运行验收，抽公共 renderer 风险高于收益。

## 已复用但做领域适配的能力

- 表达层 fallback：BOM 也先构造确定性 `presentation`，LLM 失败或越权时降级。
- 防幻觉校验：BOM 校验 LLM 不得新增订单号、表格、物料或版本。
- B/C 边界：BOM 的 B/C 不能被 LLM 改成 A。
- NLU 模式：规则层先抽取订单、材料、版本、型号、国家、年份；LLM 只输出候选。

## 物流链路保护

本轮未修改物流 `data_qa_service`、`nlu_center_service`、`llm_answer_presentation_service`、Guardrail 配置、物流 query_key 或 903 总账。新增的 qwen-plus live NLU 和表达层验收只作用于 `plan_bom`，物流回归脚本已执行，结果见最终测试记录。
