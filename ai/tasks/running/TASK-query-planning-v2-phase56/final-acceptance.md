# Query Planning V2 Phase 5.6 + Plan BOM 多候选 Compare 修复 Final Acceptance

## 1. 本轮范围

本轮在继续完成 Query Planning V2 Phase 5.6 的同时，按用户确认采用方案 A，修复阻塞回归的 Plan BOM 多候选 compare 问题。

### Phase 5.6：可选响应 meta 暴露

- 新增可选 `query_plan_v2_meta` 响应字段。
- 默认关闭。
- 必须同时满足请求字段 `include_query_plan_v2_meta=true`、配置 `QUERY_PLANNING_V2_RESPONSE_META_ENABLED=true`、非生产环境，才返回轻量 meta。
- `prod` / `production` 等生产环境命名均 fail-closed。
- 不新增临时 token/header。
- 不暴露完整 raw payload、SQL、业务数据、原始问题、最终答案正文。
- 物流与 Plan BOM 同步/流式 done payload 均保持正式结果语义不变。

### Plan BOM 多候选 compare 修复

- 修复问题：`订单00067和订单00106玻璃、间隙贴膜、焊带、汇流条、接线盒的规格描述有什么不一样，并用表格统计出来` 原先因右侧尾号 `00106` 命中多个业务实例而进入 `CLARIFICATION_REQUIRED`。
- 新行为：仅在 `cross_order_material_compare + CANDIDATE_REQUIRED + order_identity scope + 单侧候选 + 候选未截断 + 候选数 <=20` 时，把多业务实例展开为多组确定性对比。
- 保留保护：单订单歧义查询仍追问，候选截断不展开，避免静默选择错误实例。

### Plan BOM 业务化回答修复

- Plan BOM 流式兜底优先使用 `presentation.answer`，避免把 `answer_summary/result_table/raw_result` 等内部结构化键作为用户可见正文。
- `PlanBomAnswerPresentationService` 中误标为静态方法但使用 `self` 的 helper 已恢复为实例方法。

## 2. 安全边界

- LLM 不生成 SQL。
- LLM 不查数。
- LLM 不直接生成最终业务事实。
- Phase 5.6 meta 只读取 shadow comparison 摘要，不参与正式 query execution。
- meta 构建异常 fail-soft，不影响正式 QA 响应。
- 多候选 compare 展开仅复用 `PlanBomQueryService.compare`，不 hardcode 订单、客户、文件名或结果。

## 3. 验证结果

### Focused / scoped

```text
python -m pytest tests/business_acceptance/test_plan_bom_qa_multi_candidate_compare.py -q
3 passed

python -m pytest tests/unit/query_planning/test_query_planning_phase56_response_meta.py -q
9 passed

python -m pytest tests/unit/query_planning -q
43 passed
```

### tracked tests + 本轮新增 scoped tests

当前工作区存在大量其它历史/并行任务未跟踪测试文件；为避免把非本轮未跟踪测试纳入提交门禁，最终回归使用 `git ls-files tests` 加本轮新增测试文件：

```text
185 passed, 2 warnings in 29.21s
```

说明：本轮早些时候在修复 Plan BOM 多候选 compare 后曾执行 `python -m pytest tests -q`，全工作区当时为 `246 passed, 2 warnings`。随后工作区内其它未跟踪并行测试文件发生/保留额外失败，已按 dirty-worktree focused-review 规则隔离，本轮提交不纳入这些未跟踪文件。

### 静态与格式

```text
python -m compileall -q backend tests
COMPILE=PASS

python -m pyflakes <scoped files>
PYFLAKES=PASS

scoped static secret/dangerous pattern scan
STATIC_SCAN=PASS

git diff --check <scoped files>
DIFF_CHECK=PASS

python -m ruff check <scoped files>
RUFF=SKIPPED: /opt/anaconda3/bin/python: No module named ruff
```

## 4. 独立 Review

- 初次大 diff review 因 patch 较大超时。
- 改用 compact review bundle 后完成独立 review。
- 第一轮 compact review：通过，提出两条建议。
- 已处理：
  1. 生产环境别名 `production` 也 fail-closed；
  2. 左侧候选展开时使用已解析右侧上下文，避免回退到原始尾号。
- 复审结果：通过，无阻塞安全/逻辑问题。

## 5. 影响评估

- 不破坏物流 Data QA 主链路。
- 不破坏 Plan BOM QA 主链路。
- Query Planning V2 仍为 shadow/diagnostic/gray exposure，不替代正式 planner。
- Plan BOM 多候选 compare 只扩大对比语义下的候选展开能力，不改变单订单歧义追问口径。

## 6. 未执行事项

- 未 push。
- 未部署。
- 未合并。
- 未修改 main。
