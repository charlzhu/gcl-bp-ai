# Review Result — LLM 主导综合型问题拆分

## 最终结论

**通过（PASSED）**。

最终独立 reviewer JSON：

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": [],
  "suggestions": [],
  "summary": "复审 bundle 后确认第六轮采购方式残留校验已覆盖第二个采购方式词附近的隐式限定，未发现阻塞性安全或逻辑问题。"
}
```

## 审查历程

本任务执行了多轮 reviewer 收口：

1. 初始 reviewer 发现：
   - 规则强拆路径必须移除；
   - LLM sub_plans 不能额外/未知后静默丢弃；
   - source_clause 必须回溯原文并覆盖全部诉求。

2. 后续 reviewer 发现：
   - source_clause 不能用整句/重叠片段掩盖漏问；
   - 采购方式全局查询不能静默丢弃客户限定；
   - LLM filters 与原文槽位冲突必须 fail-closed。

3. 字段能力 reviewer 发现：
   - 采购方式子句不能只依赖 LLM filters；
   - 隐式客户名、区域、月份、基地、承运商等限定也要 fail-closed；
   - 高运费子计划额外 filters/source_clause 限定不能静默忽略。

4. 最终 reviewer 发现：
   - `询比价和海尔招标` 这类限定出现在第二个采购方式词附近的表达仍需全句残留校验。

5. 第六轮返工后 reviewer 通过。

## 最终关键安全边界

- 无 LLM candidate 时不生成 `composite_decomposed`。
- Guardrail 旧拒答策略例外只允许 LLM 输出 `composite_decomposed`，不能借机放行其它 A 类 query_key。
- LLM `sub_plans` 必须正好 2 个，query_key 集合必须严格等于：
  - `hist_high_fee_addresses_by_customer`
  - `sys_mw_by_procurement_type`
- source_clause 必须：
  - 出现在原文中；
  - 不是整句；
  - 不包含另一个子句；
  - 可定位为非重叠 span；
  - 移除后只允许剩余标点、寒暄和连接词。
- 高运费子计划只允许 `year/customer_name/threshold_fee` filters。
- 采购方式子计划只允许 `year/default_system_year` filters。
- 采购方式 source_clause 不能含客户、区域、月份、基地、承运商、地址、回指或任意剥离支持词后的业务实体残留。
- 高运费 source_clause 不能含区域、月份、基地、承运商等当前无法下推限定。
- 明确“吨”口径 fail-closed。
- “这些地址/上述地址/上面的地址”等回指 fail-closed。
- 历史高运费地址内部采购方式拆分 fail-closed。

## 审查材料

- `ai/tasks/running/TASK-llm-led-composite-decomposition/review_bundle.md`
- `ai/tasks/running/TASK-llm-led-composite-decomposition/diff.patch`
- `ai/tasks/running/TASK-llm-led-composite-decomposition/test.log`
