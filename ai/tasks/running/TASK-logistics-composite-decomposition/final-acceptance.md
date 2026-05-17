# TASK-logistics-composite-decomposition 最终验收报告

## 1. 任务结论

验收通过。

本轮已优化物流数据问答的顶层并列复合问题处理：当用户问题可安全拆为多个已支持、已审计的确定性子问题时，planner 会生成 `composite_decomposed` 计划，service 分别执行子查询并合并答案返回前端。

同时保留安全边界：

- 真正要求“历史高运费地址内部按询比价/招标拆分”的问题仍拒答，不用 2026 全局采购方式结果冒充历史子集拆分。
- 显式要求“吨”口径发运量时仍澄清，不用 MW 口径替代。
- LLM 不参与业务数值计算；业务结果仍来自后端确定性查询。

## 2. 根因分析

1. 原 planner 缺少顶层复合问题拆分机制。
   - 截图问题同时包含“2024 年客户高运费收货地址”和“采购方式发运量”两个可独立回答的子问题。
   - 原逻辑把整句作为一个历史采购方式拆分问题处理，命中 `historical_procurement_split_missing`，导致整体拒答。

2. 客户名抽取存在误判风险。
   - “创维客户发货的项目地...”这类表达中，旧抽取逻辑可能把“项目地”的“地”误当客户名。
   - 本轮针对高运费地址子句增加窄口径客户名抽取，避免把领域词尾字当客户。

3. 复合拆分必须保守处理回指。
   - “这些地址 / 上述的地址 / 这些高运费地址 / 上面的地址”等表达并不是独立第二问，而是在前一个历史结果集内部继续拆分。
   - 历史台账缺少稳定采购方式字段，必须拒答，不能替换成 2026 系统侧全局聚合。

## 3. 修改文件

- `backend/app/domains/logistics/services/data_qa_planner.py`
  - 新增可拆复合问题识别：`composite_decomposed`。
  - 新增高运费地址子句、采购方式发运量子句、金额阈值、客户名、回指边界等辅助识别。
  - 将“吨口径发运量”澄清边界前置到复合拆分之前。
  - 对 `这些/上述/上面/前面/该批/... + 地址/项目地/结果/清单` 等回指表达 fail-closed。

- `backend/app/domains/logistics/services/data_qa_service.py`
  - 新增复合计划执行逻辑。
  - 每个子计划仍走既有受控 query_key 和确定性仓储查询。
  - 合并 `answer_summary`、`result_table`、`calculation_logic`、`data_scope`、`warnings`。
  - 任一子计划不可回答时保守返回不支持。

- `tests/business_acceptance/test_business_feedback_excel_qa_regression.py`
  - 增加截图类复合正例。
  - 增加不同年份/客户的泛化正例。
  - 增加历史采购方式内部拆分负例。
  - 增加回指前一结果的参数化负例：这些地址、上述的地址、这些高运费地址、上述高运费项目地、上面的地址、这些运费超过20万的地址。
  - 增加显式吨口径澄清负例。

## 4. TDD 记录

### 初始 RED

```text
2 failed, 1 passed, 14 deselected
```

截图复合题和泛化复合题修复前均失败，符合预期。

### reviewer 返工 RED

- “这些地址”回指：修复前失败。
- “上述的地址 / 这些高运费地址 / 上述高运费项目地”：修复前失败。
- “上面的地址 / 这些运费超过20万的地址”：修复前失败。

### 最终 GREEN focused

```bash
PYTHONPATH=. pytest tests/business_acceptance/test_business_feedback_excel_qa_regression.py -q -k "reference_to_previous_high_fee_addresses or composite or non_decomposable or explicit_ton_unit"
```

结果：

```text
10 passed, 14 deselected in 1.12s
```

## 5. 测试与验证

### 业务反馈回归文件

```bash
PYTHONPATH=. pytest tests/business_acceptance/test_business_feedback_excel_qa_regression.py -q
```

结果：

```text
24 passed in 1.17s
```

### 全量业务验收测试

```bash
PYTHONPATH=. pytest tests/business_acceptance -q
```

结果：

```text
203 passed, 2 warnings in 30.33s
```

warning 为 `openpyxl` 读取 xlsm 的既有第三方库提示，本轮未新增失败。

### 编译检查

```bash
PYTHONPATH=. python -m py_compile backend/app/domains/logistics/services/data_qa_planner.py backend/app/domains/logistics/services/data_qa_service.py tests/business_acceptance/test_business_feedback_excel_qa_regression.py
```

结果：通过，无输出。

### 前端构建

```bash
npm run build
```

目录：`frontend`

结果：

```text
✓ 1702 modules transformed.
✓ built in 2.96s
```

Vite chunk size warning 为现有体积提示，本轮未修改前端。

### 静态检查

- `ruff`：当前环境未安装，输出 `ruff not installed`。
- `git diff --check`：通过。
- 新增行静态安全扫描：0 findings。

## 6. 独立 review

最终独立 reviewer 结论：通过。

reviewer 重点验证：

- 复合正例进入 `composite_decomposed`。
- 6 类回指前一高运费地址结果的变体均不会误拆成 2026 全局采购方式。
- 显式“吨”口径返回澄清。
- 历史高运费地址内部按询比价/招标拆分仍保持不支持边界。
- 服务层只执行受控子计划，不做跨源二次推理。

详见：`ai/tasks/running/TASK-logistics-composite-decomposition/review-result.md`

## 7. 风险与边界

1. 当前复合拆分有意收窄在“历史高运费地址清单 + 2026 系统侧采购方式 MW 发运量”这一类，不扩展为任意自由拆句。
2. 未写年份的采购方式子句默认按 2026 系统侧口径处理，并在 warning 中说明历史台账与 2026 系统侧不混算。
3. 若后续业务希望支持“历史高运费地址内部按采购方式拆分”，需要先补齐历史台账稳定采购方式字段或映射规则，不能由当前逻辑硬推。
4. 后续可继续补充更多回指同义词，例如“前面提到的地址”“这些收货地”等。

## 8. 是否影响现有 BOM / 物流能力

- BOM：未修改 BOM 主链路和计划功率链路，理论不影响。
- 物流：仅增加受控复合拆分和相关安全边界，既有业务验收测试全量通过。
- 前端：未修改前端代码；后端返回仍使用既有 `LogisticsDataQaResult` 结构，复合结果通过 `section` 字段区分子结果。

## 9. 提交建议

当前工作区存在大量其它历史脏文件/未跟踪文件，提交时不要使用 `git add .` 或 `git add -A`。

建议仅暂存本轮相关文件：

```bash
git add \
  backend/app/domains/logistics/services/data_qa_planner.py \
  backend/app/domains/logistics/services/data_qa_service.py \
  tests/business_acceptance/test_business_feedback_excel_qa_regression.py \
  ai/tasks/running/TASK-logistics-composite-decomposition/diff.patch \
  ai/tasks/running/TASK-logistics-composite-decomposition/test.log \
  ai/tasks/running/TASK-logistics-composite-decomposition/review-result.md \
  ai/tasks/running/TASK-logistics-composite-decomposition/final-acceptance.md
```

合并和上线仍需用户人工确认。
