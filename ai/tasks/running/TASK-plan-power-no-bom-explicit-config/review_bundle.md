# Review Bundle: TASK-plan-power-no-bom-explicit-config

## 背景
业务员提出：在 BOM 还没做/没上传的情况下，只给出版型、准备搭配、目标组件功率，也希望系统直接回答各电池厂家可以满足的效率段，不应强制要求 BOM 上传。

截图复现问题原问法：

```text
NT12-66GDF，0.24+0.26焊带+超高透玻璃+6*0.35+4*0.35反光+400/-200mm（4mm²）+计量院基准，满足单一功率720，分别需要哪些供应商多少效率起投
```

修复前：返回 B 类澄清，提示 `glass` 未确认；实际根因是：
- NLU 里的玻璃正则先匹配 `高透`，导致 `超高透玻璃` 被误抽成 `高透`；
- 无 BOM 评估问法中，业务员省略“汇流条/接线盒”字样，直接写 `6*0.35+4*0.35反光+400/-200mm（4mm²）`，旧 NLU 不抽 busbar/cable；
- M4 显式玻璃归一只覆盖 `双镀/单镀`，不覆盖 `超高透`；
- cable 显式解析不兼容 `+400/-200mm（4mm²）` 里的负号和显式线径。

## 修改文件
- `backend/app/domains/plan_bom/services/nlu_center_service.py`
  - `超高透` 放到 `高透` 前，避免正则从中间误抽。
  - 增加无 BOM 显式方案问法的通用 busbar/cable 槽位抽取：支持 `6*0.35+4*0.35反光` 和 `+400/-200mm（4mm²）`。
  - 仅做槽位抽取；有效性仍交给 M4 确定性 option 校验。
- `backend/app/domains/plan_bom/services/power_config_resolver_service.py`
  - M4 显式玻璃归一支持 `超高透/高透/双镀/单镀` 前缀，只匹配当前 active 模型真实 option。
  - M4 cable 显式解析支持 `+400/-200mm（4mm²）`，显式线径优先，失败时再用 active 默认线径，仍 fail-closed。
- `tests/business_acceptance/test_plan_power_real_business_qa_regression.py`
  - 新增 RED/GREEN 真实业务回归：无 BOM + 版型 + 显式搭配 + 单一 720W，应返回 A 类供应商效率段。

## 职责边界
- 未改后端 M3 功率计算公式、CTM、预测比例、供应商评分逻辑。
- 未让 LLM 直接计算功率预测结果。
- 未修改前端。
- 未恢复任何临时 token/admin token。
- 不针对某个客户/订单/截图值写死；规则基于材料槽位和 active 模型 option。

## 验证记录
详见 `ai/tasks/running/TASK-plan-power-no-bom-explicit-config/test.log`。

关键结果：
- RED：新增无 BOM 显式配置测试先失败，修复前返回 `classification=B` / `CLARIFICATION_REQUIRED`。
- GREEN focused：无 BOM 显式配置测试通过。
- Reviewer blocking RED #1：新增 `+400/-200mm（9mm²）` 无效显式线径 fail-closed 测试，修复前错误返回 `classification=A`。
- Reviewer blocking RED #2：补充默认长度 `+300/-200mm（9mm²）` fail-closed 测试，修复前仍错误回退默认 `4mm²` 并返回 `classification=A`。
- Reviewer fix GREEN：原始无 BOM直答 + 两个无效线径 fail-closed 场景 `3 passed`。
- Related backend QA/M3/M4 tests：`82 passed, 2 warnings`。
- Full suite：`164 passed, 2 warnings`。
- Compile：通过。
- Frontend build：通过（本任务未改前端，仅作为质量门禁；最终修复后重新跑过）。
- Focused diff check + literal secret scan：通过；无新增凭据/密钥/token。

## Reviewer 返工说明
首轮 reviewer 发现阻塞问题：当用户显式写 `+400/-200mm（9mm²）` 且模型无该线径 option 时，旧修复会回退 active 默认 `4mm²` 并错误直答。第二轮 reviewer 又发现默认长度 `+300/-200mm（9mm²）` 仍会落入默认 option fallback。已修复为：
- 如果用户显式给出线径，只尝试该显式线径；无法命中模型真实 option 时立即返回 `None`，由 M4 unresolved 触发澄清。
- 只有用户没有显式线径、仅写长度时，才允许使用 active 模型默认线径/默认 option 补齐。

## 人工验证输出摘要
当前问法返回：
- classification: `A`
- status: `OK 供应商功率推荐成功`
- answer: `已按显式输入配置和目标功率比例完成供应商推荐，当前最高匹配供应商为 通威。`
- resolution: `resolved`，`glass=超高透+间隙铝膜`，`cable=+400/-200mm（4mm²）`
- 结果表 6 行，含通威/爱旭/中润/芜湖/时创等供应商，目标功率档 `720W`，并输出建议效率段和落档比例预估。

## 请 reviewer 重点检查
1. 是否满足“无 BOM 也可显式搭配直算”的业务需求。
2. NLU 新增正则是否足够通用，是否存在把订单/型号误抽为 busbar/cable 的风险。
3. M4 归一是否只匹配 active 模型真实 option，是否仍 fail-closed。
4. 是否破坏已有 BOM 查询/订单消歧/功率推荐路径。
5. 是否存在硬编码客户/订单/截图案例或凭据泄漏。
