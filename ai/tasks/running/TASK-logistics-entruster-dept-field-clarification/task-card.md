# TASK-logistics-entruster-dept-field-clarification

## 用户反馈

截图问题：`26年 经营计划 刘娟 用车总费用是多少`。

当前回答只按“经营计划用车锁定口径”返回总运费，丢失了 `刘娟` 这个人名条件，也没有明确把业务词映射到真实字段。

## 业务口径

1. `经营计划`：指物流 2026 系统任务字段 `扩充部门`（代码字段：`expand_dept`）里的数据。
2. `刘娟`：指物流 2026 系统任务字段 `委托人`（代码字段：`entrusted_person`）里的数据。
3. 当问题里出现不能确定归属字段的业务词、人名或口语化范围时，必须先反问补充字段口径，不能默认套用“锁定口径”或全量总费用。

## 验收标准

- `26年 经营计划 刘娟 用车总费用是多少` 应生成可执行 plan：
  - `query_key = sys_total_fee_by_filters`
  - `filters.expand_dept = 经营计划`
  - `filters.entrusted_person = 刘娟`
  - 不再使用 `special_scope=planning` 吞掉人名条件。
- `2026年经营计划用车总费用是多少` 应只按 `expand_dept` 过滤。
- `2026年刘娟用车总费用是多少` 应只按 `entrusted_person` 过滤。
- repository SQL 必须把 `expand_dept`、`entrusted_person` 下推到 `dwd_logistics_ship_task`，使用参数绑定。
- `26年 张三 用车总费用是多少` 等未知人名/范围，如果没有受控字段映射，必须返回 clarification。
- 不能 hardcode 单题答案；允许维护受控业务词典，但必须以字段映射形式表达。
- 不 commit / push / deploy。
