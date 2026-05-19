# TASK-plan-power-exact-bom-disambiguation Review Bundle - Final

## User follow-up
User emphasized: do not hardcode this issue; future business users may provide other explicit BOM order names/customer instances.

## Final hardcode-prevention changes
- Generic tests use fake customer names (`华东新能源-2027-12345`, `西南客户-2028-54321`) plus a fake-header resolver filter test.
- RED proved old extraction swallowed polite prefixes like `请问一下` / `麻烦看一下` into the hint.
- Implemented generic polite/query prefix cleanup with no customer-specific strings.
- Normalized `/`, `_`, and `-` separators for BOM-name hint matching.
- Removed concrete customer names from production service comments/docstrings; search over production service files now returns no hits for reported/test fake customer names.

## Verification
FAILED tests/business_acceptance/test_plan_power_real_business_qa_regression.py::test_exact_bom_name_disambiguates_same_review_number_candidates[NT10/78GDF(\u6c5f\u82cf\u6c49\u817e-2026-00106)Bill of materials\uff08GCL-XXJC-JSPS-2026-00106\uff0c\u7248\u672c A0\uff09\uff0c0.24+0.26\u710a\u5e26+\u9ad8\u900f\u73bb\u7483+\u95f4\u9699\u94dd\u819c+300/200\u7ebf\u957f\uff0c\u8ba1\u91cf\u9662\u57fa\u51c6\uff0c\u5355\u4e00\u9700\u6c42720\u529f\u7387\uff0c\u5404\u4e2a\u4f9b\u5e94\u5546\u5382\u5bb6\u4ece\u4ec0\u4e48\u7535\u6c60\u6548\u7387\u53ef\u4ee5\u6ee1\u8db3]
FAILED tests/business_acceptance/test_plan_power_real_business_qa_regression.py::test_exact_bom_name_disambiguates_same_review_number_candidates[NT10/78GDF(\u6c5f\u82cf\u6c49\u817e-2026-00106)\uff0c0.24+0.26\u710a\u5e26+\u9ad8\u900f\u73bb\u7483+\u95f4\u9699\u94dd\u819c+300/200\u7ebf\u957f\uff0c\u8ba1\u91cf\u9662\u57fa\u51c6\uff0c\u5355\u4e00\u9700\u6c42720\u529f\u7387\uff0c\u5404\u4e2a\u4f9b\u5e94\u5546\u5382\u5bb6\u4ece\u4ec0\u4e48\u7535\u6c60\u6548\u7387\u53ef\u4ee5\u6ee1\u8db3]
2 failed in 0.96s
FAILED tests/business_acceptance/test_plan_power_real_business_qa_regression.py::test_exact_bom_name_disambiguates_same_review_number_candidates[NT10/78GDF(\u6c5f\u82cf\u6c49\u817e-2026-00106)Bill of materials\uff08GCL-XXJC-JSPS-2026-00106\uff0c\u7248\u672c A0\uff09\uff0c0.24+0.26\u710a\u5e26+\u9ad8\u900f\u73bb\u7483+\u95f4\u9699\u94dd\u819c+300/200\u7ebf\u957f\uff0c\u8ba1\u91cf\u9662\u57fa\u51c6\uff0c\u5355\u4e00\u9700\u6c42720\u529f\u7387\uff0c\u5404\u4e2a\u4f9b\u5e94\u5546\u5382\u5bb6\u4ece\u4ec0\u4e48\u7535\u6c60\u6548\u7387\u53ef\u4ee5\u6ee1\u8db3]
FAILED tests/business_acceptance/test_plan_power_real_business_qa_regression.py::test_exact_bom_name_disambiguates_same_review_number_candidates[NT10/78GDF(\u6c5f\u82cf\u6c49\u817e-2026-00106)\uff0c0.24+0.26\u710a\u5e26+\u9ad8\u900f\u73bb\u7483+\u95f4\u9699\u94dd\u819c+300/200\u7ebf\u957f\uff0c\u8ba1\u91cf\u9662\u57fa\u51c6\uff0c\u5355\u4e00\u9700\u6c42720\u529f\u7387\uff0c\u5404\u4e2a\u4f9b\u5e94\u5546\u5382\u5bb6\u4ece\u4ec0\u4e48\u7535\u6c60\u6548\u7387\u53ef\u4ee5\u6ee1\u8db3]
2 failed in 1.27s
2 passed in 1.15s
12 passed in 1.27s
88 passed, 2 warnings in 23.30s
132 passed, 2 warnings in 27.47s
No credential/secret findings in added lines of focused task diff.
FAILED tests/business_acceptance/test_plan_power_real_business_qa_regression.py::test_exact_bom_name_disambiguates_same_review_number_candidates[\u6c5f\u82cf\u6c49\u817e-2026-00106\uff0c\u7248\u672c A0\uff0c0.24+0.26\u710a\u5e26+\u9ad8\u900f\u73bb\u7483+\u95f4\u9699\u94dd\u819c+300/200\u7ebf\u957f\uff0c\u8ba1\u91cf\u9662\u57fa\u51c6\uff0c\u5355\u4e00\u9700\u6c42720\u529f\u7387\uff0c\u5404\u4e2a\u4f9b\u5e94\u5546\u5382\u5bb6\u4ece\u4ec0\u4e48\u7535\u6c60\u6548\u7387\u53ef\u4ee5\u6ee1\u8db3]
1 failed, 2 passed in 1.35s
3 passed in 1.19s
13 passed in 1.62s
89 passed, 2 warnings in 18.19s
133 passed, 2 warnings in 25.03s
No credential/secret findings in added lines of focused task diff.
FAILED tests/business_acceptance/test_plan_power_real_business_qa_regression.py::test_order_name_hint_extraction_is_generic_not_case_hardcoded
1 failed in 1.73s
1 passed in 1.32s
14 passed in 1.51s
77 passed, 2 warnings in 15.59s
FAILED tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_remark_keyword_fee_ratio_is_supported_before_complex_report_guard
FAILED tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_remark_keyword_fee_ratio_without_record_delimiter_is_supported
2 failed, 132 passed, 2 warnings in 26.36s
No credential/secret findings in added lines of focused task diff.
## RED: broader generic no-hardcode guard for polite prefixes and fake headers
FAILED tests/business_acceptance/test_plan_power_real_business_qa_regression.py::test_order_name_hint_extraction_is_generic_not_case_hardcoded
1 failed, 1 passed in 1.05s
## GREEN: broader generic no-hardcode guard for polite prefixes and fake headers
2 passed in 1.12s
## focused real-business regression after final generic hardcode guards
15 passed in 1.34s
## related plan power acceptance after final generic hardcode guards
78 passed, 2 warnings in 17.61s
No credential/secret findings in added lines of focused task diff.
## final smoke after removing concrete customer examples from production comments
5 passed in 1.13s
Production code concrete-customer search:
hits= []

## Reviewer
Second addendum reviewer passed=true; only non-blocking suggestion was to replace concrete customer example in docstring, now done.

## Full test note
Full `pytest tests` after unrelated logistics dirty changes were isolated has 2 logistics remark-keyword failures unrelated to this Plan BOM addendum; focused/related Plan BOM tests pass. Earlier full tests passed while unrelated logistics dirty changes were present.
