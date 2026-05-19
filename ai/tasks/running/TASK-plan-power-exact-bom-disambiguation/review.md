# TASK-plan-power-exact-bom-disambiguation 代码审查记录

## Reviewer 结论

```text
passed=true
阻塞问题：无
```

## 审查范围

- `backend/app/domains/plan_bom/services/nlu_center_service.py`
- `backend/app/domains/plan_bom/services/power_config_resolver_service.py`
- `backend/app/domains/plan_bom/services/qa_service.py`
- `tests/business_acceptance/test_plan_power_real_business_qa_regression.py`
- `ai/tasks/running/TASK-plan-power-exact-bom-disambiguation/test.log`
- `ai/tasks/running/TASK-plan-power-exact-bom-disambiguation/diff.patch`
- `ai/tasks/running/TASK-plan-power-exact-bom-disambiguation/review_bundle.md`

## 重点结论

1. 完整 BOM 文件名 / 客户实例 / 版本消歧通过：截图原文不再返回两个 BOM 候选，不再混入“石家庄科林”。
2. 独立 `客户-年份-尾号` 覆盖通过：`江苏汉腾-2026-00106，版本 A0...` 可抽取 `order_name_hint=江苏汉腾-2026-00106` 并命中江苏汉腾实例。
3. 非匹配项目前缀仍保持 fail-closed：`创维210N—00106...` 继续返回 `candidate_required`、候选数 2，并提示项目名未匹配候选。
4. LLM 未参与 BOM 事实判断或功率计算；M4 仍为确定性 DB / active 模型映射，M3 仍负责数值计算。
5. 未发现新增 secret / token / credential 风险。

## Reviewer 独立验证

```text
PYTHONPATH=. pytest -q tests/business_acceptance/test_plan_power_real_business_qa_regression.py
13 passed
```

Reviewer 还手工验证：

- 截图原文：`candidate_count=0`，不含“命中 2 个 BOM 候选”，不含“石家庄科林”。
- 独立客户实例：`江苏汉腾-2026-00106` 可消歧。
- 非匹配项目前缀：`创维210N—00106` 仍返回两个候选和 mismatch 提示。

## 非阻塞建议

1. 后续可增强 `order_name_hint` 边界处理，例如 `请问江苏汉腾-2026-00106` 这类前置口语可能需要进一步裁剪。
2. 后续可增强 `/` 与 `-` 混写归一化。
3. 后续可增加 resolver 层单元测试，直接验证 hint 未命中时不会错误缩窄候选。
