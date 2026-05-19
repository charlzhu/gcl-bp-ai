# Final Acceptance: TASK-logistics-entruster-dept-field-clarification

## 结论

通过。已修复物流问答中 `经营计划` / `刘娟` 字段口径误判问题，并完成最终交付验证。

## 用户问题

`26年 经营计划 刘娟 用车总费用是多少`

## 修复后的业务行为

- `经营计划` 映射为系统字段 `扩充部门`，代码过滤键：`expand_dept=经营计划`。
- `刘娟` 映射为系统字段 `委托人`，代码过滤键：`entrusted_person=刘娟`。
- 两个条件可叠加执行 `sys_total_fee_by_filters`，不再退化为旧 `sys_special_total_fee` 锁定口径。
- 未知业务词 / 人名（如 `张三`）不再默认查全量或套不相关字段，而是返回 `CLARIFICATION_REQUIRED`，要求确认字段口径。

## 根因

旧逻辑把 `经营计划`、`刘娟` 当作 2026 系统总费用的 special_scope 触发词；当同一问题同时包含业务词和人名时，planner 优先进入单一锁定口径，导致条件丢失，答案口径错误。

## 主要修改

- `backend/app/domains/logistics/services/data_qa_planner.py`
  - 增加受控字段别名映射；
  - 增加未知字段口径澄清；
  - 让受控字段过滤优先于旧 special_scope。
- `backend/app/domains/logistics/services/data_qa_service.py`
  - 下传 `expand_dept` / `entrusted_person`；
  - 答案和计算逻辑中明确字段口径。
- `backend/app/domains/logistics/repositories/data_qa_repository.py`
  - `sys_total_fee_by_filters` 增加 `expand_dept` / `entrusted_person` 参数化 SQL 过滤。
- `tests/business_acceptance/test_logistics_field_scope_clarification.py`
  - 新增 focused 回归，覆盖 planner/service/repository/API/clarification。
- `ai/tasks/running/TASK-logistics-entruster-dept-field-clarification/`
  - 新增任务卡、API smoke、浏览器 smoke 后端和交付材料。

## 验证结果

- Focused 回归：`6 passed`
- Logistics acceptance：`49 passed`
- Full business_acceptance：`155 passed, 2 warnings`
- 此前 6 个失败专项复查：`8 passed`，不需要继续修复
- API smoke：通过
- Browser smoke：通过，页面展示 `扩充部门=经营计划` + `委托人=刘娟`，无 JS error
- compileall：通过
- frontend build：通过
- Independent review：`passed=true`

## 对此前 6 个 business_acceptance 失败的判断

此前失败集中在前端/Plan BOM presentation 的 `table_spec` 断言，不属于本次物流字段口径链路。复查后相关 8 个 case 已全部通过；全量 `tests/business_acceptance` 也通过，因此本轮无需针对这 6 个失败继续修复。

## 风险与后续建议

- 当前受控映射只包含业务已确认的 `经营计划/经营计划部` 和 `刘娟`；后续新增人名/业务词时应继续通过配置化或受控词典扩展，不能开放猜测。
- 独立 review 建议后续增加“用户显式说客户/承运商/项目字段”的正反例，防止未知字段澄清过度。
- 当前答案文案 `扩充部门=经营计划委托人=刘娟` 可读性可后续加分隔符优化，不影响业务正确性。

## 人工处理

- 未 commit / push / deploy。
- 工作区仍存在多个历史任务残留 modified/untracked 文件；提交时必须 scoped staging，禁止 `git add -A`。
