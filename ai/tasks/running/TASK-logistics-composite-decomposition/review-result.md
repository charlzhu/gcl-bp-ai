# TASK-logistics-composite-decomposition Review Result

## 最终结论

通过。

## 独立 reviewer 结论摘要

- 阻塞问题列表：无。
- 复合正例会进入 `composite_decomposed`，拆为：
  - `hist_high_fee_addresses_by_customer`
  - `sys_mw_by_procurement_type`
- 以下回指前一高运费地址结果的变体均不会误拆成 2026 全局采购方式，均返回 `UNSUPPORTED_QUESTION / unsupported / query_key=None`：
  - 这些地址
  - 上述的地址
  - 这些高运费地址
  - 上述高运费项目地
  - 上面的地址
  - 这些运费超过20万的地址
- 显式“吨”口径在复合拆分前被拦截，返回 `CLARIFICATION_REQUIRED`，不会用 MW 口径替代。
- 历史高运费地址内部按询比价/招标拆分仍保持不支持边界，未发现绕过历史采购方式缺字段保护的问题。
- 服务层合并结果只执行受控子计划，不做跨源二次推理，并通过 warning 明确历史台账与 2026 系统侧采购方式不混算。

## reviewer 执行验证

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -p no:cacheprovider tests/business_acceptance/test_business_feedback_excel_qa_regression.py -q -k "reference_to_previous_high_fee_addresses or composite or non_decomposable or explicit_ton_unit"
# 10 passed, 14 deselected

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -p no:cacheprovider tests/business_acceptance/test_business_feedback_excel_qa_regression.py -q
# 24 passed
```

## 非阻塞建议

1. 后续可继续补充更多回指同义词测试，例如“前面提到的地址”“上述项目所在地”“这些收货地”等，避免未来同类表达漏网。
2. 如后续扩展更多复合类型，继续采用白名单子计划方式，不要泛化为自由拆句执行。
3. 默认把采购方式子句未写年份解释为 2026 系统侧口径时，产品文案层需保持 caveat 可见，避免用户误解为历史地址内部拆分。
