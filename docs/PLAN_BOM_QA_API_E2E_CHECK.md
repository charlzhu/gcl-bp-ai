# PLAN_BOM_QA_API_E2E_CHECK

## 接口地址

- `POST /api/v1/plan-bom/qa/ask`

## 验收方式

- 使用 `scripts/plan_bom_qa_api_e2e_check.py`。
- 使用 FastAPI `TestClient` 发起真实 HTTP 请求。
- 测试库先导入真实 `BOM 源数据.zip` 中的 Excel，不使用 mock 数据。
- QA API 仍走已有 `PlanBomExcelImportService`、`PlanBomQueryService`、`PlanBomQaService`、`PlanBomNluCenterService` 和答案表达层。

## 覆盖结果

- 本轮扩容用例：`30` 条。
- 通过：`30`
- 失败：`0`
- 路由注册：`True`
- A 类单订单查询：通过。
- A 类范围清单：通过。
- A 类物料存在性检查：通过。
- B 类自然追问：通过。
- B 类多订单歧义：通过。
- C 类功率倒推拒答解释：通过。
- 空结果：通过。
- presentation 字段：通过。
- 非核心材料安全降级：通过，`cell / eva_film` 不再进入核心五类 Pydantic schema，不会触发 500。

## 报告

- JSON：`tmp/plan_bom/plan_bom_qa_api_e2e_check_report.json`
- 本轮结果：`30/30` 通过。
