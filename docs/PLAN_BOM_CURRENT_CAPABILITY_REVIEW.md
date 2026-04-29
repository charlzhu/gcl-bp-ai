# PLAN_BOM_CURRENT_CAPABILITY_REVIEW

## 当前已有 BOM 能力清单

- 后端领域目录已存在：`backend/app/domains/plan_bom/`。
- 已有数据库模型：`PlanBomImportBatch`、`PlanBomHeader`、`PlanBomMaterialLine`、`PlanBomRevision`、导出任务模型。
- 已有 Excel 导入服务：`PlanBomExcelImportService`，支持 `.xls/.xlsx/.xlsm` 解析、BOM 头、材料行、修订区、重复行和冲突识别。
- 已有仓储：`PlanBomImportRepository`、`PlanBomQueryRepository`。
- 已有查询服务：`PlanBomQueryService.detail()` 和 `PlanBomQueryService.compare()`。
- 已有 API：`/api/v1/plan-bom/import/excel`、`/api/v1/plan-bom/query/detail`、`/api/v1/plan-bom/query/compare`、`/api/v1/plan-bom/query/compare/replay/{log_id}`。
- 已有前端页面：`frontend/src/views/plan-bom/PlanBomDetailQueryPage.vue`。
- 已有测试：`backend/tests/test_plan_bom_excel_import.py`、`backend/tests/test_plan_bom_query_service.py`、`backend/tests/test_plan_bom_models.py`。
- 已有文档：`docs/PLAN_BOM_*` 系列一期设计、输入、字段、compare、导出和阶段总结文档。

## 已有能力判断

- BOM 文件上传能力：已有 `/api/v1/plan-bom/import/excel`，本轮新增验收口径更清晰的 `/api/v1/plan-bom/upload`，未废弃旧接口。
- BOM Excel 解析能力：已存在并可复用，本轮用真实 ZIP 全量验证。
- BOM 问答链路：已有结构化 detail/compare 查询；本轮新增自然语言 QA 编排，不重建查询引擎。
- BOM 前端页面：已有明细查询页；本轮补自然语言问答区和 Excel 上传入口。
- BOM 回归脚本：本轮前只有单元测试；本轮新增源数据治理、上传、NLU、问题回归、语义闭环、表达层和重点样例脚本。
- BOM 正式问题来源：本轮已纠正为 `BOM问题.xlsx`，读取 sheet `全部问题汇总`，有效问题 `129` 条；`BOM提问的问题.docx` 只作为兼容输入，不是正式回归源。
- BOM 脚本路径：`scripts/plan_bom_*.py` 已改为 `--source-zip` / `--question-file` 参数化，默认读取项目内 `data/plan_bom/` 或 `tmp/plan_bom/input/`，不再依赖本机 Desktop 绝对路径。

## 可复用物流能力

- LLM 配置读取：复用 `settings.llm_base_url / llm_api_key / llm_model / llm_answer_presentation_model`。
- 表达层边界：复用“确定性结果先生成，LLM 只做表达，校验失败 fallback”的设计。
- Guardrail 思路：复用不让 LLM 查数、改状态、改边界、改数值的原则，BOM 增加订单/物料/规格/版本防编造。
- NLU Center 模式：复用规则优先、LLM 候选辅助、白名单和审计说明思路。
- 回归报告：复用 `tmp/...json + docs/...md` 的报告风格。

## 不建议直接复用的能力

- 物流 query_key、指标、slot：语义完全不同，直接复用会污染 BOM。
- 物流 SQL 模板和 data-qa planner：物流面向运量/费用统计，BOM 面向订单版本和材料规格。
- 物流前端展示组件：当前字段耦合物流图表、费用和运量，BOM 先在本页适配，后续再抽通用 renderer。

## 本轮最小新增范围

- BOM NLU Center：`backend/app/domains/plan_bom/services/nlu_center_service.py`。
- BOM QA 主链路：`backend/app/domains/plan_bom/services/qa_service.py`。
- BOM 表达层适配：`backend/app/domains/plan_bom/services/answer_presentation_service.py`。
- BOM QA schema/API：`backend/app/domains/plan_bom/schemas/qa.py`、`api/endpoints/qa.py`。
- 上传验收接口：`/api/v1/plan-bom/upload`。
- 数据治理和回归脚本：`scripts/plan_bom_*.py`。
- 前端已有 BOM 页最小增强：上传入口和自然语言问答展示。
- API 级验收脚本：`scripts/plan_bom_upload_api_check.py`、`scripts/plan_bom_qa_api_e2e_check.py`，均使用 TestClient。
