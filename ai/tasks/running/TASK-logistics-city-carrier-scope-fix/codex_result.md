已完成修复，未 commit / push / deploy，未改 `main`、`.env`、前端或 DB 结构。

修改文件：
- [data_qa_planner.py](/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/backend/app/domains/logistics/services/data_qa_planner.py:653)：承运商 KPI 分支保留 `city`，新增承运商范围城市抽取，并让“发运多少量/多少量”这类口语 MW 问法命中承运商 KPI。
- [data_qa_service.py](/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/backend/app/domains/logistics/services/data_qa_service.py:1017)：`hist_carrier_kpi_by_year` 调用在有城市时透传 `city`，摘要显示如“常州城市”，不退化成单行总发运量。
- [data_qa_repository.py](/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/backend/app/domains/logistics/repositories/data_qa_repository.py:564)：`hist_carrier_kpi_by_year` 新增可选 `city` 参数，分母总量和承运商分组分子共用同一参数化过滤条件。

RED/GREEN：
- RED 复现：`PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_city_carrier_scope.py`，4 failed。
- GREEN：同命令，`4 passed in 0.28s`。
- 组合回归：`PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_region_business_answer.py tests/business_acceptance/test_logistics_city_carrier_scope.py`，`9 passed in 0.23s`。

风险点：城市抽取仍是规则型，已覆盖“常州的物流公司”“苏州的承运商”等同类表达，并避开省份/大区误下推；后续如果出现更长的地址式城市表达，可能还需要扩充受控抽取规则。

