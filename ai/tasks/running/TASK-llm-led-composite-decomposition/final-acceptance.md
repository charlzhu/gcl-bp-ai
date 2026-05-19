# Final Acceptance — LLM 主导综合型问题拆分

## 验收结论

**通过（PASSED）**。

本轮已完成用户要求：综合型问题拆分必须建立在 LLM 语义理解主导之上，不能纯靠规则拆分；规则层仅承担安全校验、query_key 白名单、字段能力边界、source_clause grounding、槽位冲突和 fail-closed 保护。

## 根因

旧实现中，planner 存在按关键词/规则直接构造 `composite_decomposed` 的路径。该路径可以在没有 LLM 明确给出可拆分综合问题和子计划结构时，直接把问题拆成多个受控查询，违反“LLM 主导拆分”的原则。

同时，原先 Guardrail 对某些旧拒答策略完全锁定，LLM 没有机会判断“这是两个独立子问”；而放开后如果不做严格校验，又存在 LLM 输出不完整、不接地、带额外限定或静默丢弃字段边界的风险。

## 最终改动

### 代码

- `backend/app/domains/logistics/schemas/llm_understanding.py`
  - 增加 `composite` intent 支持。

- `backend/app/domains/logistics/services/llm_understanding_service.py`
  - LLM query key 白名单/提示词支持 `composite_decomposed`。
  - 明确要求 LLM 输出 `filters.sub_plans`，包括 `query_key/source_clause/filters`。

- `backend/app/domains/logistics/services/llm_understanding_guardrail_service.py`
  - Guardrail allowlist 加入 `composite_decomposed`。
  - 旧 `high_fee_address_procurement_split` 策略仅作为受控复合拆分例外。
  - 在该例外下，LLM candidate 必须是 `composite_decomposed`，不能放行其它 query_key。

- `backend/app/domains/logistics/services/data_qa_planner.py`
  - 移除无 LLM candidate 的规则强拆主路径。
  - 新增 LLM composite 回构与严格校验：
    - sub_plans 正好 2 个；
    - query_key 集合严格匹配；
    - source_clause 必须 grounded；
    - source_clause 必须非重叠 span 覆盖全部实质诉求；
    - LLM filters 与原文确定性槽位冲突 fail-closed；
    - 高运费子计划 filters/source_clause 额外限定 fail-closed；
    - 采购方式子计划 filters/source_clause 额外限定 fail-closed；
    - 吨口径、回指、历史子集采购方式拆分 fail-closed。

- `backend/app/domains/logistics/services/data_qa_service.py`
  - 复合执行说明改为“LLM 先识别顶层并列子问题，规则层再映射到受控 query_key”。

### 测试

- `tests/business_acceptance/test_logistics_llm_led_composite_decomposition.py`
  - 新增 19 个 LLM 主导综合拆分回归测试。

覆盖：

1. 无 LLM candidate 时不得规则强拆。
2. Guardrail 允许 LLM composite candidate。
3. Guardrail 不允许 policy exception 放行非 composite query_key。
4. 可信 LLM 拆分可执行并合并结果。
5. 吨口径 fail-closed。
6. 回指 fail-closed。
7. LLM 子计划额外/未知 query_key fail-closed。
8. source_clause 幻觉 fail-closed。
9. LLM filters 年份冲突 fail-closed。
10. LLM 漏报第三诉求 fail-closed。
11. 整句/重叠 source_clause fail-closed。
12. 采购方式显式客户限定 fail-closed。
13. 采购方式隐式客户限定 fail-closed。
14. 采购方式区域/月度限定 fail-closed。
15. 采购方式第二个采购方式词附近隐式实体限定 fail-closed。
16. 高运费子计划额外 filters fail-closed。
17. 高运费 source_clause 区域限定 fail-closed。

## 验证结果

### Focused

```bash
PYTHONPATH=. pytest tests/business_acceptance/test_logistics_llm_led_composite_decomposition.py -q
```

结果：

```text
19 passed in 0.95s
```

### 全量业务验收

```bash
PYTHONPATH=. pytest tests/business_acceptance -q
```

结果：

```text
168 passed, 2 warnings in 25.08s
```

warnings 来自 `openpyxl` 对 Excel 扩展和条件格式不支持，非本轮新增失败。

### 编译检查

```bash
python -m compileall -q ...
python -m py_compile tests/business_acceptance/test_logistics_llm_led_composite_decomposition.py
```

结果：通过。

### 前端构建

```bash
cd frontend && npm run build
```

结果：通过；仅 Vite chunk size warning。

### diff whitespace

```bash
git diff --check -- <task scoped files>
```

结果：通过。

### 新增行安全扫描

扫描项：

- hardcoded secret
- shell injection
- eval/exec
- pickle loads
- SQL string-formatting

结果：

```text
added-line static scan findings: 0
```

### ruff

环境未安装：

```text
/opt/anaconda3/bin/python: No module named ruff
```

## 独立 reviewer

最终 reviewer 通过：

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": [],
  "suggestions": [],
  "summary": "复审 bundle 后确认第六轮采购方式残留校验已覆盖第二个采购方式词附近的隐式限定，未发现阻塞性安全或逻辑问题。"
}
```

## 风险与说明

1. 本轮只修物流综合型问题拆分链路，不处理前一项“回答格式优化”的最终验收。
2. 工作区存在其它历史脏文件/未跟踪文件，提交时必须只暂存本轮任务范围文件和验收材料，不能使用 `git add .`。
3. `sys_mw_by_procurement_type` 当前仍只支持全局 2026 系统侧采购方式 MW；任何客户/区域/月份/承运商/地址限定均 fail-closed，后续如需支持，需要新增确定性查询能力，而不是让 LLM 代算或静默丢弃限定。
4. 当前实现对 LLM 输出采取保守解析；可回答范围比纯规则强拆窄，但符合“LLM 主导 + 规则安全校验”的业务边界。

## 任务材料

- `ai/tasks/running/TASK-llm-led-composite-decomposition/diff.patch`
- `ai/tasks/running/TASK-llm-led-composite-decomposition/test.log`
- `ai/tasks/running/TASK-llm-led-composite-decomposition/review_bundle.md`
- `ai/tasks/running/TASK-llm-led-composite-decomposition/review-result.md`
- `ai/tasks/running/TASK-llm-led-composite-decomposition/final-acceptance.md`
