# TASK-logistics-extra-fee-2026-01 最终验收

## 1. 问题结论

截图中的 2026 年 1 月额外费用答案确实错误。

- 错误答案：157,551.00 元；任务数 368；明细数 1015。
- 正确答案：143,013.00 元；贡献任务数 7；贡献产品明细数 7。

根因不是源库到 ODS/DWD 的发运产品额外费用同步缺失，而是 QA 仓储查询口径接错字段：

- 正确金额来源：`dwd_logistics_ship_product.extra_cost`，对应源系统 `logistic_ship_product.extra_cost`。
- 错误旧口径：`dwd_logistics_assign_detail.extra_cost`，该字段属于派车/分配明细侧费用，不能用于本题“额外费用产生多少钱”的金额来源。

因此本次修复将 `sys_extra_fee_summary` 从 `assign_detail.extra_cost` 改为 `ship_product.extra_cost`，并只统计 `extra_cost <> 0` 的贡献记录，避免 0 值/空值任务把记录数放大。

## 2. 分层核对证据

已按同一业务过滤条件（2026 年 1 月，优先 `pickup_date`，缺失时回退业务日期）逐层核对：

| 层级 | 表/字段 | 金额 | 任务数 | 明细数 | 结论 |
| --- | --- | ---: | ---: | ---: | --- |
| 源系统 | `logistic_ship_product.extra_cost` | 143,013.00 | 7 | 7 | 正确源头 |
| ODS | `ods_logistic_ship_product.extra_cost` | 143,013.00 | 7 | 7 | 同步正确 |
| DWD | `dwd_logistics_ship_product.extra_cost` | 143,013.00 | 7 | 7 | 中间表正确 |
| 旧 QA 误用 | `dwd_logistics_assign_detail.extra_cost` | 157,551.00 | 13 | 27 | 截图错误来源 |

详见：`ai/tasks/running/TASK-logistics-extra-fee-2026-01/data-audit.log`。

## 3. 修改文件

任务相关代码/测试变更：

1. `backend/app/domains/logistics/repositories/data_qa_repository.py`
   - `sys_extra_fee_summary()` 改为从 `dwd_logistics_ship_product.extra_cost` 汇总。
   - 统计贡献任务数和贡献产品明细数。
   - 月份过滤改为 SQLAlchemy expanding bind 参数，避免动态月份拼接。
   - 增补中文 docstring，说明参数、返回值和业务字段口径。
2. `backend/app/domains/logistics/services/data_qa_service.py`
   - 将答案计算口径和 `data_scope` 从 `dwd_logistics_assign_detail` 同步改为 `dwd_logistics_ship_product`。
3. `tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py`
   - 新增回归测试 `test_sys_extra_fee_summary_uses_ship_product_amount_source()`。
   - 锁定问法、planner 路由、金额 143,013.00 元、任务数 7、明细数 7。

验收材料：

- `ai/tasks/running/TASK-logistics-extra-fee-2026-01/diff.patch`
- `ai/tasks/running/TASK-logistics-extra-fee-2026-01/test.log`
- `ai/tasks/running/TASK-logistics-extra-fee-2026-01/data-audit.log`
- `ai/tasks/running/TASK-logistics-extra-fee-2026-01/review-result.json`
- `ai/tasks/running/TASK-logistics-extra-fee-2026-01/final-acceptance.md`

## 4. TDD 与验证

RED：

- 新增 focused test 后先运行失败。
- 失败原因：旧服务仍返回 `2026年1月额外费用总额为157,551.00元。`，而回归测试期望 `143,013.00元`。

GREEN / 回归：

```bash
backend/.venv/bin/python -m pytest tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_sys_extra_fee_summary_uses_ship_product_amount_source -q
# 1 passed

backend/.venv/bin/python -m pytest \
  tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py \
  tests/business_acceptance/test_logistics_system_sync_normalization.py \
  tests/business_acceptance/test_logistics_e2e_robustness_fixes.py \
  -q
# 39 passed

backend/.venv/bin/python -m compileall -q backend/app/domains/logistics
# pass

git diff --check -- backend/app/domains/logistics/repositories/data_qa_repository.py backend/app/domains/logistics/services/data_qa_service.py tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py
# pass
```

服务实测结果：

```text
2026年1月额外费用总额为143,013.00元。
[{'extra_fee_amount': Decimal('143013.00'), 'task_count': 7, 'detail_count': 7}]
```

详见：`ai/tasks/running/TASK-logistics-extra-fee-2026-01/test.log`。

## 5. 独立 Review

独立 reviewer 结论：通过。

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": [],
  "summary": "Scoped patch passes review: field source, SQL binding, focused regression coverage, and business display metadata are aligned with the corrected ship_product.extra_cost口径。"
}
```

## 6. 风险与边界

- 本次只修复“2026 年 1 月额外费用总额/记录数”的系统侧 QA 汇总口径，不实现项目/原因明细拆分。
- 当前系统仍保留原 warning：额外费用项目/原因明细口径尚未固化；本次先返回可审计的额外费用总额。
- 工作区存在较多与本任务无关的未提交/未跟踪文件，本次 review 和 `diff.patch` 已按任务范围限定到上述 3 个代码/测试文件。
- 未修改 BOM、计划 BOM 功率、前端、接口结构、数据库迁移、同步入库逻辑。

## 7. 是否影响现有能力

- 物流 QA：影响 `sys_extra_fee_summary` 的额外费用汇总口径，修复为正确金额来源。
- 历史物流 Excel QA：不影响。
- 计划 BOM / 功率模型：不影响。
- 前端：不影响接口结构；前端会继续渲染同一结果表字段，但数值修正为 143,013.00 / 7 / 7。

## 8. 下一步建议

1. 由用户确认后，可按任务范围提交：
   - `backend/app/domains/logistics/repositories/data_qa_repository.py`
   - `backend/app/domains/logistics/services/data_qa_service.py`
   - `tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py`
   - `ai/tasks/running/TASK-logistics-extra-fee-2026-01/*`
2. 若业务后续要回答“分别是什么项目/什么原因产生的”，需要先固化额外费用项目/原因字段来源或人工维护映射表，再新增明细查询能力。
