# NQE-SQL-MAIN-2：统一元数据知识库表设计

> 本文是 NQE 统一 SQL Agent 正式主链路替换任务的第二阶段设计产物。  
> 任务范围：只读审计与表族设计，不修改业务代码、不创建迁移、不替换正式链路、不调用编码代理。  
> 上游依据：`docs/NQE_SQL_MAIN_1_MAIN_LINK_DESIGN.md`、`docs/NQE_SQL_MAIN_ARCHITECTURE.md`、`docs/NQE_SQL_MAIN_SAFETY_BOUNDARY.md`、本轮 NQE 主执行指令与主需求报告。  
> 下游承接：NQE-SQL-MAIN-3 多路召回机制设计、NQE-SQL-MAIN-6 nqe_* 元数据表 Alembic 迁移。

---

## 一、设计结论

NQE 统一 SQL Agent 需要一套独立的 `nqe_*` 元数据知识库表族，统一承接物流、产销存 / 经营分析、计划 BOM、功率预测四域的表、字段、指标、维度、业务取值、关联关系、示例问法、业务口径、Prompt 版本、召回片段、运行 trace、shadow compare 和评测集。

本阶段设计结论如下：

1. **元数据知识库必须落在当前 MySQL 中间库**，不能依赖代码常量、散落 YAML 或单域 Python catalog 作为运行期唯一事实源。
2. **NQE 主链路只允许从 nqe_* 白名单资产中构造 SQL 上下文**，禁止让 LLM 猜表、猜字段、猜指标。
3. **知识库分五层表族**：基础资产层、语义资产层、召回资产层、运行审计层、评测治理层。
4. **字段取值索引第一阶段使用 MySQL value index**，后续可在不改主表结构的前提下增加专门检索引擎。
5. **向量检索只保存索引指针和 embedding 版本信息**，主事实仍以 MySQL nqe_* 表为准。
6. **每条元数据必须具备 domain、source、version、status、is_active、effective_time 和 audit 字段**，保证分域灰度、回滚和追溯。
7. **trace / replay / shadow compare 不进入用户可见输出**，只用于内部审计、回归和灰度决策。
8. **功率预测不直接 SQL 化确定性计算**；NQE 只负责统一入口、参数/模型/取值查询和调用确定性 fallback 的元数据描述。

---

## 二、现有资产对照

### 2.1 已具备但分散的资产

当前仓库已具备以下可复用资产形态：

| 类型 | 现状 | NQE 设计吸收方式 |
|---|---|---|
| 统一能力配置 | 已有统一能力注册 YAML | 同步到 `nqe_capability`、`nqe_business_rule`、`nqe_example_question` |
| 语义指标 / 维度 / 实体 | 已有 Pydantic 结构定义 | 同步到 `nqe_metric_info`、`nqe_dimension_info`、`nqe_entity_info` |
| 物流 NL2SQL catalog | 已有单域表、字段、指标、示例和规则 | 作为物流首域元数据同步源 |
| 产销存 / 经营分析 catalog | 已有库存、销售、生产相关语义资产 | 作为第二域元数据同步源 |
| 计划 BOM / 功率预测 | 有业务服务、映射配置、确定性计算引擎，但 catalog 化不足 | 新增元数据映射和 fallback 能力描述 |
| 查询日志 | 已有 `sys_query_log` | NQE 新增独立 trace 表并可关联旧日志 |
| 评测运行器 | 已有评测集和泄露检查思路 | NQE 统一沉淀评测 suite/case/run/result |
| shadow compare | 已有部分对比能力 | NQE 统一沉淀 shadow 对比结果 |

### 2.2 当前缺口

1. 缺少统一 `nqe_*` 落库事实源。
2. 缺少四域共享的表 / 字段 / 指标 / 维度 / 取值关系模型。
3. 缺少可被多路召回统一消费的 chunk 表和索引状态表。
4. 缺少 SQL 生成、修正、EXPLAIN、执行过程的结构化 trace 明细。
5. 缺少统一的 shadow compare 和 replay 数据模型。
6. 缺少元数据版本、发布、回滚、灰度状态字段。

---

## 三、表族分层总览

```text
基础资产层
  nqe_domain
  nqe_data_source
  nqe_capability
  nqe_table_info
  nqe_column_info

语义资产层
  nqe_metric_info
  nqe_dimension_info
  nqe_entity_info
  nqe_column_metric
  nqe_value_info
  nqe_join_info
  nqe_business_rule
  nqe_example_question
  nqe_prompt_version

召回资产层
  nqe_retrieval_chunk
  nqe_retrieval_index
  nqe_value_index

运行审计层
  nqe_query_trace
  nqe_query_trace_step
  nqe_sql_revision
  nqe_shadow_compare

评测治理层
  nqe_eval_suite
  nqe_eval_case
  nqe_eval_run
  nqe_eval_result
  nqe_metadata_version
  nqe_metadata_sync_job
  nqe_quality_gate
```

后续 NQE-SQL-MAIN-6 做 Alembic 迁移时，可按上述层级拆成 2～3 个迁移文件，避免单次迁移过大。

---

## 四、统一字段规范

除特殊关系表外，所有主表建议统一包含以下字段：

| 字段 | 类型建议 | 说明 |
|---|---|---|
| `id` | bigint 自增 | 内部主键 |
| `code` | varchar(128) | 稳定业务编码，同域内唯一或全局唯一 |
| `domain_code` | varchar(64) | 所属业务域：logistics / business_analysis / plan_bom / plan_power / material_management 等 |
| `name` | varchar(255) | 中文业务名称 |
| `description` | text | 内部说明，禁止写入密钥或连接串 |
| `source_type` | varchar(64) | 来源类型：manual / yaml / python_catalog / db_introspection / eval / runtime 等 |
| `source_ref` | varchar(512) | 来源引用，如配置路径或同步任务编号；不得包含真实密钥 |
| `version` | varchar(64) | 元数据版本号 |
| `status` | varchar(32) | draft / active / disabled / deprecated |
| `is_active` | tinyint | 当前是否启用 |
| `effective_from` | datetime | 生效时间 |
| `effective_to` | datetime nullable | 失效时间 |
| `created_by` | varchar(64) | 创建来源或系统账号 |
| `updated_by` | varchar(64) | 更新来源或系统账号 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |
| `extra_json` | json/text | 扩展字段，存储非关键元信息 |

约束：

1. `status='active' AND is_active=1` 的记录才能进入线上召回上下文。
2. `effective_to IS NULL OR effective_to > NOW()` 的记录才可被运行期使用。
3. 任何 `extra_json` 不得保存 API Key、Token、密码、连接串、真实主机或用户凭证。

---

## 五、基础资产层设计

### 5.1 `nqe_domain`

用途：登记 NQE 支持的业务域、灰度模式和域级安全边界。

核心字段：

| 字段 | 说明 |
|---|---|
| `code` | 业务域编码，如 `logistics`、`business_analysis`、`plan_bom`、`plan_power` |
| `display_name` | 业务展示名，如物流、经营分析、计划 BOM、功率预测 |
| `domain_order` | 域路由优先级 |
| `gray_mode` | off / shadow / assist / on |
| `fallback_service` | fallback 能力标识，仅内部使用 |
| `max_result_rows` | 域级最大返回行数 |
| `default_limit_rows` | 明细默认 LIMIT |
| `allow_direct_sql` | 是否允许进入 NQE SQL 生成执行链路 |
| `risk_level` | low / medium / high |

唯一约束：

```text
uniq_nqe_domain_code(code)
```

索引建议：

```text
idx_nqe_domain_active(is_active, status, gray_mode)
```

数据来源：NQE 手工初始化 + 后续配置同步。

---

### 5.2 `nqe_data_source`

用途：登记 NQE 可查询的数据源、逻辑库和只读执行配置边界。该表只保存安全占位或逻辑引用，不保存真实连接信息。

核心字段：

| 字段 | 说明 |
|---|---|
| `code` | 数据源编码 |
| `domain_code` | 默认业务域 |
| `source_kind` | mysql / oracle_sync_mid / csv_import / model_table 等逻辑类型 |
| `logical_name` | 逻辑名称 |
| `readonly_required` | 是否强制只读 |
| `connection_ref` | 配置引用名，不保存真实连接串 |
| `allow_explain` | 是否支持 EXPLAIN |
| `timeout_ms` | 查询超时 |
| `max_rows` | 最大返回行数 |

唯一约束：

```text
uniq_nqe_data_source_code(code)
```

风险说明：

1. 不得保存真实 host、user、password、DSN、Token。
2. 外部同步源只能作为同步来源或受控工具来源，用户问答不得直接越过中间库实时查询。

---

### 5.3 `nqe_capability`

用途：描述每个业务域可支持的问数能力，如聚合查询、明细查询、对比查询、候选消歧、功率预测 fallback。

核心字段：

| 字段 | 说明 |
|---|---|
| `code` | 能力编码 |
| `domain_code` | 所属业务域 |
| `capability_type` | aggregate / detail / compare / disambiguation / deterministic_tool / fallback |
| `intent_names` | 支持意图列表 JSON |
| `required_slots` | 必填参数 JSON |
| `optional_slots` | 可选参数 JSON |
| `supported_modes` | off / shadow / assist / on 支持列表 |
| `fallback_required` | 是否必须保留 fallback |
| `fallback_reason` | 必须 fallback 的业务原因 |

唯一约束：

```text
uniq_nqe_capability_domain_code(domain_code, code)
```

数据来源：统一能力配置、领域服务审计结果、后续人工维护。

---

### 5.4 `nqe_table_info`

用途：登记可被 SQL Agent 使用的白名单业务表、视图或中间库表。

核心字段：

| 字段 | 说明 |
|---|---|
| `code` | NQE 表编码，建议不直接等同物理表名 |
| `domain_code` | 所属业务域 |
| `data_source_code` | 数据源编码 |
| `physical_table_name` | 实际表名，仅内部 trace 使用，不进入用户可见回答 |
| `business_name` | 业务名称 |
| `table_role` | fact / dimension / bridge / model / snapshot / log_safe |
| `grain` | 数据粒度，如单票、订单、月度、BOM 行、功率模型版本 |
| `time_column_code` | 默认时间字段编码 |
| `owner_capability_code` | 主要能力编码 |
| `row_count_level` | small / medium / large / huge，用于安全预检 |
| `allow_select` | 是否允许 SELECT |
| `allow_detail` | 是否允许明细查询 |
| `default_limit_rows` | 明细默认 LIMIT |
| `max_limit_rows` | 最大 LIMIT |
| `sensitive_level` | normal / internal / restricted |

唯一约束：

```text
uniq_nqe_table_domain_code(domain_code, code)
uniq_nqe_table_physical(data_source_code, physical_table_name)
```

索引建议：

```text
idx_nqe_table_domain_active(domain_code, is_active, status)
idx_nqe_table_capability(domain_code, owner_capability_code)
```

安全规则：

1. `allow_select=1` 且 `sensitive_level != restricted` 才可进入 SQL 生成上下文。
2. 系统库、权限、用户、密钥、调度和敏感日志表不得登记为可查询业务表。

---

### 5.5 `nqe_column_info`

用途：登记字段级元数据，支撑字段召回、SQL 生成和技术泄露过滤。

核心字段：

| 字段 | 说明 |
|---|---|
| `table_code` | 所属 NQE 表编码 |
| `column_code` | NQE 字段编码 |
| `physical_column_name` | 实际字段名，仅内部使用 |
| `business_name` | 中文业务名 |
| `data_type` | string / number / date / datetime / boolean / decimal 等 |
| `semantic_type` | time / amount / count / category / entity / measure / status |
| `is_primary_key` | 是否主键或业务唯一键 |
| `is_time_key` | 是否时间字段 |
| `is_filterable` | 是否允许作为过滤条件 |
| `is_groupable` | 是否允许分组 |
| `is_aggregatable` | 是否允许聚合 |
| `allowed_aggregations` | sum / count / avg / min / max 等 JSON |
| `unit` | 单位 |
| `synonyms_json` | 同义词、业务别名 |
| `sample_values_json` | 安全样例值，不含敏感信息 |
| `value_index_enabled` | 是否进入字段取值索引 |
| `sensitive_level` | normal / internal / restricted |

唯一约束：

```text
uniq_nqe_column_table_code(table_code, column_code)
uniq_nqe_column_physical(table_code, physical_column_name)
```

索引建议：

```text
idx_nqe_column_domain_semantic(domain_code, semantic_type)
idx_nqe_column_filterable(domain_code, is_filterable, is_active)
idx_nqe_column_value_index(domain_code, value_index_enabled, is_active)
```

安全规则：

1. `sensitive_level='restricted'` 的字段不得进入 Prompt 上下文。
2. 用户可见回答不得展示 `physical_column_name`。
3. LLM 生成 SQL 只能使用经过召回和白名单过滤后的物理字段。

---

## 六、语义资产层设计

### 6.1 `nqe_metric_info`

用途：登记统一指标，支撑指标召回、指标过滤、SQL 聚合表达和业务口径追溯。

核心字段：

| 字段 | 说明 |
|---|---|
| `metric_code` | 指标编码 |
| `domain_code` | 所属业务域 |
| `business_name` | 业务指标名称 |
| `metric_type` | count / amount / ratio / rate / distribution / deterministic_result |
| `grain` | 指标粒度 |
| `unit` | 单位 |
| `default_aggregation` | sum / count / avg / custom |
| `formula_text` | 内部公式说明，不直接暴露用户 |
| `sql_expression_template` | 受控 SQL 表达模板，后续实现可选 |
| `base_table_code` | 默认事实表 |
| `time_dimension_code` | 默认时间维度 |
| `synonyms_json` | 同义词和问法 |
| `required_filters_json` | 必要过滤条件 |
| `quality_note` | 数据质量说明 |
| `fallback_required` | 是否需要确定性 fallback |

唯一约束：

```text
uniq_nqe_metric_domain_code(domain_code, metric_code)
```

典型映射：

1. 物流：车次、费用、重量、线路均价等。
2. 产销存 / 经营分析：产量、销量、库存、预算达成率等。
3. 计划 BOM：BOM 行数、物料用量、候选版本数量等。
4. 功率预测：中心功率、功率档分布等标记为 `deterministic_result`，由确定性引擎计算。

---

### 6.2 `nqe_dimension_info`

用途：登记统一维度，支撑 group by、筛选、对比和结果展示。

核心字段：

| 字段 | 说明 |
|---|---|
| `dimension_code` | 维度编码 |
| `domain_code` | 业务域 |
| `business_name` | 维度名称 |
| `dimension_type` | time / geography / org / customer / product / material / supplier / status |
| `table_code` | 默认来源表 |
| `column_code` | 默认字段 |
| `hierarchy_json` | 层级，如年-月-日、省-市 |
| `synonyms_json` | 同义词 |
| `default_sort` | 默认排序 |
| `is_disambiguation_key` | 是否可用于候选消歧 |

唯一约束：

```text
uniq_nqe_dimension_domain_code(domain_code, dimension_code)
```

---

### 6.3 `nqe_entity_info`

用途：登记业务实体，统一承接人名、客户、订单、BOM 文件、版型、供应商、物料等可被识别和消歧的对象。

核心字段：

| 字段 | 说明 |
|---|---|
| `entity_code` | 实体类型编码 |
| `domain_code` | 所属业务域 |
| `entity_type` | person / customer / order / bom_file / model_code / supplier / material / warehouse |
| `business_name` | 业务名称 |
| `primary_table_code` | 主表 |
| `primary_column_code` | 主字段 |
| `alias_columns_json` | 可用于别名匹配的字段 |
| `disambiguation_strategy` | exact / fuzzy / multi_candidate / fallback |
| `clarification_template` | 多候选时澄清文案模板 |

唯一约束：

```text
uniq_nqe_entity_domain_type(domain_code, entity_type)
```

设计说明：

1. 计划 BOM 的文件名、评审号、客户实例、订单号都应作为实体/消歧对象沉淀。
2. 功率预测的版型、供应商、配置项也应作为实体对象沉淀。
3. 物流中人名、部门、线路、客户等应通过实体映射减少误解。

---

### 6.4 `nqe_column_metric`

用途：登记字段与指标的组成关系，说明某指标依赖哪些字段、字段在指标中的角色。

核心字段：

| 字段 | 说明 |
|---|---|
| `metric_code` | 指标编码 |
| `table_code` | 表编码 |
| `column_code` | 字段编码 |
| `role` | numerator / denominator / filter / group_key / time_key / measure |
| `aggregation` | sum / count / avg / custom |
| `required` | 是否必需 |
| `note` | 业务说明 |

唯一约束：

```text
uniq_nqe_column_metric(metric_code, table_code, column_code, role)
```

用途示例：线路均价可描述为总费用字段与车次数字段的组合，避免误用明细行平均值。

---

### 6.5 `nqe_value_info`

用途：登记高频字段取值、业务别名、标准化值，支撑字段取值召回和参数归一化。

核心字段：

| 字段 | 说明 |
|---|---|
| `value_code` | 取值编码 |
| `domain_code` | 业务域 |
| `table_code` | 表编码 |
| `column_code` | 字段编码 |
| `raw_value` | 原始值 |
| `normalized_value` | 标准化值 |
| `display_value` | 业务展示值 |
| `aliases_json` | 别名、简称、历史叫法 |
| `pinyin_key` | 可选拼音或首字母辅助键 |
| `value_freq` | 出现频次 |
| `last_seen_at` | 最近出现时间 |
| `quality_status` | verified / inferred / stale |

唯一约束：

```text
uniq_nqe_value_column_norm(table_code, column_code, normalized_value)
```

索引建议：

```text
idx_nqe_value_lookup(domain_code, column_code, normalized_value)
idx_nqe_value_freq(domain_code, column_code, value_freq)
```

数据来源：

1. 中间库字段小样本 / distinct 安全抽样。
2. 人工维护的别名和业务映射。
3. 历史问答高频取值沉淀。

安全规则：

1. 不同步敏感字段取值。
2. 大表 distinct 必须受限、分批、审计，不允许全量无界扫描。
3. 原始值含个人敏感信息时必须脱敏或不入库。

---

### 6.6 `nqe_join_info`

用途：登记表关联关系，支撑 SQL 生成时选择可控 join 路径。

核心字段：

| 字段 | 说明 |
|---|---|
| `join_code` | 关联编码 |
| `domain_code` | 所属业务域 |
| `left_table_code` | 左表 |
| `right_table_code` | 右表 |
| `join_type` | inner / left / one_to_many_guarded |
| `join_condition_json` | 字段关联条件结构化描述 |
| `cardinality` | one_to_one / one_to_many / many_to_one / many_to_many |
| `risk_level` | low / medium / high |
| `allowed_for_detail` | 是否允许明细查询使用 |
| `allowed_for_aggregate` | 是否允许聚合查询使用 |
| `fanout_warning` | 是否存在放大行数风险 |

唯一约束：

```text
uniq_nqe_join_code(domain_code, join_code)
```

安全规则：

1. 未登记 join 关系不得由 LLM 自由构造跨表关联。
2. `many_to_many` 或高风险 join 默认只能 shadow，不可直接 on。
3. 计划 BOM、功率预测存在版本/模型类表时，必须显式登记版本维度和 active 约束。

---

### 6.7 `nqe_business_rule`

用途：登记业务口径、缺省规则、反问策略、不可 SQL 化规则和用户可见表达边界。

核心字段：

| 字段 | 说明 |
|---|---|
| `rule_code` | 规则编码 |
| `domain_code` | 业务域 |
| `rule_type` | calculation / default_filter / ambiguity / safety / fallback / presentation |
| `title` | 规则标题 |
| `rule_text` | 业务口径说明 |
| `applies_to_json` | 适用指标、维度、能力 |
| `priority` | 优先级 |
| `requires_clarification` | 是否触发反问 |
| `fallback_required` | 是否必须走 fallback |
| `visible_to_user` | 是否可转换为业务说明展示 |

唯一约束：

```text
uniq_nqe_rule_domain_code(domain_code, rule_code)
```

典型规则：

1. 用户未给时间时的默认时间范围。
2. 物流均价按总费用除以车次数，而非明细平均。
3. 功率预测计算必须由确定性引擎完成。
4. 缺数据时需要业务化反问，不能编造。

---

### 6.8 `nqe_example_question`

用途：登记示例问法、预期意图、关联资产和期望行为，支撑示例召回与评测集生成。

核心字段：

| 字段 | 说明 |
|---|---|
| `example_code` | 示例编码 |
| `domain_code` | 业务域 |
| `question_text` | 示例问题 |
| `normalized_intent` | 标准意图 |
| `linked_metrics_json` | 关联指标 |
| `linked_dimensions_json` | 关联维度 |
| `linked_tables_json` | 关联表 |
| `linked_rules_json` | 关联口径 |
| `expected_behavior` | success / clarification / unsupported / fallback |
| `source_type` | manual / eval / historical_query |
| `is_eval_candidate` | 是否可转评测用例 |

唯一约束：

```text
uniq_nqe_example_domain_code(domain_code, example_code)
```

说明：示例问法用于帮助理解业务表达，不得 hardcode 答案。

---

### 6.9 `nqe_prompt_version`

用途：登记 NQE 各节点 Prompt 版本，支撑 trace、回放和灰度对比。

核心字段：

| 字段 | 说明 |
|---|---|
| `prompt_code` | Prompt 编码，如 domain_route、generate_sql、correct_sql |
| `prompt_version` | 版本号 |
| `domain_code` | 可选业务域；为空表示全局 |
| `node_name` | 对应节点名称 |
| `content_hash` | Prompt 内容 hash |
| `storage_ref` | Prompt 文件或配置引用 |
| `enabled_modes_json` | 支持模式 |
| `change_note` | 变更说明 |
| `approved_by` | 审核人或系统 |

唯一约束：

```text
uniq_nqe_prompt_version(prompt_code, prompt_version, domain_code)
```

安全规则：Prompt 内容可存 hash 和引用，正文是否落库由后续实现卡决定；如果落库，必须防止包含密钥和外部参考项目名称。

---

## 七、召回资产层设计

### 7.1 `nqe_retrieval_chunk`

用途：把表、字段、指标、维度、取值、示例、规则等元数据转换成可召回文本片段。

核心字段：

| 字段 | 说明 |
|---|---|
| `chunk_code` | chunk 编码 |
| `domain_code` | 业务域 |
| `asset_type` | table / column / metric / dimension / value / example / rule / capability |
| `asset_id` | 对应资产主键 |
| `asset_code` | 对应资产编码 |
| `chunk_text` | 召回文本 |
| `keywords_json` | 关键词 |
| `synonyms_json` | 同义词 |
| `embedding_model` | embedding 模型版本 |
| `embedding_hash` | chunk 文本 hash |
| `index_status` | pending / indexed / failed / disabled |
| `last_indexed_at` | 最近索引时间 |

唯一约束：

```text
uniq_nqe_chunk_asset(domain_code, asset_type, asset_code, embedding_hash)
```

索引建议：

```text
idx_nqe_chunk_domain_type(domain_code, asset_type, index_status)
idx_nqe_chunk_asset(domain_code, asset_code)
```

说明：运行期可以先从 MySQL 读取召回候选，也可以通过向量索引返回 chunk_code 后再回查 MySQL 主事实。

---

### 7.2 `nqe_retrieval_index`

用途：登记向量索引、全文索引、关键词索引等召回索引状态。该表只保存索引元信息，不作为元数据事实源。

核心字段：

| 字段 | 说明 |
|---|---|
| `index_code` | 索引编码 |
| `domain_code` | 业务域 |
| `index_type` | vector / keyword / value |
| `asset_type` | 索引资产类型 |
| `collection_name` | 逻辑集合名 |
| `embedding_model` | embedding 模型 |
| `metadata_version` | 对应元数据版本 |
| `build_status` | pending / running / success / failed |
| `chunk_count` | chunk 数量 |
| `last_build_at` | 最近构建时间 |
| `error_message` | 失败原因，需脱敏 |

唯一约束：

```text
uniq_nqe_retrieval_index(index_code, metadata_version)
```

---

### 7.3 `nqe_value_index`

用途：字段取值索引主表，第一阶段用 MySQL 支撑精确/模糊取值召回。

核心字段：

| 字段 | 说明 |
|---|---|
| `domain_code` | 业务域 |
| `table_code` | 表编码 |
| `column_code` | 字段编码 |
| `normalized_value` | 标准化取值 |
| `display_value` | 展示值 |
| `match_text` | 用于 LIKE / 分词匹配的文本 |
| `aliases_text` | 别名拼接文本 |
| `freq` | 频次 |
| `quality_score` | 质量评分 |
| `source_snapshot` | 来源快照或同步批次 |

唯一约束：

```text
uniq_nqe_value_index(domain_code, table_code, column_code, normalized_value)
```

索引建议：

```text
idx_nqe_value_index_match(domain_code, column_code, match_text)
idx_nqe_value_index_freq(domain_code, column_code, freq)
```

说明：`nqe_value_info` 偏业务事实与别名治理，`nqe_value_index` 偏运行检索性能，两者通过 domain/table/column/normalized_value 对齐。

---

## 八、运行审计层设计

### 8.1 `nqe_query_trace`

用途：记录一次 NQE 问数请求的总览信息，支撑 query log、replay、shadow compare 和灰度观测。

核心字段：

| 字段 | 说明 |
|---|---|
| `trace_id` | 请求追踪 ID |
| `session_id` | 会话 ID，可选 |
| `user_question` | 原始问题，可按安全策略脱敏 |
| `domain_code` | 最终业务域 |
| `gray_mode` | off / shadow / assist / on |
| `route_status` | success / clarify / unsupported / error |
| `final_status` | success / empty_result / clarification / fallback / error |
| `selected_tables_json` | 选中表编码 |
| `selected_metrics_json` | 选中指标编码 |
| `selected_values_json` | 解析取值 |
| `final_sql_hash` | 最终 SQL hash |
| `result_row_count` | 结果行数 |
| `latency_ms` | 总耗时 |
| `fallback_used` | 是否使用 fallback |
| `old_query_log_id` | 可选关联旧日志 |
| `error_code` | 错误码 |
| `error_message` | 脱敏错误信息 |

唯一约束：

```text
uniq_nqe_query_trace(trace_id)
```

索引建议：

```text
idx_nqe_trace_domain_time(domain_code, created_at)
idx_nqe_trace_status(final_status, created_at)
idx_nqe_trace_mode(gray_mode, created_at)
```

安全规则：

1. trace 可记录内部 SQL hash 和脱敏摘要，是否保存完整 SQL 由安全策略控制。
2. 用户可见回答不得暴露 trace 中的内部技术字段。

---

### 8.2 `nqe_query_trace_step`

用途：记录一次 NQE 请求每个节点的输入摘要、输出摘要、状态和耗时。

核心字段：

| 字段 | 说明 |
|---|---|
| `trace_id` | 请求追踪 ID |
| `step_order` | 节点顺序 |
| `node_name` | 节点名称，如 domain_route、recall_metrics、generate_sql、explain_validate |
| `step_status` | running / success / skipped / error |
| `input_summary_json` | 输入摘要，需脱敏 |
| `output_summary_json` | 输出摘要，需脱敏 |
| `prompt_code` | 使用的 Prompt 编码 |
| `prompt_version` | Prompt 版本 |
| `latency_ms` | 节点耗时 |
| `error_message` | 脱敏错误 |

唯一约束：

```text
uniq_nqe_trace_step(trace_id, step_order, node_name)
```

用途：为 replay 和问题定位提供可审计链路。

---

### 8.3 `nqe_sql_revision`

用途：记录 LLM 生成 SQL、预检、EXPLAIN、错误修正、最终执行的迭代过程。

核心字段：

| 字段 | 说明 |
|---|---|
| `trace_id` | 请求追踪 ID |
| `revision_no` | SQL 版本序号，0 为初版 |
| `sql_hash` | SQL hash |
| `sql_text_redacted` | 可选脱敏 SQL 文本；生产可只存 hash 和摘要 |
| `generation_reason` | generated / corrected / fallback |
| `safety_status` | pass / blocked |
| `safety_block_reason` | 拦截原因 |
| `explain_status` | pass / failed / skipped |
| `explain_summary_json` | EXPLAIN 摘要 |
| `db_error_message` | 脱敏数据库错误 |
| `correction_prompt_version` | 修正 Prompt 版本 |
| `is_final` | 是否最终采用 |

唯一约束：

```text
uniq_nqe_sql_revision(trace_id, revision_no)
```

安全规则：

1. SQL 文本保存策略必须由 NQE-SQL-MAIN-5 安全设计最终确认。
2. 即使保存 SQL，也只允许内部审计查看，不进入用户可见输出。
3. 所有错误信息必须脱敏，不得包含连接串、账号、主机或密钥。

---

### 8.4 `nqe_shadow_compare`

用途：记录新 NQE 链路与旧链路 / fallback 链路的 shadow 对比结果。

核心字段：

| 字段 | 说明 |
|---|---|
| `trace_id` | 请求追踪 ID |
| `domain_code` | 业务域 |
| `new_status` | NQE 结果状态 |
| `old_status` | 旧链路结果状态 |
| `new_row_count` | NQE 行数 |
| `old_row_count` | 旧链路行数 |
| `key_metric_diff_json` | 关键指标差异 |
| `answer_diff_summary` | 回答差异摘要 |
| `compare_status` | match / warning / mismatch / not_comparable |
| `risk_level` | low / medium / high |
| `review_required` | 是否需人工复核 |
| `review_note` | 复核意见 |

唯一约束：

```text
uniq_nqe_shadow_trace(trace_id)
```

用途：支持四域灰度从 shadow → assist → on 的准入判断。

---

## 九、评测治理层设计

### 9.1 `nqe_eval_suite`

用途：登记评测套件，按域、阶段、用途组织评测集。

核心字段：

| 字段 | 说明 |
|---|---|
| `suite_code` | 评测套件编码 |
| `domain_code` | 业务域 |
| `suite_type` | focused / regression / shadow / acceptance / safety |
| `baseline_version` | 基线版本 |
| `case_count` | 用例数量 |
| `pass_threshold` | 通过阈值 |
| `leak_check_enabled` | 是否启用技术泄露检查 |

唯一约束：

```text
uniq_nqe_eval_suite(suite_code, baseline_version)
```

---

### 9.2 `nqe_eval_case`

用途：登记单条评测用例。

核心字段：

| 字段 | 说明 |
|---|---|
| `suite_code` | 所属套件 |
| `case_code` | 用例编码 |
| `domain_code` | 业务域 |
| `question_text` | 问题文本 |
| `expected_status` | success / empty_result / clarification / unsupported / fallback / error |
| `expected_metrics_json` | 期望指标 |
| `expected_row_count` | 期望行数，可空 |
| `expected_answer_keywords_json` | 期望业务关键词 |
| `forbidden_keywords_json` | 禁止泄露关键词 |
| `linked_assets_json` | 关联元数据资产 |
| `case_source` | manual / example / historical_query / bugfix |

唯一约束：

```text
uniq_nqe_eval_case(suite_code, case_code)
```

---

### 9.3 `nqe_eval_run`

用途：记录一次评测运行。

核心字段：

| 字段 | 说明 |
|---|---|
| `run_code` | 运行编码 |
| `suite_code` | 套件编码 |
| `metadata_version` | 使用的元数据版本 |
| `prompt_versions_json` | 使用的 Prompt 版本 |
| `code_version` | 代码版本或 commit |
| `total_cases` | 总用例数 |
| `passed_cases` | 通过数 |
| `failed_cases` | 失败数 |
| `pass_rate` | 通过率 |
| `run_status` | running / success / failed / aborted |
| `started_at` | 开始时间 |
| `finished_at` | 结束时间 |

唯一约束：

```text
uniq_nqe_eval_run(run_code)
```

---

### 9.4 `nqe_eval_result`

用途：记录单条评测结果，关联 trace 以便回放。

核心字段：

| 字段 | 说明 |
|---|---|
| `run_code` | 运行编码 |
| `case_code` | 用例编码 |
| `trace_id` | 对应 NQE trace |
| `actual_status` | 实际状态 |
| `matched_status` | 状态是否匹配 |
| `key_numbers_match` | 关键数字是否匹配 |
| `leak_found` | 是否有技术泄露 |
| `mismatch_detail` | 差异说明 |
| `result_payload_json` | 结果摘要 |

唯一约束：

```text
uniq_nqe_eval_result(run_code, case_code)
```

---

### 9.5 `nqe_metadata_version`

用途：管理元数据版本、发布、回滚与灰度。

核心字段：

| 字段 | 说明 |
|---|---|
| `metadata_version` | 版本号 |
| `domain_code` | 业务域，可为 global |
| `version_status` | draft / published / rolled_back / archived |
| `source_summary_json` | 来源摘要 |
| `asset_counts_json` | 各类资产数量 |
| `quality_score` | 质量评分 |
| `publish_note` | 发布说明 |
| `published_by` | 发布人或系统 |
| `published_at` | 发布时间 |
| `rollback_from` | 回滚来源版本 |

唯一约束：

```text
uniq_nqe_metadata_version(domain_code, metadata_version)
```

用途：每次元数据同步、人工修订或发布，都可生成新版本，确保可回滚。

---

### 9.6 `nqe_metadata_sync_job`

用途：记录元数据同步任务，包括从 YAML、Python catalog、数据库 introspection、评测集、历史查询等来源同步到 nqe_* 表。

核心字段：

| 字段 | 说明 |
|---|---|
| `job_code` | 同步任务编码 |
| `domain_code` | 业务域 |
| `source_type` | yaml / python_catalog / db_introspection / historical_query / manual_import |
| `target_version` | 目标元数据版本 |
| `job_status` | pending / running / success / failed |
| `started_at` | 开始时间 |
| `finished_at` | 结束时间 |
| `created_count` | 新增数 |
| `updated_count` | 更新数 |
| `disabled_count` | 禁用数 |
| `error_message` | 脱敏错误信息 |

唯一约束：

```text
uniq_nqe_metadata_sync_job(job_code)
```

---

### 9.7 `nqe_quality_gate`

用途：记录元数据、召回、SQL 安全、评测、shadow compare 的准入门禁结果。

核心字段：

| 字段 | 说明 |
|---|---|
| `gate_code` | 门禁编码 |
| `domain_code` | 业务域 |
| `gate_type` | metadata / retrieval / sql_safety / eval / shadow / release |
| `metadata_version` | 元数据版本 |
| `gate_status` | pass / warning / failed / blocked |
| `summary` | 门禁摘要 |
| `details_json` | 详细结果 |
| `required_for_on` | 是否是 on 模式必需门禁 |
| `checked_at` | 检查时间 |

唯一约束：

```text
uniq_nqe_quality_gate(gate_code, metadata_version)
```

---

## 十、核心关系图

```text
nqe_domain
  ├─ nqe_capability
  ├─ nqe_data_source
  ├─ nqe_table_info
  │    └─ nqe_column_info
  │         ├─ nqe_value_info
  │         └─ nqe_value_index
  ├─ nqe_metric_info
  │    └─ nqe_column_metric
  ├─ nqe_dimension_info
  ├─ nqe_entity_info
  ├─ nqe_join_info
  ├─ nqe_business_rule
  ├─ nqe_example_question
  ├─ nqe_prompt_version
  ├─ nqe_retrieval_chunk
  │    └─ nqe_retrieval_index
  ├─ nqe_query_trace
  │    ├─ nqe_query_trace_step
  │    ├─ nqe_sql_revision
  │    └─ nqe_shadow_compare
  └─ nqe_eval_suite
       ├─ nqe_eval_case
       └─ nqe_eval_run
            └─ nqe_eval_result

nqe_metadata_version
  ├─ nqe_metadata_sync_job
  └─ nqe_quality_gate
```

---

## 十一、运行期调用路径

### 11.1 领域识别

1. 从 `nqe_domain` 读取启用域和灰度模式。
2. 从 `nqe_capability`、`nqe_example_question`、`nqe_business_rule` 读取领域描述和示例。
3. 领域识别结果写入 `nqe_query_trace`。

### 11.2 多路召回

| 召回类型 | 主要表 |
|---|---|
| 表召回 | `nqe_table_info`、`nqe_retrieval_chunk` |
| 字段召回 | `nqe_column_info`、`nqe_retrieval_chunk` |
| 指标召回 | `nqe_metric_info`、`nqe_column_metric`、`nqe_retrieval_chunk` |
| 维度召回 | `nqe_dimension_info`、`nqe_retrieval_chunk` |
| 取值召回 | `nqe_value_info`、`nqe_value_index` |
| 示例召回 | `nqe_example_question`、`nqe_retrieval_chunk` |
| 口径召回 | `nqe_business_rule`、`nqe_retrieval_chunk` |
| 关联召回 | `nqe_join_info` |

每路召回结果写入 `nqe_query_trace_step` 的脱敏摘要，供回放和调优使用。

### 11.3 SQL 生成上下文构造

1. 只允许使用 `active` 且 `is_active=1` 的表、字段、指标、join、规则。
2. 只允许加入 `sensitive_level != restricted` 的字段。
3. join 必须来自 `nqe_join_info`。
4. 指标计算优先使用 `nqe_metric_info` + `nqe_column_metric` 的定义。
5. Prompt 版本从 `nqe_prompt_version` 读取或记录引用。

### 11.4 SQL 安全与执行追踪

1. 初始 SQL 写入 `nqe_sql_revision` revision 0。
2. 安全预检结果写入 `nqe_sql_revision.safety_status`。
3. EXPLAIN 结果写入 `nqe_sql_revision.explain_status`。
4. 修正 SQL 继续新增 revision，最多次数由 NQE-SQL-MAIN-5 确认。
5. 最终结果摘要写入 `nqe_query_trace`。

### 11.5 shadow compare 与评测

1. shadow 模式同时运行旧链路和 NQE 链路。
2. 对比结果写入 `nqe_shadow_compare`。
3. 批量回归写入 `nqe_eval_run`、`nqe_eval_result`。
4. 发布准入写入 `nqe_quality_gate`。

---

## 十二、四域适配策略

### 12.1 物流

优先级：第一接入域。

元数据来源：

1. 物流 NL2SQL 语义 catalog。
2. 物流历史回归问题集。
3. 物流问答日志与 shadow 数据。
4. 统一能力配置。

必须沉淀：

1. 物流事实表、字段、时间字段、费用/车次/重量等指标。
2. 部门、人名、线路、客户、承运商等取值和别名。
3. 物流均价等关键业务口径。
4. 旧链路 fallback 能力描述。

风险：字段取值量可能较大，value index 必须分批、限量、可审计。

### 12.2 产销存 / 经营分析

优先级：第二接入域。

元数据来源：

1. 现有库存、销售、生产语义资产。
2. 指标口径文档和业务确认规则。
3. 历史问答 / 评测样例。

必须沉淀：

1. 产量、销量、库存、预算达成率等指标。
2. 年月、产品、事业部、库存口径等维度。
3. 未发布月份、缺数据、平均库存等反问规则。
4. 旧服务 fallback 能力描述。

风险：年度/月份口径、预算达成率和库存周转等计算需要严格业务规则，不允许 LLM 编造。

### 12.3 计划 BOM

优先级：第三接入域。

元数据来源：

1. BOM 相关服务和模型。
2. BOM 候选消歧逻辑。
3. BOM 回归测试与样例问题。

必须沉淀：

1. BOM 文件、评审号、订单号、客户实例、版本、物料等实体。
2. 候选消歧字段和澄清模板。
3. BOM 明细表和关键字段。
4. compare / replay fallback 能力描述。

风险：BOM 文档中的历史样例不能 hardcode；候选消歧必须通用。

### 12.4 功率预测

优先级：第四接入域。

元数据来源：

1. 功率模型版本、模型页、供应商效率分布、配置项映射。
2. 功率预测确定性引擎的输入/输出结构。
3. 功率模型校验用例。

必须沉淀：

1. 版型、供应商、配置项、标板、效率段等实体和取值。
2. 功率预测相关指标标记为 `deterministic_result`。
3. PowerPredictionEngine fallback 能力描述。
4. 模型版本 active 约束和校验状态。

风险：中心功率、效率段、功率档分布必须由确定性引擎计算，NQE 不得让 LLM 直接计算业务事实。

---

## 十三、索引与约束策略

### 13.1 必选唯一约束

1. 所有 `code` 类主资产必须同域唯一。
2. 表物理名在同数据源内唯一。
3. 字段物理名在同表内唯一。
4. 指标、维度、实体、规则、示例在同域内唯一。
5. trace_id 全局唯一。
6. eval run_code 全局唯一。

### 13.2 必选检索索引

1. `(domain_code, is_active, status)`：所有运行期主资产。
2. `(domain_code, asset_type, index_status)`：召回 chunk。
3. `(domain_code, column_code, normalized_value)`：字段取值。
4. `(domain_code, created_at)`：trace 和评测历史。
5. `(metadata_version, gate_status)`：发布门禁。

### 13.3 JSON 字段使用边界

允许放入 JSON 的内容：

1. 同义词、别名。
2. 适用资产列表。
3. 非关键展示配置。
4. 脱敏摘要。

不允许仅放入 JSON、必须结构化成列的内容：

1. 业务域。
2. 表编码。
3. 字段编码。
4. 指标编码。
5. active/status/version。
6. trace_id。
7. 安全状态和评测状态。

---

## 十四、NQE-SQL-MAIN-6 Alembic 迁移建议

NQE-SQL-MAIN-6 应只做迁移和 ORM 模型，不实现同步脚本或业务链路。

建议迁移拆分：

1. `nqe_core_metadata`：domain、data_source、capability、table、column。
2. `nqe_semantic_metadata`：metric、dimension、entity、column_metric、value、join、rule、example、prompt。
3. `nqe_runtime_governance`：retrieval、trace、sql_revision、shadow、eval、metadata_version、sync_job、quality_gate。

推荐 scoped 文件范围：

```text
backend/app/models/nqe_metadata.py
backend/app/models/nqe_runtime.py
backend/app/schemas/nqe_metadata.py
backend/alembic/versions/*_create_nqe_metadata_tables.py
```

验收标准：

1. Alembic upgrade / downgrade 可运行。
2. 所有表名均为 `nqe_*`。
3. 不写入业务代码调用链。
4. 不影响现有物流、计划 BOM、功率预测、产销存接口。
5. 不保存真实连接信息或密钥。
6. ORM / migration 有中文注释说明核心业务用途。

---

## 十五、NQE-SQL-MAIN-3 承接要求

NQE-SQL-MAIN-3 多路召回机制设计必须基于本文表族继续细化：

1. 每一路召回读取哪些表。
2. 召回输入、输出和评分字段。
3. 多路召回如何合并、去重、排序。
4. 如何利用 `nqe_retrieval_chunk` 和 `nqe_value_index`。
5. 如何在召回层过滤 inactive、过期、restricted、高风险 join。
6. 如何把召回结果写入 trace。
7. 如何为 NQE-SQL-MAIN-8、9 分别承接向量索引和 MySQL value index。

---

## 十六、验收结论

NQE-SQL-MAIN-2 的设计验收口径：

1. 已设计 `nqe_*` 元数据知识库表族。
2. 已覆盖表、字段、指标、维度、实体、取值、join、示例问法、业务口径、Prompt、召回 chunk、value index、trace、SQL revision、shadow compare、评测、元数据版本、同步任务和质量门禁。
3. 已明确主键、唯一约束、索引、数据来源、四域适配、运行期调用路径和安全边界。
4. 已明确后续 NQE-SQL-MAIN-3 与 NQE-SQL-MAIN-6 的承接方式。
5. 本文档仅为设计文档，未修改业务代码，未创建数据库迁移，未替换正式链路。
