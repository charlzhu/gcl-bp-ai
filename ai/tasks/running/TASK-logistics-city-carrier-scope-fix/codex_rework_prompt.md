你是本项目 Codex 执行工程师。上一轮修复后，我作为技术经理独立审查发现一个阻塞逻辑回归风险，请只做定向返工，不要 commit/push/deploy。

问题：
- 新增 `_extract_carrier_scope_city` 会把“2025年各物流公司发运量是多少？”误抽成 `city=各`。
- 这会把本应全局按物流公司分组的问题过滤到 city='各'，属于阻塞逻辑错误。

我已新增 RED 测试：
- `test_all_logistics_companies_question_does_not_fake_city_scope`
- 当前运行：`PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_city_carrier_scope.py -q`
- 失败点：`assert plan.filters.get("city") is None`，实际为 `'各'`。

请只修改必要代码，要求：
1. “各物流公司 / 不同物流公司 / 各承运商 / 各家物流”等全局承运商分组问法不能抽 city。
2. “常州的物流公司 / 常州物流公司 / 苏州的承运商”仍然抽 city。
3. 保持通用逻辑，不 hardcode 常州或苏州。
4. 保持中文注释。

完成后运行：
- `PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_city_carrier_scope.py`
- `PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_region_business_answer.py tests/business_acceptance/test_logistics_city_carrier_scope.py`

只输出修改摘要和测试结果。