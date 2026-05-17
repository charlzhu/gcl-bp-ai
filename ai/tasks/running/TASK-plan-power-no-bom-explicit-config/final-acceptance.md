# Final Acceptance: TASK-plan-power-no-bom-explicit-config

## 结论
已完成：计划 BOM 功率问答现在支持“无 BOM / BOM 尚未上传”的显式搭配评估场景。

当业务员只给出：
- 版型；
- 准备搭配（焊带、玻璃、汇流条、线缆/接线盒、标板基准等）；
- 目标组件功率；

系统会走确定性链路：NLU 槽位抽取 → M4 显式配置 option 校验 → M3 功率预测/供应商推荐，直接输出各电池厂家建议效率段，不再强制要求先上传 BOM。

## 截图问题验证
问题：

```text
NT12-66GDF，0.24+0.26焊带+超高透玻璃+6*0.35+4*0.35反光+400/-200mm（4mm²）+计量院基准，满足单一功率720，分别需要哪些供应商多少效率起投
```

当前结果：
- classification: A
- status: OK
- resolution: resolved
- model: NT12-66GDF
- glass: 超高透+间隙铝膜
- cable: +400/-200mm（4mm²）
- 返回供应商效率段明细表：通威、爱旭、中润、芜湖、时创等；目标功率档为 720W。

## 根因
旧逻辑在该问法上误澄清，主要原因：
1. `超高透玻璃` 被正则从中间误抽为 `高透`。
2. 无 BOM 方案评估中，业务员直接写 `6*0.35+4*0.35反光` 和 `+400/-200mm（4mm²）`，旧 NLU 只支持带“汇流条/接线盒/线长”等显式标签的写法。
3. M4 显式玻璃归一原只覆盖 `双镀/单镀`，未覆盖 `超高透`。
4. cable 显式解析原不兼容 `+400/-200mm（4mm²）` 里的负号和显式线径。

## 修改文件
- `backend/app/domains/plan_bom/services/nlu_center_service.py`
  - 修复 `超高透` / `高透` 抽取顺序。
  - 增加无 BOM 显式搭配问法中的 busbar/cable 通用抽取。
  - 仅抽槽位，不计算功率。
- `backend/app/domains/plan_bom/services/power_config_resolver_service.py`
  - M4 显式玻璃支持 `超高透/高透/双镀/单镀` 前缀匹配，但只匹配 active 模型真实 option。
  - M4 cable 支持 `+400/-200mm（4mm²）` 这类显式线径。
  - 对显式无效线径 fail-closed：例如 `9mm²` 不会静默回退成默认 `4mm²`。
- `tests/business_acceptance/test_plan_power_real_business_qa_regression.py`
  - 新增无 BOM 显式配置直答回归。
  - 新增无效线径 fail-closed 回归，覆盖 `+400/-200mm（9mm²）` 和默认长度 `+300/-200mm（9mm²）`。
- `ai/tasks/running/TASK-plan-power-no-bom-explicit-config/*`
  - `test.log`
  - `diff.patch`
  - `review_bundle.md`
  - `review.md`
  - `final-acceptance.md`

## TDD / 验证
- RED：无 BOM 显式配置测试修复前失败，返回 `classification=B` / `CLARIFICATION_REQUIRED`。
- GREEN：无 BOM 显式配置 happy path 通过。
- Reviewer RED #1：`+400/-200mm（9mm²）` 修复前错误返回 A，已加回归。
- Reviewer RED #2：`+300/-200mm（9mm²）` 修复前仍会回退默认 4mm²，已加回归。
- GREEN：happy path + 两个 invalid wire fail-closed 场景 `3 passed`。
- Related backend QA/M3/M4：`82 passed, 2 warnings`。
- Full pytest：`164 passed, 2 warnings`。
- Compile：通过。
- Frontend build：通过。
- Focused whitespace/static/literal secret scan：通过。
- Final reviewer：`passed=true`，Blocking issues: None。

## 影响范围
- 不修改 M3 功率计算公式、CTM、预测比例、供应商评分逻辑。
- 不修改前端。
- 不影响 BOM 上传入口。
- 不恢复任何临时 admin token。
- 不针对截图/客户/订单写死；新增规则基于通用材料槽位和 active 模型 option 校验。

## 当前工作区注意
当前 workspace 仍有多个其他任务的历史 WIP 修改/未跟踪文件。本任务聚焦上述计划 BOM 功率问答文件与验收材料。
