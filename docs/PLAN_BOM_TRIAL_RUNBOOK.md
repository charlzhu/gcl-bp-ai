# PLAN_BOM_TRIAL_RUNBOOK

## 后端启动

```bash
cd <repo-root>
PYTHONPATH=. uvicorn backend.app.main:create_application --factory --reload
```

## 前端启动

```bash
cd <repo-root>/frontend
npm install
npm run dev
```

## 必要环境变量

- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL=qwen-plus`
- `LLM_ANSWER_PRESENTATION_ENABLED=true`
- `LLM_ANSWER_PRESENTATION_MODEL` 可选；未配置时按当前策略使用通用 `LLM_MODEL`。

不要把真实 API Key 写入代码、文档或报告。

## 接口

- 上传接口：`POST /api/v1/plan-bom/upload`
- 兼容上传接口：`POST /api/v1/plan-bom/import/excel`
- QA 接口：`POST /api/v1/plan-bom/qa/ask`

## 常用回归命令

```bash
PYTHONPATH=. python scripts/plan_bom_upload_api_check.py --source-zip 'tmp/plan_bom/input/BOM 源数据.zip'
PYTHONPATH=. python scripts/plan_bom_qa_api_e2e_check.py --source-zip 'tmp/plan_bom/input/BOM 源数据.zip'
PYTHONPATH=. python scripts/plan_bom_nlu_eval.py --question-file 'tmp/plan_bom/input/BOM问题.xlsx'
PYTHONPATH=. python scripts/plan_bom_b_clarification_regression.py
PYTHONPATH=. python scripts/plan_bom_a_precise_batch1.py
PYTHONPATH=. python scripts/plan_bom_question_regression.py --question-file 'tmp/plan_bom/input/BOM问题.xlsx'
PYTHONPATH=. python scripts/plan_bom_semantic_closure_eval.py --question-file 'tmp/plan_bom/input/BOM问题.xlsx'
PYTHONPATH=. python scripts/plan_bom_answer_presentation_regression.py --question-file 'tmp/plan_bom/input/BOM问题.xlsx'
PYTHONPATH=. python scripts/plan_bom_answer_presentation_live_eval.py --limit 30
PYTHONPATH=. python scripts/plan_bom_key_acceptance.py
PYTHONPATH=. pytest backend/tests/test_plan_bom_models.py backend/tests/test_plan_bom_excel_import.py backend/tests/test_plan_bom_query_service.py
npm run build --prefix frontend
```

## 上传失败排查

- 检查文件是否为 `.xls/.xlsx/.xlsm`。
- 检查是否为空文件或超过 20MB。
- 检查 `business_type` 是否为 `plan_bom`。
- 查看返回的 `data_quality_summary`、`warnings`、`errors` 和 `report_path`。

## 问答失败排查

- 检查问题中是否包含订单、版本或材料范围。
- B 类先按追问补槽，不要直接判定为系统错误。
- C 类查看拒答原因，确认是否超出当前 BOM 数据和业务规则。
- 非核心材料当前不进入核心五类查询。

## LLM fallback 排查

- 检查 `LLM_BASE_URL / LLM_API_KEY / LLM_MODEL` 是否配置。
- 查看 NLU 和答案表达层报告中的 fallback 原因。
- LLM fallback 不影响确定性查询事实。

## 前端异常排查

- 检查浏览器 network 中 `/api/v1/plan-bom/upload` 和 `/api/v1/plan-bom/qa/ask` 返回。
- A 类应展示答案和表格。
- B 类应展示追问，不应当作错误。
- C 类应展示拒答解释，不应当作系统故障。
