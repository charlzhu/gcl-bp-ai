# NQE-SQL-MAIN-3：多路召回机制设计与实现方案

## 0. 文档边界

本文是 NQE 统一 SQL Agent 正式主链路替换任务的第三张设计卡交付物。

本卡性质：

```text
只读设计卡；不写业务代码；不改前端；不新增数据库迁移；不创建真实表；不调用编码代理；不替换正式链路。
```

本卡事实源：

1. `ai/inbox/Hermes_NQE_统一SQLAgent最终执行指令_修正版.md`
2. `ai/inbox/NQE_统一SQLAgent正式主链路替换_最终报告_修正版.md`
3. `docs/NQE_SQL_MAIN_1_MAIN_LINK_DESIGN.md`
4. `docs/NQE_SQL_MAIN_2_METADATA_KB_DESIGN.md`
5. 当前仓库代码只读审计结果

明确排除：

1. `docs/CURRENT_STATUS.md`
2. `docs/NEXT_TASK.md`
3. `docs/HANDOFF.md`

上述三份通用状态文件当前记录物管 / SAP MID 并行任务，只读用于冲突判断，不作为 NQE 需求依据。

---

## 1. 当前仓库能力判断

### 1.1 已完成能力

只读审计确认当前仓库已经具备以下雏形能力：

1. 已存在统一 Graph 雏形，主线覆盖：接收问题、领域路由、关键词抽取、字段召回、指标召回、取值召回、合并、表过滤、指标过滤、上下文补充、SQL 生成、SQL 校验、SQL 修正、只读执行。
2. 物流域已有较成熟的语义目录、候选资产召回、评分排序、上下文拼装、影子评测和历史回归基础。
3. 统一语义目录层已有 Metric、Dimension、Entity、Capability 等结构，可作为 `nqe_*` 元数据表族的迁移参考。
4. 产销存 / 经营分析域已有部分业务语义资产，可沉淀为 NQE 指标、维度、业务口径和示例问法。
5. 计划 BOM 与功率预测已有确定性服务和部分领域能力，可作为后续 NQE 入口接入与 fallback 的基础。

### 1.2 未完成能力

当前仓库仍缺少正式 NQE 多路召回所需的关键能力：

1. 召回来源仍分散在领域代码、YAML、Python catalog、历史评测和临时服务中，尚未统一到 `nqe_*` 元数据知识库。
2. 当前召回主要是字段、指标、取值三路，尚未显式覆盖表、能力、示例问法、业务口径、join 路径、元数据版本和权限边界。
3. 当前召回缺少统一候选结构，无法在不同来源之间稳定合并、去重、排序、裁剪和审计。
4. 当前召回缺少逐路 score breakdown，难以定位为什么选中某张表、某个字段、某个指标或某个取值。
5. 当前召回缺少 `nqe_query_trace_step` 级别的结构化 trace，无法满足 replay、shadow compare 和质量门禁要求。
6. 当前 Graph 上下文拼装仍偏领域内实现，尚未形成统一 SQL Agent 可复用的上下文包。
7. 当前召回未绑定 `nqe_metadata_version`，后续难以复现同一问题在同一元数据版本下的输出。

### 1.3 本次任务与当前状态是否一致

一致。本卡只做设计，不写业务代码，重点补齐 NQE 多路召回的：

1. 输入结构。
2. 召回路径。
3. 候选来源。
4. 评分策略。
5. 合并去重。
6. 上下文裁剪。
7. trace 记录。
8. 后续实现卡边界。

### 1.4 本轮允许修改范围

仅允许新增或更新 NQE 独立文档：

1. `docs/NQE_SQL_MAIN_3_RETRIEVAL_DESIGN.md`
2. `docs/NQE_SQL_MAIN_CURRENT_STATUS.md`
3. `docs/NQE_SQL_MAIN_NEXT_TASK.md`
4. `docs/NQE_SQL_MAIN_HANDOFF.md`

### 1.5 本轮禁止修改范围

1. 不修改 `backend/` 业务代码。
2. 不修改 `frontend/` 代码。
3. 不新增 Alembic 迁移。
4. 不创建真实数据库表。
5. 不调用编码代理。
6. 不改正式问答链路。
7. 不覆盖物管 / SAP MID 的三份通用状态文件。
8. 不写入真实密钥、连接串、账号、Token 或内部凭证。

---

## 2. NQE 多路召回总体目标

NQE 多路召回的目标不是简单“多搜几个结果”，而是为 LLM 直接生成 SQL 提供一个可控、可审计、可复现的业务上下文包。

核心目标：

1. **不猜表**：只能从 active、白名单、权限允许的元数据资产中选择表。
2. **不猜字段**：只能使用召回并进入上下文的字段。
3. **不猜指标**：指标定义、聚合方式、单位、过滤规则必须来自元数据。
4. **不自由 join**：跨表关联只能来自登记的 join 资产。
5. **不越权取值**：字段取值召回必须走受控 value index，不做无界扫描。
6. **可解释**：每个候选为什么被召回、为什么被选中、为什么被丢弃都能在 trace 中看到。
7. **可复现**：每次查询绑定元数据版本、Prompt 版本、召回参数和候选摘要。
8. **可灰度**：物流先行，产销存 / 经营分析第二，计划 BOM 第三，功率预测第四。

---

## 3. 总体流程

NQE-SQL-MAIN-3 建议的多路召回流程如下：

```text
用户问题
  ↓
query normalize / keyword rewrite
  ↓
domain + capability recall
  ↓
并行多路召回：
  1. table recall
  2. column recall
  3. metric / dimension recall
  4. value / entity recall
  5. example question recall
  6. business rule recall
  7. join path recall
  8. time / unit / granularity recall
  ↓
候选标准化 CandidateEnvelope
  ↓
active / permission / domain / version / safety filter
  ↓
多路合并、交叉增益、冲突惩罚
  ↓
排序、裁剪、上下文预算分配
  ↓
RetrievalContextPackage
  ↓
写入 nqe_query_trace_step
  ↓
进入 NQE-SQL-MAIN-4 主 Graph 的 SQL 生成上下文
```

---

## 4. 查询标准化与关键词改写

### 4.1 输入

输入来自统一入口：

```text
question: 用户原始问题
session_context: 会话上下文，可为空
domain_hint: 前端或上游传入的业务域提示，可为空
user_context: 用户权限、组织、角色，可为空
metadata_version_hint: 元数据版本提示，可为空
```

### 4.2 输出

建议生成统一 `RetrievalQuery`：

| 字段 | 含义 |
|---|---|
| original_question | 用户原始问题 |
| normalized_question | 规范化后的问题 |
| domain_hints | 领域候选提示 |
| intent_hints | 意图候选提示，如统计、明细、对比、趋势、排名、缺口、预测入口 |
| keywords | 核心关键词 |
| expanded_keywords | LLM 或规则辅助扩展关键词 |
| entity_terms | 疑似实体词，如人名、基地、项目、客户、供应商、物料、月份 |
| metric_terms | 疑似指标词，如费用、车次、库存、产量、销量、功率 |
| time_terms | 时间表达，如年份、月份、区间、同比、环比 |
| numeric_terms | 数值条件，如前十、超过、低于、TopN |
| compare_terms | 对比对象，如两个年份、两个基地、两个客户 |
| metadata_version_id | 选定的元数据版本 |

### 4.3 关键词改写规则

1. 原始问题必须保留，不允许只用改写问题。
2. 改写词只用于召回，不直接进入用户可见回答。
3. 改写词必须写入 trace，便于复现。
4. 改写结果必须受业务域约束，不得扩展到未启用业务域。
5. 人名、基地、项目、供应商、客户等实体词应同时进入 value / entity recall。
6. 时间词应进入 time / granularity recall，不应混入普通字段召回。
7. 指标词应进入 metric / dimension recall，不应只靠字段名匹配。

---

## 5. 统一候选结构

所有召回路径输出统一 `CandidateEnvelope`，便于跨路合并和审计。

| 字段 | 类型 | 说明 |
|---|---|---|
| candidate_id | str | 候选唯一 ID，建议由 kind + asset_id 组成 |
| kind | str | table、column、metric、dimension、value、entity、example、rule、join、capability、time_grain |
| domain_id | str | 业务域 |
| capability_id | str | 能力 ID，可为空 |
| asset_id | str | 对应 `nqe_*` 资产主键或稳定唯一键 |
| display_name | str | 内部展示名，用户可见回答不得直接暴露 |
| source_table_ids | list | 涉及表 ID |
| source_column_ids | list | 涉及字段 ID |
| related_metric_ids | list | 关联指标 ID |
| related_rule_ids | list | 关联口径 ID |
| match_text | str | 命中的文本片段 |
| payload | dict | 资产摘要，不放密钥和真实连接信息 |
| score_total | float | 综合分 |
| score_breakdown | dict | 语义、词法、领域、结构、质量等分项 |
| evidence | list | 命中理由，如别名命中、示例命中、指标依赖命中 |
| risk_flags | list | 风险标记，如 restricted、ambiguous、missing_join |
| metadata_version_id | str | 元数据版本 |
| expires_at | datetime | 元数据有效期，可为空 |

设计原则：

1. 候选结构只承载召回事实，不承载最终 SQL。
2. 候选可以包含内部表名、字段名，但只用于后端 SQL 生成上下文和 trace，不得出现在用户可见回答。
3. `payload` 必须截断，避免把超长字段值、全量样例或敏感信息写入 trace。
4. 每个候选必须有 `score_breakdown`，不能只有总分。

---

## 6. 各路召回设计

### 6.1 Domain + Capability Recall

#### 目标

先确定问题可能属于哪个业务域和能力范围，避免后续召回跨域扩散。

#### 候选来源

1. `nqe_domain`
2. `nqe_capability`
3. 当前领域注册与能力注册配置
4. 历史评测用例中的域标签

#### 输入

1. 原始问题。
2. 规范化问题。
3. domain hint。
4. capability hint。
5. 用户权限。

#### 评分

| 分项 | 建议权重 | 说明 |
|---|---:|---|
| 领域关键词命中 | 0.25 | 业务域名称、别名、典型词 |
| 能力关键词命中 | 0.20 | 查询、对比、趋势、明细、预测入口等能力 |
| 示例问法相似度 | 0.20 | 与历史样例的语义相似度 |
| 元数据覆盖度 | 0.15 | 该域是否有可用表、字段、指标和规则 |
| 前端 / 上下文提示 | 0.10 | 由入口或会话提供的弱提示 |
| 权限可用性 | 0.10 | 用户是否可访问该域 |

#### 输出

输出 Top 1～3 个 domain/capability 候选。

#### Fallback

1. Top1 与 Top2 分差过小，进入澄清或 shadow 多域执行。
2. 领域分数低于阈值，返回“暂不支持/需要补充业务域”。
3. 能力未启用，直接走旧链路或业务化 fallback。

---

### 6.2 Table Recall

#### 目标

从当前业务域白名单中召回可能参与 SQL 的表。

#### 候选来源

1. `nqe_table_info`
2. `nqe_capability` 与表的能力绑定
3. `nqe_metric_info` 反向关联表
4. `nqe_dimension_info` 反向关联表
5. `nqe_example_question` 中沉淀的使用表
6. `nqe_join_info` 中被 join 路径连接的表

#### 输入

1. domain/capability 候选。
2. metric_terms。
3. entity_terms。
4. time_terms。
5. 示例召回结果。
6. 业务规则召回结果。

#### 评分

| 分项 | 建议权重 | 说明 |
|---|---:|---|
| 领域与能力匹配 | 0.25 | 表是否属于选中业务域和能力 |
| 指标依赖命中 | 0.25 | 召回指标是否依赖该表 |
| 字段 / 维度覆盖 | 0.20 | 问题中筛选、分组、排序条件是否可由表字段覆盖 |
| 示例问法支持 | 0.10 | 类似问题是否使用该表 |
| 业务规则支持 | 0.10 | 相关口径是否指向该表 |
| 元数据质量 | 0.10 | active、版本新鲜度、覆盖度、历史评测表现 |

#### 输出

每个表候选输出：

1. 表 ID。
2. 所属域和能力。
3. 业务说明。
4. 可用于 SQL 的字段 ID 列表。
5. 关联指标、维度、规则、join。
6. 是否事实表、维表、汇总表或宽表。

#### Fallback

1. 表候选为空：不得让 LLM 猜表，返回不支持或走旧链路。
2. 多表候选但无登记 join：只能选择单表路径，或进入澄清 / fallback。
3. 表被 restricted 或 inactive：不得进入上下文。

---

### 6.3 Column Recall

#### 目标

召回可用于 SELECT、WHERE、GROUP BY、ORDER BY 的字段。

#### 候选来源

1. `nqe_column_info`
2. `nqe_dimension_info`
3. `nqe_metric_info` 的指标依赖字段
4. `nqe_value_info` / `nqe_value_index` 的字段反查
5. `nqe_business_rule` 的字段依赖
6. 当前领域语义目录中的字段描述与别名

#### 输入

1. keywords。
2. entity_terms。
3. metric_terms。
4. time_terms。
5. table candidates。
6. value candidates。

#### 评分

| 分项 | 建议权重 | 说明 |
|---|---:|---|
| 字段业务名 / 别名命中 | 0.25 | 如“委托人”“基地”“月份”“客户”等 |
| 语义相似度 | 0.20 | 向量或文本相似 |
| 表候选支持 | 0.20 | 字段所属表是否已是高分表 |
| 取值反向支持 | 0.15 | 召回到的值是否属于该字段 |
| 指标 / 规则依赖 | 0.15 | 指标或口径是否依赖该字段 |
| 字段质量 | 0.05 | 类型、活跃、非敏感、示例覆盖 |

#### 输出

1. 字段 ID。
2. 字段名。
3. 字段业务名。
4. 数据类型。
5. 语义角色。
6. 所属表。
7. 示例值摘要。
8. 是否可过滤、可分组、可排序、可聚合。

#### Fallback

1. 字段候选不足时，不允许生成包含未召回字段的 SQL。
2. 时间字段不明确时，优先按业务域默认时间字段；无默认字段时澄清。
3. 人名、组织名等取值命中多个字段且分数接近时澄清。

---

### 6.4 Metric / Dimension Recall

#### 目标

召回业务指标、聚合口径、维度定义，避免 LLM 自行发明计算公式。

#### 候选来源

1. `nqe_metric_info`
2. `nqe_dimension_info`
3. `nqe_column_metric`
4. `nqe_business_rule`
5. 领域现有指标目录
6. 历史评测样例中的期望指标

#### 输入

1. metric_terms。
2. intent_hints。
3. domain/capability candidates。
4. table/column candidates。
5. example candidates。

#### 评分

| 分项 | 建议权重 | 说明 |
|---|---:|---|
| 指标业务名 / 别名命中 | 0.30 | 如费用、车次、库存、销量、产量、达成率 |
| 计算口径匹配 | 0.20 | 聚合函数、分子分母、单位是否匹配 |
| 领域和能力匹配 | 0.15 | 指标是否属于当前域和能力 |
| 示例问法支持 | 0.15 | 历史类似问题是否使用该指标 |
| 字段覆盖完整度 | 0.15 | 指标依赖字段是否都可用 |
| 质量门禁 | 0.05 | active、非废弃、评测稳定性 |

#### 输出

1. 指标 ID。
2. 指标业务名。
3. 指标说明。
4. 聚合方式。
5. 单位。
6. 分子 / 分母 / 过滤条件摘要。
7. 依赖字段。
8. 适用粒度。
9. 关联业务规则。

#### Fallback

1. 指标不存在或定义不完整：不得让 LLM 自行计算，应澄清或 fallback。
2. 多个指标别名相近：使用业务口径优先级；仍不明确时澄清。
3. 功率预测类问题：NQE 只识别入口和参数，预测计算交给确定性引擎。

---

### 6.5 Value / Entity Recall

#### 目标

召回字段取值和业务实体，用于 WHERE 条件、消歧和业务化说明。

#### 候选来源

1. `nqe_value_info`
2. `nqe_value_index`
3. `nqe_entity_info`
4. 领域 value resolver / entity resolver 的只读结果
5. 历史评测样例中的标准实体

#### 输入

1. entity_terms。
2. normalized_question。
3. domain/capability candidates。
4. table/column candidates。
5. 用户权限和数据范围。

#### 评分

| 分项 | 建议权重 | 说明 |
|---|---:|---|
| 精确匹配 | 0.30 | 完全相同、标准编码相同、别名相同 |
| 模糊匹配 | 0.20 | 编辑距离、拼音、简称等 |
| 字段适配 | 0.20 | 值是否属于高分字段 |
| 领域适配 | 0.10 | 值是否属于当前业务域 |
| 使用频率 / 新鲜度 | 0.10 | 近期同步、历史查询命中 |
| 消歧质量 | 0.10 | 候选是否唯一、是否存在多客户 / 多项目冲突 |

#### 输出

1. value ID。
2. 标准值。
3. 所属字段。
4. 所属表。
5. 实体类型。
6. 匹配词。
7. 分数。
8. 是否需要消歧。

#### 安全边界

1. 第一阶段只使用 MySQL value index。
2. 不对生产大表做无界 distinct 扫描。
3. 单次 value recall 必须有 topK、超时和字段白名单。
4. 敏感字段取值不得进入 Prompt 上下文。
5. trace 中只写候选摘要，不写超长值列表。

#### Fallback

1. 一个实体词命中多个业务字段，且无法根据上下文判断：澄清。
2. 取值数量过多：要求用户缩小条件。
3. value index 未构建：走旧链路或返回“当前维度值索引未就绪”。

---

### 6.6 Example Question Recall

#### 目标

通过历史高质量样例提供 SQL 生成模式和业务问法参考，但不 hardcode 答案。

#### 候选来源

1. `nqe_example_question`
2. 历史评测用例。
3. 已验收业务样例。
4. shadow compare 中验证通过的案例。

#### 输入

1. original_question。
2. normalized_question。
3. domain/capability candidates。
4. intent_hints。

#### 评分

| 分项 | 建议权重 | 说明 |
|---|---:|---|
| 问法语义相似度 | 0.35 | 与当前问题意图相似 |
| 领域一致性 | 0.20 | 同业务域同能力 |
| 指标 / 维度重合 | 0.20 | 使用相同指标、筛选、分组 |
| 评测通过质量 | 0.15 | 历史是否稳定通过 |
| 新鲜度 | 0.10 | 是否适配当前元数据版本 |

#### 输出

1. 示例 ID。
2. 示例问题摘要。
3. 领域、能力、指标、维度摘要。
4. 使用资产 ID 列表。
5. 生成 SQL 的结构提示。

#### 禁止事项

1. 不复制示例答案作为当前答案。
2. 不把示例中虚构或过期的业务对象当真实数据。
3. 不把示例 SQL 原样套用到当前问题，除非所有资产、条件、口径完全一致且通过安全验证。

---

### 6.7 Business Rule Recall

#### 目标

召回业务口径、默认规则、缺数据策略和展示策略，避免 SQL 结果被错误解释。

#### 候选来源

1. `nqe_business_rule`
2. `nqe_metric_info` 中的口径说明。
3. 当前项目已确认的业务规则记忆和文档。
4. 领域服务中已固化的确定性规则。

#### 输入

1. domain/capability candidates。
2. metric candidates。
3. column/value candidates。
4. intent_hints。

#### 评分

| 分项 | 建议权重 | 说明 |
|---|---:|---|
| 规则适用域 | 0.25 | 是否属于当前域和能力 |
| 指标 / 字段依赖 | 0.25 | 是否覆盖已选指标或字段 |
| 问题意图匹配 | 0.20 | 对比、趋势、达成率、缺数据等 |
| 规则优先级 | 0.15 | 用户确认规则高于一般规则 |
| 有效期和版本 | 0.15 | 是否 active、是否过期 |

#### 输出

1. rule ID。
2. 规则类型。
3. 适用域、能力、指标、字段。
4. 规则摘要。
5. SQL 约束提示。
6. 回答表达提示。
7. 缺数据或澄清策略。

#### 典型规则

1. 物流未给时间时，按业务确认范围默认覆盖 2023～2026 全部可用时间。
2. 物流“经营计划”优先映射业务口径中的扩充部门。
3. 物流人名优先映射委托人。
4. 物流线路运价均价按总费用除以车次数计算。
5. 产销存只使用已发布月份，未来月份不当实际数据。
6. 库存、存货、库存数据在当前业务口径中等价。
7. 功率预测计算由确定性引擎完成，NQE 不直接计算预测结果。

---

### 6.8 Join Path Recall

#### 目标

只从登记的 join 关系中选择跨表路径，防止 LLM 自由构造关联。

#### 候选来源

1. `nqe_join_info`
2. `nqe_table_info` 表关系摘要。
3. `nqe_column_info` 中主外键、分区键、时间键、业务键标记。
4. 历史通过评测的 join 路径。

#### 输入

1. selected table candidates。
2. selected metric candidates。
3. selected column candidates。
4. domain/capability candidates。

#### 评分

| 分项 | 建议权重 | 说明 |
|---|---:|---|
| 覆盖目标表 | 0.30 | 是否连接所有必要表 |
| join 类型可靠性 | 0.20 | 主外键、业务键、时间键的可靠程度 |
| 路径长度 | 0.15 | 路径越短越优先 |
| 评测历史 | 0.15 | 该路径是否通过历史评测 |
| 数据粒度一致性 | 0.15 | 是否会造成重复聚合或口径错误 |
| 有效期 | 0.05 | 是否 active 且版本匹配 |

#### 输出

1. join ID 或 join path ID。
2. 左右表 ID。
3. join 字段 ID。
4. join 类型。
5. 适用能力。
6. 粒度风险提示。
7. 是否允许进入 SQL 上下文。

#### Fallback

1. 需要多表但无登记 join：不得生成跨表 SQL。
2. join 可能造成重复聚合：优先使用汇总表或要求用户澄清粒度。
3. join 路径过长：优先走旧链路或返回不支持。

---

### 6.9 Time / Unit / Granularity Recall

#### 目标

识别时间字段、粒度、单位、默认周期和展示口径。

#### 候选来源

1. `nqe_column_info` 中时间字段标记。
2. `nqe_metric_info` 中指标粒度和单位。
3. `nqe_business_rule` 中默认时间规则。
4. 领域服务中已有日期口径。

#### 输入

1. time_terms。
2. metric candidates。
3. table/column candidates。
4. business rule candidates。

#### 输出

1. 时间字段候选。
2. 时间粒度：日、月、年、区间、已发布月份等。
3. 默认时间范围。
4. 单位和换算策略。
5. 是否需要澄清。

#### Fallback

1. 时间字段多候选且业务规则无法判断：澄清。
2. 指标要求月度但数据只有年度：业务化说明缺数据。
3. 单位不一致且无法换算：澄清或返回不可比。

---

## 7. 召回过滤策略

所有候选进入合并前必须先过滤。

### 7.1 强制过滤

以下候选必须直接丢弃：

1. `active=false`。
2. 元数据版本不匹配且不可兼容。
3. 已过期。
4. 超出用户权限。
5. 表、字段、指标被标记 restricted 且当前链路无授权。
6. 不属于当前候选业务域。
7. 不属于当前灰度模式允许的能力。
8. 指向外部实时生产源且当前链路禁止直查。
9. 字段或表缺少白名单注册。

### 7.2 软性降权

以下情况不直接丢弃，但降低分数：

1. 只被一个弱关键词命中。
2. 没有示例问法支持。
3. 没有业务规则支持。
4. 与高分候选存在粒度冲突。
5. 历史评测不稳定。
6. 元数据同步时间较旧。
7. 候选需要跨表 join 且路径较长。

---

## 8. 合并、去重、排序、裁剪

### 8.1 合并原则

1. 以 `kind + asset_id + metadata_version_id` 作为稳定去重键。
2. 同一资产被多路命中时保留最高分，并累加 evidence。
3. 指标命中应反向增强依赖字段和表。
4. 取值命中应反向增强所属字段和表。
5. 示例命中应增强其使用过的表、字段、指标、规则。
6. 业务规则命中应增强其覆盖的指标和字段。
7. join 命中只增强已被表 / 指标 / 字段共同支持的路径。

### 8.2 综合评分

建议统一综合分：

```text
score_total = semantic_score * 0.25
            + lexical_score * 0.20
            + domain_score * 0.15
            + structural_score * 0.15
            + rule_score * 0.10
            + example_score * 0.10
            + freshness_score * 0.05
            - risk_penalty
```

其中：

| 分项 | 含义 |
|---|---|
| semantic_score | 语义相似度或向量相似度 |
| lexical_score | 关键词、别名、精确值命中 |
| domain_score | 业务域和能力一致性 |
| structural_score | 表字段指标 join 结构完整度 |
| rule_score | 业务口径支持度 |
| example_score | 高质量样例支持度 |
| freshness_score | 元数据版本和同步新鲜度 |
| risk_penalty | 歧义、缺 join、权限、粒度冲突等惩罚 |

### 8.3 上下文预算

为控制 Prompt 长度，建议第一阶段默认预算：

| 类型 | 默认 TopK | 说明 |
|---|---:|---|
| domain / capability | 1～3 | 通常只选 Top1，低置信时保留 Top2 用于澄清 |
| table | 3～5 | 优先事实表、宽表、汇总表 |
| column | 30～60 | 按表分组，每表限制数量 |
| metric | 5～12 | 只保留与问题相关指标 |
| dimension | 10～20 | 只保留筛选、分组、排序相关维度 |
| value / entity | 10～30 | 每字段限制数量，歧义时保留候选用于澄清 |
| example | 3～6 | 只保留高质量模式样例 |
| business rule | 5～10 | 高优先级规则必须保留 |
| join path | 3～5 | 仅保留可执行候选路径 |
| time / unit | 3～8 | 只保留当前问题必要项 |

### 8.4 冲突处理

| 冲突类型 | 处理方式 |
|---|---|
| 多领域高分 | 触发澄清或 shadow 多域评估 |
| 多指标同义但口径不同 | 优先用户确认规则；否则澄清 |
| 同一实体匹配多个字段 | 使用上下文和领域规则；仍不确定则澄清 |
| 多表均可回答 | 优先宽表 / 汇总表；保留事实表作为 trace 候选 |
| 需要 join 但 join 未登记 | 禁止生成跨表 SQL，走 fallback |
| 粒度不一致 | 优先同粒度表；必要时返回业务化缺数据说明 |
| 时间范围缺失 | 使用领域默认规则；无默认则澄清 |

---

## 9. RetrievalContextPackage 设计

多路召回最终输出统一上下文包，供 SQL 生成节点使用。

### 9.1 顶层结构

```text
RetrievalContextPackage
  metadata_version_id
  prompt_version_id
  question
  normalized_question
  selected_domain
  selected_capability
  selected_tables
  selected_columns
  selected_metrics
  selected_dimensions
  selected_values
  selected_rules
  selected_examples
  selected_join_paths
  time_context
  unit_context
  constraints
  clarification_hints
  fallback_hints
  trace_refs
```

### 9.2 SQL 生成上下文规则

1. 只把 selected 资产放入 SQL 生成上下文。
2. 不把被过滤或低分候选放入 SQL 生成上下文。
3. 对每张表只提供必要字段，不提供全 schema。
4. 对每个指标提供定义、单位、聚合口径和依赖字段。
5. 对每个字段标记是否可过滤、可分组、可排序、可聚合。
6. 对字段取值只提供当前问题必要候选。
7. 对 join 只提供允许的 join path。
8. 对业务规则只提供与当前问题相关的规则摘要。
9. 如果上下文不足以安全生成 SQL，应进入澄清或 fallback，不允许 LLM 猜测。

### 9.3 用户可见边界

NQE 内部上下文可以包含表、字段、指标和 SQL 生成依据，但用户可见回答不得暴露：

1. SQL。
2. 表名。
3. 字段名。
4. query key。
5. planner / guardrail / schema / raw / debug / LLM 等内部技术内容。
6. trace 原文。

---

## 10. Trace 设计

### 10.1 写入位置

每一路召回必须写入 `nqe_query_trace_step`。

建议 step_code：

1. `normalize_query`
2. `recall_domain_capability`
3. `recall_table`
4. `recall_column`
5. `recall_metric_dimension`
6. `recall_value_entity`
7. `recall_example`
8. `recall_business_rule`
9. `recall_join_path`
10. `recall_time_unit_grain`
11. `merge_retrieval_candidates`
12. `build_retrieval_context`

### 10.2 每步 trace 字段

| 字段 | 说明 |
|---|---|
| trace_id | 查询 trace ID |
| step_code | 步骤编码 |
| metadata_version_id | 元数据版本 |
| input_digest | 输入摘要，不写敏感原文 |
| params | topK、阈值、域、灰度模式等参数 |
| candidate_count | 原始候选数量 |
| selected_count | 选中候选数量 |
| candidate_summary | 截断后的候选摘要 |
| score_summary | 分数分布和分项摘要 |
| dropped_summary | 丢弃原因统计 |
| warnings | 歧义、缺 join、缺指标、缺权限等警告 |
| latency_ms | 步骤耗时 |
| status | success、fallback、clarify、error |

### 10.3 安全要求

1. trace 不写密钥、连接串、真实账号。
2. trace 不写超长字段取值列表。
3. trace 不写未脱敏敏感字段值。
4. trace 可以写内部资产 ID，但用户可见回答不得展示。
5. trace 必须支持 replay：同一 trace 能找回当时元数据版本、Prompt 版本、召回参数和 SQL 修订记录。

---

## 11. 分业务域召回特例

### 11.1 物流域

物流域作为第一替换域，召回设计必须优先保留现有稳定能力。

重点：

1. 默认时间口径按已确认业务规则处理。
2. 人名、部门、基地、线路、客户、承运商等实体优先进入 value / entity recall。
3. 运价、费用、车次、均价等指标必须从业务口径召回，不允许 LLM 自行计算。
4. 年度对比必须保留无匹配年份空值行的业务口径。
5. 旧物流链路必须保留 fallback，直到 shadow 和 on 模式验收通过。

### 11.2 产销存 / 经营分析域

重点：

1. 月度、年度、已发布月份是召回重点。
2. 产量、销量、库存、预算达成率等指标必须绑定业务口径。
3. 缺数据策略必须从业务规则召回。
4. 不得把未来月份当实际数据。
5. 库存周转率等缺关键数据时，优先业务化反问。

### 11.3 计划 BOM 域

重点：

1. BOM 单号、评审号、文件名、客户实例、版本等必须进入 entity recall。
2. 消歧逻辑必须通用，不能针对单个案例 hardcode。
3. 配置搭配、物料明细、供应商、项目等字段必须由元数据和确定性服务支撑。
4. 候选过多时优先澄清，不能混入不相关客户实例。
5. 旧计划 BOM 服务保留 fallback。

### 11.4 功率预测子能力

重点：

1. 功率预测属于计划 BOM 子能力，不单独扩业务域。
2. NQE 可召回预测入口、参数、BOM 上下文和历史结果说明。
3. 实际功率档位、比例、供应商效率、匹配度等计算必须由确定性引擎负责。
4. 若用户请求预测计算，SQL Agent 只负责查找上下文和调用 fallback，不直接让 LLM 算。

---

## 12. 与后续看板卡的承接关系

### 12.1 承接 NQE-SQL-MAIN-4

NQE-SQL-MAIN-4 需要基于本文设计主 Graph：

1. normalize query 节点。
2. domain/capability recall 节点。
3. 多路并行召回节点。
4. merge retrieval 节点。
5. build context 节点。
6. SQL generation 节点。
7. SQL safety precheck 节点。
8. EXPLAIN / validate 节点。
9. correct loop。
10. execute / answer / fallback 节点。

### 12.2 承接 NQE-SQL-MAIN-6

NQE-SQL-MAIN-6 创建 `nqe_*` 数据库迁移时，应按本文召回需求优先保证以下表字段可用：

1. `nqe_table_info`
2. `nqe_column_info`
3. `nqe_metric_info`
4. `nqe_dimension_info`
5. `nqe_entity_info`
6. `nqe_value_info`
7. `nqe_join_info`
8. `nqe_business_rule`
9. `nqe_example_question`
10. `nqe_retrieval_chunk`
11. `nqe_retrieval_index`
12. `nqe_value_index`
13. `nqe_query_trace_step`
14. `nqe_metadata_version`

### 12.3 承接 NQE-SQL-MAIN-8

NQE-SQL-MAIN-8 负责元数据向量索引。

本文要求向量索引只作为召回加速和语义匹配来源，主事实仍以 MySQL `nqe_*` 元数据表为准。

### 12.4 承接 NQE-SQL-MAIN-9

NQE-SQL-MAIN-9 负责 value index。

本文要求 value index：

1. 有字段白名单。
2. 有 topK 和超时。
3. 有脱敏策略。
4. 有同步任务记录。
5. 不做生产大表无界扫描。

---

## 13. 后续实现建议

后续编码卡建议按以下粒度拆分：

1. 定义 NQE 召回实体 Pydantic schema。
2. 实现 `RetrievalQuery` 标准化。
3. 实现 domain/capability recall。
4. 实现 table recall。
5. 实现 column recall。
6. 实现 metric/dimension recall。
7. 实现 value/entity recall。
8. 实现 example/rule recall。
9. 实现 join/time/unit recall。
10. 实现 candidate merge/rank/prune。
11. 实现 context package builder。
12. 实现 trace step writer。
13. 编写 focused tests。
14. 接入 shadow 模式。

每个编码卡都必须先写 RED 测试，再实现，再跑 focused/full 回归，并保留旧链路 fallback。

---

## 14. 验收标准

NQE-SQL-MAIN-3 完成应满足：

1. 已形成多路召回总体流程。
2. 已定义统一候选结构。
3. 已覆盖 domain、capability、table、column、metric、dimension、value、entity、example、rule、join、time/unit/grain。
4. 已说明每一路输入、候选来源、评分、输出、fallback。
5. 已说明合并、去重、排序、裁剪策略。
6. 已说明 SQL 生成上下文包结构。
7. 已说明 trace 写入方式。
8. 已说明四类接入域的召回特例。
9. 已明确 NQE-SQL-MAIN-4、6、8、9 的承接边界。
10. 未修改业务代码。
11. 未覆盖物管 / SAP MID 状态文件。
12. 文档未写入外部参考项目名称。
13. 文档未写入密钥、账号、连接串或其他敏感凭证。

---

## 15. 当前结论

NQE-SQL-MAIN-3 的设计结论是：统一 SQL Agent 的召回层必须从“三路召回雏形”升级为“元数据版本绑定的多路召回 + 候选标准化 + 评分解释 + 合并裁剪 + 上下文包 + trace/replay”的完整底座。

在该设计落地前，不应把 LLM 直接生成 SQL 接到正式用户链路；即使进入 shadow，也必须先保证候选资产来自白名单元数据，并且每次召回可追溯、可复现、可回滚。
