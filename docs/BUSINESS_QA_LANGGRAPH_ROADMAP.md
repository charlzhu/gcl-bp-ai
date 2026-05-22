# Business QA LangGraph 受控编排路线图

## 一、文档用途

本文档用于说明统一业务问数 LangGraph 改造的阶段边界、8 张工程卡目标、15 个能力阶段覆盖关系，以及它与现有 Query Planning V2 / 受控 NL2SQL / 各业务域确定性服务之间的分层关系。

当前已落地范围为 LQG-1：只建立默认关闭的 LangGraph 基础骨架，包含配置开关、请求/响应/事件/state 数据结构、`receive` 节点、`START -> receive -> END` 最小图和 Runner。LQG-1 不执行真实业务查询，不替代物流、计划 BOM、经营分析、物管等既有服务。

---

## 二、总体定位

统一业务问数 Graph 是“入口编排层”，不是事实计算层，也不是自由 SQL 执行层。

分层原则：

1. Graph 负责接收请求、串联节点、记录 trace、根据阶段能力选择受控 adapter。
2. 业务域服务负责真实查询、计算、消歧、结果结构化。
3. Query Planning V2 / 受控 NL2SQL 负责生成和校验结构化计划，但必须经白名单、语义目录、安全校验和只读中间库边界。
4. LLM 只允许参与领域识别、意图理解、候选生成和表达润色，不直接计算业务事实。
5. 用户问答必须优先基于智能助手中间库，不实时直查 SAP Oracle MID、ERP、MES、WMS、TMS 等外部业务源库。
6. 用户可见回答不得暴露内部技术实现内容。

---

## 三、8 张工程卡目标

| 卡号 | 目标 | 主要交付 | 禁止越界 |
| --- | --- | --- | --- |
| LQG-1 | LangGraph 基础骨架 | 默认关闭配置、request/response/event/state、`receive` 节点、`START -> receive -> END`、单元测试 | 不接真实业务执行，不接前端入口，不替换现有问答链路 |
| LQG-2 | 领域识别与普通问答分流 | domain router 节点、低置信度澄清、普通问答安全出口、路由 trace | 不把未知业务问题强行路由到某个领域 |
| LQG-3 | Query Planning V2 adapter | 将 Graph state 转成既有 Query Planning V2 调用上下文，保留 shadow/audit | 不让 LLM 绕过 QueryPlan schema 与安全策略 |
| LQG-4 | 能力/工具注册与权限预检 | capability registry、工具白名单、风险等级、审批占位、审计事件 | 不允许未注册工具或危险写操作自动执行 |
| LQG-5 | 领域服务执行 adapter | 物流、计划 BOM、经营分析、物管的受控 service adapter；统一 result contract | 不直接查外部源库，不绕过中间库和领域 repository |
| LQG-6 | 事实锁定与回答表达 | facts contract、presentation adapter、技术泄露检查、空结果/澄清/unsupported 边界 | 不让 LLM 改写数值、状态、表格事实或错误类型 |
| LQG-7 | 审计、回放与评测 | graph trace 持久化、shadow report、回放脚本、跨域样例集 | 不用演示题替代正式回归，不保存密钥或连接串 |
| LQG-8 | API/前端灰度接入 | 默认关闭 API、灰度开关、流式事件、前端可视 trace、全链路 E2E | 不默认替换现有物流/BOM/经营分析入口 |

---

## 四、15 个能力阶段覆盖关系

| 阶段 | 能力阶段 | 覆盖卡 | 说明 |
| --- | --- | --- | --- |
| C01 | 请求接收 | LQG-1 | 接收问题、领域提示、trace_id，写入 receive trace。 |
| C02 | 入口开关与灰度 | LQG-1, LQG-8 | 默认关闭；灰度打开前不影响既有 API。 |
| C03 | 领域识别 | LQG-2 | 区分物流、计划 BOM、物管、经营分析、普通问答和未知问题。 |
| C04 | 普通问答与非业务分流 | LQG-2 | 普通问题不进入业务查数链路。 |
| C05 | 澄清与拒答边界 | LQG-2, LQG-6 | 低置信度、缺口径、unsupported、空结果必须 fail-closed。 |
| C06 | 能力匹配 | LQG-3, LQG-4 | 将意图映射到受控 capability、query plan 或工具。 |
| C07 | 语义目录与实体归一 | LQG-3, LQG-5 | 使用既有领域语义目录和值解析，不硬编码单个样例。 |
| C08 | QueryPlan/SQLPlan 候选 | LQG-3 | 候选只能是结构化 schema，不能是可自由执行文本。 |
| C09 | 安全校验与权限预检 | LQG-3, LQG-4 | 白名单、只读、中间库、字段/指标/维度、工具权限统一校验。 |
| C10 | 领域确定性执行 | LQG-5 | 调用各领域 service/repository，程序负责查数和计算。 |
| C11 | 工具调用与副作用治理 | LQG-4, LQG-7 | 工具必须注册、审计、可回放；写操作需要正式权限/审批。 |
| C12 | 事实合同与结果结构 | LQG-5, LQG-6 | 统一 status、facts、table、cards、warnings、source basis。 |
| C13 | LLM 表达润色 | LQG-6 | 只基于已锁定事实表达，不改状态、不改数值。 |
| C14 | 前端流式与持久化 | LQG-8 | 统一流式事件、历史重放、表格/图表/导出展示。 |
| C15 | 审计评测与回归 | LQG-7, LQG-8 | 建立 graph 级 shadow、回放、跨域回归和验收材料。 |

---

## 五、与现有 NL2SQL / Query Planning 分层关系

推荐调用链：

```text
统一业务问答入口
  -> Business QA Graph receive
  -> domain router
  -> capability / query planning adapter
  -> Query Planning V2 / 受控 NL2SQL 候选
  -> deterministic validator
  -> domain service / repository / tool adapter
  -> facts contract
  -> presentation adapter
  -> frontend streaming / history / audit
```

关键边界：

1. Graph 不能直接拼接或执行 SQL。
2. Graph 不能直接读取 SAP Oracle MID 等外部源库。
3. Graph 不能让 LLM 自行决定执行结果是否成功。
4. 受控 NL2SQL 只能作为候选计划生成层，必须经过语义目录、白名单、安全校验、只读执行和审计。
5. 物流 NL2SQL 现有 shadow / SQLPlan / Semantic Catalog 能力是领域能力，不因 Graph 接入而被替换。
6. 计划 BOM、物管、经营分析在具备各自中间库、语义目录、测试集和安全门禁前，不应被统一 Graph 强行接入自由问数。

---

## 六、LQG-1 已落地边界

代码路径：

1. `backend/app/core/config.py`
   - 新增 `business_qa_langgraph_enabled: bool = False`。
2. `backend/app/domains/business_qa_graph/schemas/`
   - 新增 request、response、event、state 数据结构。
3. `backend/app/domains/business_qa_graph/nodes/receive_node.py`
   - 接收问题、领域提示、trace_id，并写入 receive trace。
4. `backend/app/domains/business_qa_graph/builder.py`
   - 构建 `START -> receive -> END` 最小 StateGraph。
5. `backend/app/domains/business_qa_graph/runner.py`
   - 提供默认关闭的 Runner；关闭时返回 DISABLED，打开时只执行 receive 节点。
6. `tests/unit/business_qa_graph/test_business_qa_graph_skeleton.py`
   - 覆盖配置默认关闭、路由不被替换、receive trace、graph invoke、runner skeleton-only 响应。

LQG-1 不包含：

1. API endpoint。
2. 前端入口。
3. 领域识别模型。
4. 工具调用。
5. SQLPlan 执行。
6. 任何真实业务查数或计算。

---

## 七、后续推进建议

1. 先完成 LQG-2，让领域识别和普通问答分流在 shadow 下可观测。
2. 再做 LQG-3，把 Graph 与既有 Query Planning V2 连接为 adapter，不新增平行 planner。
3. LQG-4 必须先定义工具/能力注册表，再允许任何工具节点存在。
4. LQG-5 每接入一个业务域，都要先证明该业务域已有中间库、确定性 service、样例题和 regression。
5. LQG-6 前不得把 Graph 输出暴露为正式业务答案。
6. LQG-8 前不得替换现有物流、计划 BOM、经营分析问答入口。

---

## 八、验收门槛

每张 LQG 卡至少需要：

1. TDD RED/GREEN 记录。
2. focused tests。
3. 相邻业务域回归。
4. Python compile 或等价静态检查。
5. scoped diff。
6. 独立 review。
7. final acceptance 文档。
8. 明确说明是否影响物流、计划 BOM、功率预测、物管、经营分析既有链路。

LQG-1 当前验收口径：只要默认关闭、最小 graph 可运行、receive trace 稳定、旧业务路由不被替换，即视为阶段内完成；后续业务能力必须另开卡继续。
