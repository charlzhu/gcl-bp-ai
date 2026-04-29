# 物流域自然语言理解中枢 v1 设计

## 目标

Logistics NLU Center v1 的目标是把已经分散落地的规则 planner、LLM 理解层、Guardrail、澄清辅助、A/B/C 题库治理能力，统一成一个后端内部理解中枢。

本中枢只做理解与诊断，不替代正式 `data-qa planner`，不生成 SQL，不查数据库，不改写 B/C 最终边界。

## 现有能力映射

| 模块 | 当前已有能力 | NLU Center 复用方式 | 不重复实现内容 | 仍缺口 |
| --- | --- | --- | --- | --- |
| `llm_understanding_service.py` | LLM 语义理解、术语归一候选、query_key 白名单候选、disabled/error 降级 | 作为可选候选理解来源，只有配置可用且显式启用时调用 | 不重新写外部 LLM 调用与 prompt 约束 | 原输出 schema 不含多问题、统一 route、完整 slot 体系 |
| `llm_understanding_guardrail_service.py` | A 类白名单增强、shadow/assist/off、sample rate、审计、B/C 锁定 | NLU Center 调用其 `evaluate` 生成影子诊断摘要 | 不重新实现 Guardrail 白名单、抽样、审计和回退逻辑 | NLU 侧需要把 guardrail 决策压缩成统一字段 |
| `llm_clarification_assist_service.py` | 规则已判澄清后，LLM 辅助识别缺口径并生成业务化追问 | 作为后续澄清链路能力，不在 NLU v1 内重复调用执行态 assist | 不改写澄清辅助 prompt、category 白名单和审计 | NLU schema 需要表达 missing slots 与追问方向 |
| `question_bank_response_policy.py` | B/C 响应策略、业务化澄清模板、不支持原因与建议 | 作为 B/C 边界判断的正式来源 | 不重复实现 B/C 边界规则 | 规则类别与统一 intent/slot 的映射需持续沉淀 |
| `slot_extractor.py` | 年/月/季度、区域/省份、始发地/目的地、运输方式、车型、状态、客户/承运商、来源层等公共槽位抽取 | NLU Center 与 planner 共用同一套 slot 抽取能力 | 不重复在 NLU 与 planner 内维护相同解析规则 | 后续仍需按真实问法持续补齐更细粒度 slot |
| `data_qa_planner.py` | 受控 query_key、指标/维度/过滤条件、澄清/不支持计划 | NLU Center 先调用它得到规则 plan，再做诊断汇总；planner 已注入公共 slot extractor | 不重复实现正式 query_key 裁决与参数回构 | 少量 query_key 专属参数回构仍保留在 planner 内 |
| `data_qa_service.py` | 正式查询执行、Guardrail 受控接入、澄清辅助、日志快照 | NLU Center 不直接接入执行链路，只作为未来可选诊断入口 | 不重复实现查询执行、结果解释和日志写入 | 后续如要落到主链路，需要只写入诊断字段而不改结果 |
| `logistics_903_master_ledger.json` | 903 题总账、状态、题族、回归标记、治理池 | NLU 文档和评测样本继承其 A/B/C 边界事实，当前自动抽取 C 类边界样本 | 不复制题库总账 | 后续可把 NLU 评测失败样本回写为治理标签 |
| C2A 配置与报告 | 旧 C 中迁入 A 的行为回归和精确断言批次 | 作为 A 类稳定样本来源和不回退基线，当前自动抽取 24 条进入 NLU 评测 | 不在 NLU v1 继续推进 C2A 批次 | 后续可按 query_key 覆盖率滚动扩大 |
| BCR 配置与报告 | B_candidate 澄清模板复检、缺口径槽位、业务化追问模板 | 作为 B 类澄清评测样本和 slot 命名来源，当前自动抽取 24 条进入 NLU 评测 | 不在 NLU v1 继续推进 BCR 批次 | 可把 BCR 中文 missing slots 映射为统一英文 slot 字典 |
| Top200 / TopN v2 产物 | 高频题路线图、阶段性 A/B/C 状态、下一批优先级 | 作为高价值 A 类和边界样本来源，当前自动抽取 Top200 8 条、TopN v2 7 条 | 不重新发起 Top200 / TopN 选择 | 后续按真实日志重选样本 |

## Intent 体系

| Intent | 含义 | 典型问题 | 当前落点 |
| --- | --- | --- | --- |
| `aggregate` | 聚合统计 | 总发运量、总运费、总车次、平均运费、单瓦成本 | 现有 `aggregate` query_key |
| `ranking` | 排名 | 承运商排名、客户排名、城市费用排名、签收率前后十 | 现有 `ranking` query_key |
| `comparison` | 对比 | 年度对比、月度对比、区域对比、计划实际偏差 | planner `compare` |
| `detail` | 明细/清单 | 任务明细、未建档任务、客户名单、映射缺口 | planner `detail_list` |
| `status_quality` | 状态/数据质量 | 签收率、填充率、解析成功率、映射缺口 | 状态质量 query_key |
| `clarification` | 需澄清 | 缺时间、缺指标、缺比较标准、缺异常定义 | response policy / planner |
| `unsupported` | 不支持 | 预测、ETA、风险评分、开放讨论、未固化明细原因 | response policy / planner |
| `multi_intent` | 多问题 | 一次问总量和排名、同时问统计和明细 | NLU v1 只识别结构，不执行多查询 |

## NLU Center 流程

1. 接收用户原始问题。
2. 读取 `logistics_nlu_normalization.json` 做术语归一和同义词命中记录。
3. 调用 `LogisticsDataQaPlanner.build_plan()` 获取正式规则 plan。
4. 调用 `LogisticsQuestionBankResponsePolicy.match()` 识别 B/C 边界证据。
5. 在不触碰 B/C 边界的前提下，对明显 A 类同构变体生成诊断型 query_key 候选。
6. 当 `use_llm=True` 且 LLM 配置可用时，调用 `LogisticsLlmUnderstandingService` 获取候选理解结果。
7. 调用 `LogisticsLlmUnderstandingGuardrailService.evaluate()` 获取影子决策摘要。
8. 输出统一 `LogisticsNluResult`。

## 统一收束后的能力边界

| 能力 | 统一入口 | 最终裁决者 | 当前模式 |
| --- | --- | --- | --- |
| 术语归一 | `logistics_nlu_normalization.json` + `LogisticsNluCenterService` | 正式 planner 仍按原问题裁决；NLU 只记录归一证据 | diagnostic |
| intent 识别 | `LogisticsNluCenterService` 汇总 planner / policy / query_key | `data_qa_planner` | diagnostic |
| slot 抽取 | `LogisticsSlotExtractor` 统一抽取，NLU Center 与 planner 共享 | `data_qa_planner` 执行态 filters | diagnostic |
| query_key 候选 | planner query_key + NLU 高置信候选 + LLM 候选 | Guardrail / planner | shadow |
| A 类同构变体增强 | Guardrail 白名单 | Guardrail + planner 回构 | shadow / assist 可控 |
| B 类缺口径识别 | response policy + BCR 缺口径 + LLM clarification assist | response policy / planner | 规则主导，LLM 只生成候选 |
| C 类边界识别 | response policy + 903 C 边界样本 | response policy / planner | 规则锁定 |
| 多问题拆解 | NLU Center | 暂不执行多个查询 | PoC diagnostic |
| 评测与审计 | `scripts/logistics_nlu_center_eval.py` | 报告只做诊断，不影响线上结果 | dry-run 默认 |

## LLM 角色

LLM 只能做：

- 语义理解候选；
- 术语归一候选；
- 槽位抽取候选；
- query_key 候选；
- 澄清问题草案。

LLM 不能做：

- 直接生成 SQL；
- 直接查数据库；
- 直接计算运费、发运量或车次；
- 替代正式 planner；
- 改写 B/C 最终边界。

## 当前不允许 LLM 接管的能力

- B 类是否澄清的最终判断；
- C 类是否拒答的最终判断；
- query_key 最终放行；
- SQL 生成；
- 数据库查询；
- 运费、发运量、车次等最终数值计算；
- 多问题执行编排；
- 903 总账状态迁移。

## v1 边界

- 当前默认是 shadow / diagnostic，不直接接管主链路。
- 多问题只识别和拆结构，不执行多个查询。
- 术语归一可给出候选 query_key，但正式查询仍必须走 planner / Guardrail。
- 如果命中 B/C 规则，NLU 不允许把问题改成 answerable。
- 真实 LLM 是否调用由配置和评测脚本参数控制，默认本地评测不调用 LLM。

## 统一输出 Schema

`LogisticsNluResult` 当前包含：

- `raw_question` / `normalized_question`
- `is_multi_intent` / `intent` / `sub_questions`
- `metrics` / `dimensions` / `filters` / `time_range` / `source_scope`
- `candidate_query_keys`
- `needs_clarification` / `missing_slots` / `clarification_questions`
- `unsupported` / `unsupported_reason`
- `confidence` / `nlu_source`
- `guardrail_decision` / `risk_flags`
- `normalized_terms`
- `rule_plan` / `llm_result`

该结构服务评测、诊断、后续审计和未来小流量 assist，不直接暴露给前端，也不直接驱动查询。

## 评测体系

当前评测不再只依赖 24 条人工样本，而是采用“人工种子样本 + 治理产物自动扩展”：

| 来源 | 数量 | 用途 |
| --- | ---: | --- |
| 人工种子样本 | 47 | 覆盖 A 标准题、A 变体、B、C、多问题、短问法、真实业务口吻 |
| C2A 精确断言样本 | 24 | 验证旧 C 迁入 A 后的 query_key / route 识别 |
| BCR 澄清样本 | 24 | 验证 B_candidate 缺口径识别和澄清边界 |
| 903 C 边界样本 | 12 | 验证预测、ETA、开放讨论、额外费用明细等拒答边界 |
| Top200 A 样本 | 8 | 验证高频高价值已收口 A 题 |
| TopN v2 A 样本 | 7 | 验证滚动重选后的高价值 A 题 |

合计 122 条，默认 dry-run，不真实调用 LLM。

## 当前仍分散、后续应收敛的逻辑

- `slot_extractor.py` 已抽取公共槽位能力，planner 与 NLU Center 已共享；后续需要按真实问法继续补充更多业务别名和复杂时间表达。
- 术语归一仍有少量安全替换写在 `nlu_center_service.py`，后续应完全迁入 `logistics_nlu_normalization.json`。
- BCR 的中文 missing slots 与 NLU 英文 slot 体系尚未完全一一映射。
- LLM understanding prompt 与 NLU slot schema 还不是同一份配置驱动，后续应减少重复维护。
- 多问题拆解目前只做连接词识别，尚未支持复杂嵌套问题和跨句上下文。
- NLU 评测目前以规则 dry-run 为基础，真实 LLM 抽样仍需单独打开 `--live-llm`，不能作为基础回归依赖。

## 产物

- Schema：`backend/app/domains/logistics/schemas/nlu.py`
- Service：`backend/app/domains/logistics/services/nlu_center_service.py`
- 术语归一配置：`backend/app/domains/logistics/config/logistics_nlu_normalization.json`
- 评测集：`backend/app/domains/logistics/config/logistics_nlu_center_eval_questions.json`
- 评测脚本：`scripts/logistics_nlu_center_eval.py`
- 评测报告：`tmp/logistics_question_bank/logistics_nlu_center_eval_report.json`
- 阶段文档：`docs/LOGISTICS_NLU_CENTER_V1.md`
