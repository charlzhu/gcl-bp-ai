你是 Codex 工程执行师，工作目录为 /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai。请修复物流问答业务反馈，禁止 commit/push/deploy，禁止修改 .env/密钥/账号/token。

## 用户反馈
截图问题：`26年 经营计划 刘娟 用车总费用是多少`。
当前系统回答成“2026年经营计划用车按锁定口径统计的总运费...”，只套用了经营计划特殊口径，丢失了“刘娟”。

## 正确业务口径
1. `经营计划` 指字段 `扩充部门`，代码字段为 `expand_dept`。
2. `刘娟` 指字段 `委托人`，代码字段为 `entrusted_person`。
3. 两个条件同时出现时必须叠加过滤：`expand_dept=经营计划 AND entrusted_person=刘娟`。
4. 如果业务词/人名没有受控字段映射，例如 `26年 张三 用车总费用是多少`，必须先返回 clarification 让用户补充字段口径，不能默认查全量、不能套用不相关特殊口径。
5. 修复必须增强通用字段过滤能力，不能只 hardcode 当前单题答案。

## 已新增 RED 测试
`tests/business_acceptance/test_logistics_field_scope_clarification.py`
当前命令：
`PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_field_scope_clarification.py --tb=short`
失败点：
- planner 现在返回 `sys_special_total_fee + special_scope=planning`，应改为 `sys_total_fee_by_filters + expand_dept/entrusted_person`。
- unknown scope clarification 缺少 `clarification_category=field_scope_mapping`。
- repository `sys_total_fee_by_filters` 不支持 `expand_dept`、`entrusted_person` 参数。
- service 还会调用 `sys_special_total_fee`。

## 修改范围
允许修改：
- `backend/app/domains/logistics/services/data_qa_planner.py`
- `backend/app/domains/logistics/services/data_qa_service.py`
- `backend/app/domains/logistics/repositories/data_qa_repository.py`
- 必要时小范围更新新增测试文件。

不要修改 unrelated 前端/Plan BOM/历史旧任务文件。

## 实现要求
1. 在 planner 中优先识别 2026 系统总费用问题中的受控字段过滤：
   - `经营计划` / `经营计划部` -> `expand_dept`
   - `刘娟` -> `entrusted_person`
   - 单独出现或组合出现都返回 `sys_total_fee_by_filters`，并把字段写入 filters。
2. 不再用 `special_scope=planning` 吞掉 `entrusted_person`。
3. unknown scope/person 用 clarification：
   - `intent=clarification`
   - `needs_clarification=True`
   - `clarification_category='field_scope_mapping'`
   - reason/questions 说明需要用户确认该词对应哪个字段，例如扩充部门、委托人、客户、承运商等。
4. repository `sys_total_fee_by_filters` 增加参数：
   - `expand_dept: str | None = None`
   - `entrusted_person: str | None = None`
   并用 SQL 参数绑定下推：
   - `st.expand_dept = :expand_dept`
   - `st.entrusted_person = :entrusted_person`
5. service 调用 repository 时透传这两个参数；summary scope_parts 明确展示 `扩充部门=...`、`委托人=...`；calculation_logic 增加字段过滤说明。
6. 保留已有 `special_scope` 兼容，不要大范围删除旧能力；但本用户反馈场景必须走字段过滤。
7. 新增/修改代码要写中文注释说明业务口径、参数、返回值或复杂判断原因。

## 验证命令
完成后至少运行：
`PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_field_scope_clarification.py --tb=short`
如果时间允许再运行：
`PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py tests/business_acceptance/test_logistics_system_sync_normalization.py --tb=short`

请把执行摘要写到：
`ai/tasks/running/TASK-logistics-entruster-dept-field-clarification/codex_result.md`
