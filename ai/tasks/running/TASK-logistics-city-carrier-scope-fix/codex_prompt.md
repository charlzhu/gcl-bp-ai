你是本项目的 Codex 执行工程师。请只完成以下修复，不要 commit/push/deploy，不要修改 main，不要改 .env/密钥。

工作目录：/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai
当前任务：TASK-logistics-city-carrier-scope-fix

用户反馈：
- 问“2025年常州的物流公司发运多少量？”时，页面返回了“2025年总发运量 17374.913MW”。这是错误的：不能丢失“常州 + 物流公司/承运商”范围并退化为全国总量。

当前已完成 RED 测试：
- tests/business_acceptance/test_logistics_city_carrier_scope.py
- 运行：PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_city_carrier_scope.py
- 当前 4 个失败，分别覆盖 planner、service、repository。

请按 TDD 修复，要求：
1. 让“2025年常州的物流公司发运多少量？”命中 query_key=hist_carrier_kpi_by_year，dimensions/group_by 为 carrier_name，filters 包含 year=2025、city=常州。
2. 让“2025年苏州的承运商发货量分别是多少？”同样下推 city=苏州，不能 hardcode 常州。
3. _is_carrier_kpi_question 需要覆盖“发运多少量/多少量”等口语 MW 问法，但不要把非承运商题误判为承运商 KPI。
4. 服务层 hist_carrier_kpi_by_year 调用必须把 filters['city'] 透传给 repository，answer_summary 需要体现城市范围（如“常州城市”），且不要输出单行“总发运量”。
5. repository.hist_carrier_kpi_by_year 需要新增 city 可选参数，并把 city 过滤同时用于总量分母和承运商分组分子；继续使用 SQLAlchemy text + 参数绑定，不拼接用户输入。
6. 新增/修改代码保持中文注释，优先增量修改，不改前端、不改 DB 结构、不做大范围重构。

允许修改范围：
- backend/app/domains/logistics/services/data_qa_planner.py
- backend/app/domains/logistics/repositories/data_qa_repository.py
- backend/app/domains/logistics/services/data_qa_service.py
- tests/business_acceptance/test_logistics_city_carrier_scope.py（如测试本身有小问题可修）

完成后请运行：
- PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_city_carrier_scope.py
- PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_region_business_answer.py tests/business_acceptance/test_logistics_city_carrier_scope.py

请在输出中说明：修改了哪些文件、RED/GREEN 结果、是否存在风险。