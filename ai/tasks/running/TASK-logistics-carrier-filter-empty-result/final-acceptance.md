# TASK-logistics-carrier-filter-empty-result 最终验收报告

## 1. 问题结论

用户问题：

> 24 年 京东物流 在各区域的承运量分别是多少

原错误表现：系统返回了 2024 年所有承运商的各区域汇总，未按“京东物流”过滤。

根因：

- `hist_mw_by_all_regions` 查询分支本身已经支持 `filters.carrier_name` 下推；
- 但 `LogisticsDataQaPlanner._extract_historical_carrier_name()` 只识别 `晶茂`、`英赋嘉`，没有识别“京东物流”；
- 因此 planner 输出 `filters={'year': 2024}`，repository 按全承运商统计，最终前端展示总数据。

## 2. 修复方案

本次采用最小修复，不泛化所有“物流”短语：

1. 在历史承运商窄白名单中加入：
   - `京东物流 -> 京东`
   - `京东 -> 京东`
2. 保留原有 `晶茂`、`英赋嘉` 支持。
3. 服务层 `hist_mw_by_all_regions` 分支新增安全提示：
   - 如果用户明确指定了承运商；
   - 且该承运商过滤后无数据；
   - 返回空表和“未找到承运商……”提示；
   - 明确说明“未返回全承运商汇总”。
4. 新增回归测试防止：
   - 显式承运商过滤丢失；
   - 承运商无数据时回退全量；
   - “历史物流”等泛词被误抽为承运商。

## 3. 修改文件

本任务相关修改：

- `backend/app/domains/logistics/services/data_qa_planner.py`
  - `_extract_historical_carrier_name()` 增加京东物流窄白名单。
- `backend/app/domains/logistics/services/data_qa_service.py`
  - `hist_mw_by_all_regions` 分支增加“指定承运商 + 空结果”提示逻辑。
- `tests/business_acceptance/test_logistics_carrier_filter_scope.py`
  - 新增 3 条回归测试。
- `ai/tasks/running/TASK-logistics-carrier-filter-empty-result/diff.patch`
- `ai/tasks/running/TASK-logistics-carrier-filter-empty-result/test.log`
- `ai/tasks/running/TASK-logistics-carrier-filter-empty-result/final-acceptance.md`

## 4. RED / GREEN

RED：

- 新增测试在修复前失败：
  - planner `filters` 缺失 `carrier_name`；
  - service 观察到下推承运商为 `None`。

GREEN：

- 修复后新增测试通过：`3 passed`。

## 5. 验证结果

已通过：

- `backend/.venv/bin/python -m pytest tests/business_acceptance/test_logistics_carrier_filter_scope.py -q`
  - `3 passed`
- `backend/.venv/bin/python -m pytest tests/business_acceptance/test_logistics_*.py -q`
  - `73 passed`
- `backend/.venv/bin/python -m pytest $(git ls-files 'tests/**/*.py') tests/business_acceptance/test_logistics_carrier_filter_scope.py -q`
  - `184 passed, 2 warnings`
- `backend/.venv/bin/python -m compileall -q backend/app tests/business_acceptance/test_logistics_carrier_filter_scope.py`
  - 通过
- `git diff --check`
  - 通过
- 真实 DB 手工验证：
  - `query_key = hist_mw_by_all_regions`
  - `filters = {'year': 2024, 'carrier_name': '京东'}`
  - `rows = 0`
  - `status.code = EMPTY_RESULT`
  - 摘要：`2024年未找到承运商“京东”在各区域的发运量记录，未返回全承运商汇总。`

## 6. Review 结论

独立 reviewer：PASS。

无阻塞问题。

Reviewer 的非阻塞建议已处理：

- 增加“历史物流”泛词不误抽承运商负例；
- 增加空结果 warnings / EMPTY_RESULT 状态断言。

## 7. 已知环境事项

当前工作区在本任务开始前已有大量其它任务的 modified / untracked 文件。为避免混入无关变更，本报告和 `diff.patch` 只列本任务相关文件。

补充说明：当前直接运行 `backend/.venv/bin/python -m pytest tests -q` 会收集其它 untracked 测试，其中 `tests/business_acceptance/test_plan_bom_qa_multi_candidate_compare.py` 目前失败（`classification B != A`），这是 Plan BOM untracked 测试，与本次物流承运商过滤修复无关。针对本任务，已额外运行“git 已跟踪 tests + 本任务新增测试”，结果通过。

## 8. 是否影响现有 BOM / 物流能力

- BOM：无代码路径影响。
- 物流：仅影响历史物流问答中已显式点名承运商的区域发运量查询；未把所有含“物流”的短语泛化为承运商，已用负例保护。

## 9. 验收结论

通过。

本次修复后，对于“24 年 京东物流 在各区域的承运量分别是多少”，系统不再返回所有物流数据；在当前历史台账没有京东匹配记录时，会返回空结果并提示未找到该承运商。
