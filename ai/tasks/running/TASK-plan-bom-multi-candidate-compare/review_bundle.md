# Review Bundle — Plan BOM 多候选 Compare 修复 + Query Planning V2 Phase 5.6

## 任务范围

本 bundle 只用于审查当前 scoped diff，不审查工作区内其它历史/并行任务脏文件。

### Plan BOM 多候选 compare 修复

- 修复问题：`订单00067和订单00106玻璃、间隙贴膜、焊带、汇流条、接线盒的规格描述有什么不一样，并用表格统计出来` 曾因右侧尾号 `00106` 命中多个候选而进入 `CLARIFICATION_REQUIRED`。
- 当前策略：仅在 cross-order compare + 表格/对比语义下，允许将多候选订单尾号展开为多组受控 pair 对比；单订单/普通详情歧义仍必须追问。
- 不 hardcode 具体问题全文，不 hardcode 具体客户/订单答案。

### Phase 5.6：可选响应 meta 暴露

- `query_plan_v2_meta` 默认不返回。
- 仅当请求 `include_query_plan_v2_meta=true`、配置 `QUERY_PLANNING_V2_RESPONSE_META_ENABLED=true` 且 `APP_ENV != prod` 时返回。
- 返回字段为白名单轻量字段，不返回 raw payload、原始问题、最终答案正文、业务表数据、SQL 或 trace_events。
- meta 构建失败 fail-soft，不影响正式问答。
- 物流与 Plan BOM 同步/流式 done payload 均覆盖。

### Plan BOM 表达/流式安全补齐

- Plan BOM 流式兜底优先使用 `presentation.answer`，避免把 `answer_summary` 中的内部 slot 名称流给业务员。
- 修复 `PlanBomAnswerPresentationService` 中两个误标为 `@staticmethod` 但引用 `self` 的方法，避免运行时 NameError。

## Scoped changed files

```text
backend/.env.example
backend/app/core/config.py
backend/app/domains/query_planning/services/response_meta_exposure_service.py
backend/app/domains/query_planning/services/__init__.py
backend/app/domains/logistics/api/endpoints/data_qa.py
backend/app/domains/logistics/schemas/data_qa.py
backend/app/domains/plan_bom/api/endpoints/qa.py
backend/app/domains/plan_bom/schemas/qa.py
backend/app/domains/plan_bom/services/qa_service.py
backend/app/domains/plan_bom/services/answer_presentation_service.py
docs/QUERY_PLANNING_V2_PHASE5_GRAY_RELEASE_DESIGN.md
tests/unit/query_planning/test_query_planning_phase56_response_meta.py
tests/business_acceptance/test_plan_bom_qa_multi_candidate_compare.py
```

## 验证结果摘要

```text
failing node rerun: PASS
Plan BOM multi-candidate compare file: 3 passed
Query Planning V2 Phase 5.6 focused: 8 passed
Query Planning V2 unit suite: 42 passed
business chat answer format preference: 29 passed
focused combined after fixes: 40 passed
full tests final: 246 passed, 2 warnings
compileall: PASS
pyflakes: PASS
static scan: PASS
ruff: SKIPPED (/opt/anaconda3/bin/python: No module named ruff)
diff check: PASS
```

## Dirty worktree note

当前工作区存在其它历史/并行任务文件（如物流修复、前端/streaming 相关未跟踪文件、其它 ai/tasks 目录）。本 review 只应审查上述 scoped 文件和 `diff.patch`。
