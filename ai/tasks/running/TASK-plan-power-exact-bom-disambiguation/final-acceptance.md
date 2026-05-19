# TASK-plan-power-exact-bom-disambiguation 最终验收报告

## 1. 用户问题

用户明确输入：

```text
NT10/78GDF(江苏汉腾-2026-00106)Bill of materials（GCL-XXJC-JSPS-2026-00106，版本 A0）
```

但系统仍提示：

```text
当前订单条件命中 2 个 BOM 候选
```

并且候选中包含不相干的：

```text
NT10/78GDF(石家庄科林-2026-00106)Bill of materials
```

用户进一步强调：不能把这个问题针对某个客户名写死；下次业务员给出其他明确单号名称时也要按通用规则消歧。

## 2. 根因

原链路只抽取：

```text
order_tail_no
bom_version
model
```

没有把用户原文中的完整 BOM 名称 / 客户实例作为可用于消歧的确定性槽位传给 M4。

因此当多个客户实例共用同一个评审号 / 版本时，系统会只按尾号查候选，错误返回多候选澄清。

## 3. 修复内容

### 3.1 通用 `order_name_hint`

NLU 新增 `order_name_hint`，从以下通用表达中抽取客户实例 / BOM 名称提示：

```text
完整 BOM 名
版型(客户名称-年份-尾号)
客户名称-年份-尾号
```

并清理常见口语前缀，例如：

```text
请问
请问一下
帮我看下
麻烦看一下
```

生产逻辑不包含具体客户名分支。

### 3.2 QA 传递消歧条件

功率预测 / 供应商推荐链路会把：

```text
order_name_hint
bom_version
```

传给 M4 resolver。

### 3.3 M4 候选过滤通用化

M4 在订单尾号 / 版本初筛后，用归一化后的 `order_name_hint` 对候选 BOM 的以下字段做包含匹配：

```text
order_name
raw_file_name
order_no
file_no
```

若命中，则缩窄到对应 BOM 实例；若未命中，则保持 fail-closed，继续要求澄清，不猜测。

### 3.4 分隔符兼容

消歧归一化会忽略常见分隔符：

```text
/
-
_
```

因此类似 `NT15/72GDF` 与 `NT15-72GDF` 这类混写会更稳。

## 4. 非硬编码验证

新增 generic 测试使用 fake 客户名，而不是只用真实问题中的客户名：

```text
华东新能源-2027-12345
西南客户-2028-54321
```

还新增 fake-header resolver filter 测试，构造两个同尾号候选：

```text
NT15/72GDF(华东新能源-2027-12345)Bill of materials
NT15/72GDF(西南客户-2027-12345)Bill of materials
```

验证 `order_name_hint=华东新能源-2027-12345` 只命中第一个候选。

同时已搜索生产 service 文件：

```text
江苏汉腾 / 石家庄科林 / 华东新能源 / 西南客户
```

结果：

```text
hits=[]
```

说明生产逻辑和注释中都没有保留这些具体客户名作为特殊分支或暗示。

## 5. 当前真实问题验证

截图原文修复后：

```text
resolution_status=partial
order_name=NT10/78GDF(江苏汉腾-2026-00106)Bill of materials
candidate_count=0
answer_has_two_candidates=False
answer_has_shijiazhuang=False
```

说明已经不再错误提示“命中 2 个 BOM 候选”，也不再混入不相关客户实例。

当前仍可能因 `高透玻璃+间隙铝膜` 没有命中 active 功率模型玻璃有效 option 而返回 `partial/glass`，这是另一个配置映射问题，不是 BOM 候选消歧问题。

## 6. 测试结果

```text
RED: exact BOM name/customer should disambiguate same review number
2 failed

GREEN: exact BOM name/customer no longer returns same-review candidate list
2 passed

reviewer blocker RED: standalone customer-year-tail should disambiguate
1 failed, 2 passed

reviewer blocker GREEN: standalone customer-year-tail disambiguates
3 passed

RED: generic order-name hint should not be hardcoded to one customer
1 failed

GREEN: generic order-name hint is not case hardcoded
1 passed

RED: broader generic no-hardcode guard for polite prefixes and fake headers
1 failed, 1 passed

GREEN: broader generic no-hardcode guard for polite prefixes and fake headers
2 passed

focused real-business regression after final generic hardcode guards
15 passed

related plan power acceptance after final generic hardcode guards
78 passed, 2 warnings

final smoke after removing concrete customer examples from production comments
5 passed

compileall / diff check / static scan
passed

static / secret scan
No credential/secret findings in added lines of focused task diff.

reviewer
passed=true
```

说明：

- 2 个 warning 是既有 openpyxl 对 xlsm 扩展 / 条件格式的读取提示。
- 隔离无关物流 dirty change 后，全量 `pytest tests` 有 2 个物流 remark-keyword 既有失败；Plan BOM focused/related 测试通过，本轮改动不涉及物流。

## 7. 修改文件

```text
backend/app/domains/plan_bom/services/nlu_center_service.py
backend/app/domains/plan_bom/services/power_config_resolver_service.py
backend/app/domains/plan_bom/services/qa_service.py
tests/business_acceptance/test_plan_power_real_business_qa_regression.py
```

## 8. 验收材料

```text
ai/tasks/running/TASK-plan-power-exact-bom-disambiguation/test.log
ai/tasks/running/TASK-plan-power-exact-bom-disambiguation/diff.patch
ai/tasks/running/TASK-plan-power-exact-bom-disambiguation/review_bundle.md
ai/tasks/running/TASK-plan-power-exact-bom-disambiguation/review.md
ai/tasks/running/TASK-plan-power-exact-bom-disambiguation/final-acceptance.md
```
