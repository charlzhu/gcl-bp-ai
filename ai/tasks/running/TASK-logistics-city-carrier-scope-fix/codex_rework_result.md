修改摘要：
- 仅修改 `backend/app/domains/logistics/services/data_qa_planner.py` 的 `_extract_carrier_scope_city`。
- 增加“各/不同/各家/每家/全部/所有 + 物流公司/承运商”全局承运商分组保护，避免误抽 `city=各`。
- 保留“常州的物流公司 / 常州物流公司 / 苏州的承运商”这类城市 + 承运商问法的通用抽取逻辑。
- 未 commit / push / deploy。

测试结果：
- `PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_city_carrier_scope.py`
  - `5 passed in 0.24s`
- `PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_region_business_answer.py tests/business_acceptance/test_logistics_city_carrier_scope.py`
  - `10 passed in 0.28s`

