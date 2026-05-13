# Plan BOM 多候选 Compare 修复 Final Acceptance

## 1. 本轮范围

按用户确认采用方案 A，修复阻塞回归的 Plan BOM 多候选 compare 问题，并同步保留 Query Planning V2 Phase 5.6 可选响应 meta 暴露变更。

## 2. 根因

`PlanBomQueryService.compare` 在单侧订单尾号命中多个业务实例时返回候选态：

```text
status.code = CANDIDATE_REQUIRED
missing_slots = ["order_identity"]
```

这对单订单查询是正确保护，但对“订单 A 和订单 B 的规格描述有什么不一样，并用表格统计出来”这类跨订单表格对比问题，用户已经表达了对比意图；此时如果只有单侧多业务实例，系统可以安全地把每个候选实例分别与已确定的另一侧做确定性 compare，并在表格中展示实例标签，而不是追问内部实例字段。

## 3. 修复

- 新增 `_expanded_candidate_compare_response`：候选态 compare 可安全展开时，逐个候选调用既有 `query_service.compare`。
- 新增受控判断 `_can_expand_compare_candidates`：仅允许 `cross_order_material_compare + CANDIDATE_REQUIRED + order_identity scope + 单侧候选 + 非截断 + <=20`。
- 新增展开表列：`compare_pair / left_instance / right_instance / material_category / left_description / right_description / difference_type` 等。
- 保留单订单歧义追问保护。
- 候选截断时不展开，避免不完整对比伪装成完整结果。
- 左/右侧候选展开均使用已解析上下文构造精确 compare 请求，避免回退到原始尾号。

## 4. 验证

```text
python -m pytest tests/business_acceptance/test_plan_bom_qa_multi_candidate_compare.py -q
3 passed
```

覆盖：

1. 两个订单尾号做规格差异表时，多业务实例尾号自动展开对比，不再追问 `order_identity`；
2. 单订单查询命中多业务实例时仍返回澄清；
3. 候选被截断时不展开。

## 5. 回归

```text
tracked tests + 本轮新增 scoped tests
185 passed, 2 warnings in 29.21s
```

说明：当前工作区存在其它历史/并行任务未跟踪测试文件；本轮提交门禁按 tracked tests 加本轮新增测试隔离执行。

## 6. Review

独立 compact review + 复审均通过，无阻塞安全/逻辑问题。

## 7. 未执行事项

- 未 push。
- 未部署。
- 未合并。
- 未修改 main。
