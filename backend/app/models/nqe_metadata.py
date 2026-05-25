from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, declarative_mixin, mapped_column

from backend.app.db.base import Base

# 说明：生产库使用 BigInteger；SQLite 结构测试需要 INTEGER 主键才能稳定自增。
NQE_ID_TYPE = BigInteger().with_variant(Integer, "sqlite")


@declarative_mixin
class NqeIdMixin:
    """NQE 表统一技术主键。"""

    id: Mapped[int] = mapped_column(NQE_ID_TYPE, primary_key=True, autoincrement=True, comment="技术主键")


@declarative_mixin
class NqeRequiredDomainMixin:
    """需要明确归属业务域的 NQE 元数据列。"""

    domain_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="业务域编码")


@declarative_mixin
class NqeOptionalDomainMixin:
    """运行审计或治理记录可延迟补齐业务域。"""

    domain_code: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="业务域编码")


@declarative_mixin
class NqeSourceMixin:
    """记录逻辑来源，禁止保存真实连接串或密钥。"""

    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="来源类型")
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="来源引用，不保存真实连接串")


@declarative_mixin
class NqeLifecycleMixin:
    """NQE 元数据发布、启停与审计通用字段。"""

    version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1", comment="元数据版本标签")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", comment="状态：draft/published/disabled")
    is_active: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, comment="是否启用")
    effective_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="生效开始时间")
    effective_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="生效结束时间")
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="创建人")
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="更新人")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )
    extra_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="扩展属性 JSON 字符串")


class NqeDomain(NqeIdMixin, NqeSourceMixin, NqeLifecycleMixin, Base):
    """NQE 业务域元数据表。

    用途：
        保存统一 SQL Agent 可识别的业务域白名单和展示名称。
    """

    __tablename__ = "nqe_domain"
    __table_args__ = (
        UniqueConstraint("code", name="uk_nqe_domain_code"),
        UniqueConstraint("domain_code", name="uk_nqe_domain_domain_code"),
        {"comment": "NQE 业务域元数据表"},
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False, comment="稳定编码")
    domain_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="业务域编码")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="业务域名称")
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="用户侧展示名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="业务域说明")


class NqeDataSource(NqeIdMixin, NqeRequiredDomainMixin, NqeSourceMixin, NqeLifecycleMixin, Base):
    """NQE 数据源白名单表。

    重要边界：
        connection_ref 只保存逻辑配置引用，不保存真实连接身份或地址。
    """

    __tablename__ = "nqe_data_source"
    __table_args__ = (
        UniqueConstraint("code", name="uk_nqe_data_source_code"),
        Index("idx_nqe_data_source_domain", "domain_code"),
        {"comment": "NQE 数据源白名单表"},
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False, comment="数据源稳定编码")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="数据源名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="数据源说明")
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False, comment="数据源类别：middle_db/oracle/mysql/file 等")
    logical_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="逻辑名称")
    readonly_required: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, comment="是否强制只读")
    connection_ref: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="连接配置逻辑引用，不保存密钥")
    allow_explain: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, comment="是否允许 EXPLAIN")
    timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=30000, comment="查询超时时间毫秒")
    max_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=1000, comment="最大返回行数")


class NqeTableInfo(NqeIdMixin, NqeRequiredDomainMixin, NqeSourceMixin, NqeLifecycleMixin, Base):
    """NQE 查询表白名单与语义说明表。"""

    __tablename__ = "nqe_table_info"
    __table_args__ = (
        UniqueConstraint("code", name="uk_nqe_table_info_code"),
        Index("idx_nqe_table_info_domain", "domain_code"),
        Index("idx_nqe_table_info_source", "data_source_code"),
        {"comment": "NQE 查询表白名单与语义说明表"},
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False, comment="表稳定编码")
    data_source_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="数据源编码")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="表业务名称")
    business_name: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="业务别名")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="表说明")
    physical_table_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="物理表名，仅供后端白名单使用")
    table_role: Mapped[str] = mapped_column(String(64), nullable=False, comment="表角色：fact/dim/ods/dwd/dws/dm")
    grain: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="数据粒度说明")
    allow_select: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, comment="是否允许查询")
    allow_detail: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否允许明细查询")
    default_limit_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=100, comment="默认返回行数")
    max_limit_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=1000, comment="最大返回行数")
    sensitive_level: Mapped[str] = mapped_column(String(64), nullable=False, default="normal", comment="敏感等级")


class NqeColumnInfo(NqeIdMixin, NqeRequiredDomainMixin, NqeSourceMixin, NqeLifecycleMixin, Base):
    """NQE 查询字段白名单与语义说明表。"""

    __tablename__ = "nqe_column_info"
    __table_args__ = (
        UniqueConstraint("code", name="uk_nqe_column_info_code"),
        UniqueConstraint("table_code", "column_code", name="uk_nqe_column_table_column"),
        Index("idx_nqe_column_info_table", "table_code"),
        Index("idx_nqe_column_info_domain", "domain_code"),
        {"comment": "NQE 查询字段白名单与语义说明表"},
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False, comment="字段稳定编码")
    table_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="表编码")
    column_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="字段编码")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="字段业务名称")
    business_name: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="字段业务别名")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="字段说明")
    physical_column_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="物理字段名，仅供后端白名单使用")
    data_type: Mapped[str] = mapped_column(String(128), nullable=False, comment="数据类型")
    semantic_type: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="语义类型：time/entity/amount/status 等")
    is_filterable: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否可过滤")
    is_groupable: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否可分组")
    is_aggregatable: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否可聚合")
    allowed_aggregations: Mapped[str | None] = mapped_column(Text, nullable=True, comment="允许聚合函数 JSON 字符串")
    sensitive_level: Mapped[str] = mapped_column(String(64), nullable=False, default="normal", comment="敏感等级")
    sample_values_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="字段安全样例值 JSON 字符串")
    value_index_enabled: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否允许构建字段取值索引")
    synonyms_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="字段同义词 JSON 字符串")
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="字段单位")


class NqeValueInfo(NqeIdMixin, NqeRequiredDomainMixin, NqeSourceMixin, NqeLifecycleMixin, Base):
    """NQE 字段取值资产表。

    用途：
        保存允许索引字段的标准化取值，供后续 value recall 使用。
    """

    __tablename__ = "nqe_value_info"
    __table_args__ = (
        UniqueConstraint("code", name="uk_nqe_value_info_code"),
        UniqueConstraint("table_code", "column_code", "normalized_value", name="uk_nqe_value_info_table_column_value"),
        Index("idx_nqe_value_info_domain_column_value", "domain_code", "column_code", "normalized_value"),
        Index("idx_nqe_value_info_domain_column_freq", "domain_code", "column_code", "value_freq"),
        {"comment": "NQE 字段取值资产表"},
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False, comment="取值稳定编码")
    table_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="表编码")
    column_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="字段编码")
    value_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="取值编码")
    raw_value: Mapped[str] = mapped_column(String(512), nullable=False, comment="原始取值")
    normalized_value: Mapped[str] = mapped_column(String(256), nullable=False, comment="标准化取值")
    display_value: Mapped[str] = mapped_column(String(512), nullable=False, comment="展示取值")
    aliases_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="取值别名 JSON 字符串")
    pinyin_key: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="拼音或缩写检索键")
    value_freq: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="取值出现频次")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最近观察时间")
    quality_status: Mapped[str] = mapped_column(String(32), nullable=False, default="trusted", comment="质量状态")


class NqeValueIndex(NqeIdMixin, NqeRequiredDomainMixin, NqeSourceMixin, NqeLifecycleMixin, Base):
    """NQE 字段取值检索索引表。

    用途：
        保存面向精确、别名、包含匹配的轻量索引文本，不查询业务明细表。
    """

    __tablename__ = "nqe_value_index"
    __table_args__ = (
        UniqueConstraint("code", name="uk_nqe_value_index_code"),
        UniqueConstraint("domain_code", "table_code", "column_code", "normalized_value", name="uk_nqe_value_index_domain_table_column_value"),
        Index("idx_nqe_value_index_domain_column_match", "domain_code", "column_code", "match_text"),
        Index("idx_nqe_value_index_domain_column_freq", "domain_code", "column_code", "freq"),
        {"comment": "NQE 字段取值检索索引表"},
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False, comment="索引稳定编码")
    table_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="表编码")
    column_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="字段编码")
    normalized_value: Mapped[str] = mapped_column(String(256), nullable=False, comment="标准化取值")
    display_value: Mapped[str] = mapped_column(String(512), nullable=False, comment="展示取值")
    match_text: Mapped[str] = mapped_column(String(1024), nullable=False, comment="主匹配文本")
    aliases_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="别名匹配文本")
    freq: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="取值频次")
    quality_score: Mapped[int] = mapped_column(Integer, nullable=False, default=100, comment="质量分")
    source_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True, comment="来源快照 JSON 字符串")


class NqeMetricInfo(NqeIdMixin, NqeRequiredDomainMixin, NqeSourceMixin, NqeLifecycleMixin, Base):
    """NQE 指标语义资产表。"""

    __tablename__ = "nqe_metric_info"
    __table_args__ = (
        UniqueConstraint("code", name="uk_nqe_metric_info_code"),
        UniqueConstraint("metric_code", name="uk_nqe_metric_info_metric_code"),
        Index("idx_nqe_metric_info_domain", "domain_code"),
        Index("idx_nqe_metric_info_table", "base_table_code"),
        {"comment": "NQE 指标语义资产表"},
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False, comment="指标稳定编码")
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="指标编码")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="指标名称")
    business_name: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="指标业务别名")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="指标说明")
    metric_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="指标类型：atomic/derived/ratio")
    default_aggregation: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="默认聚合方式")
    formula_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="业务公式说明")
    sql_expression_template: Mapped[str | None] = mapped_column(Text, nullable=True, comment="受控 SQL 表达式模板")
    base_table_code: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="基础表编码")
    fallback_required: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="失败时是否必须降级")


class NqeDimensionInfo(NqeIdMixin, NqeRequiredDomainMixin, NqeSourceMixin, NqeLifecycleMixin, Base):
    """NQE 维度语义资产表。"""

    __tablename__ = "nqe_dimension_info"
    __table_args__ = (
        UniqueConstraint("code", name="uk_nqe_dimension_info_code"),
        UniqueConstraint("dimension_code", name="uk_nqe_dimension_info_dimension_code"),
        Index("idx_nqe_dimension_info_domain", "domain_code"),
        {"comment": "NQE 维度语义资产表"},
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False, comment="维度稳定编码")
    dimension_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="维度编码")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="维度名称")
    business_name: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="维度业务别名")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="维度说明")
    dimension_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="维度类型：time/org/product/customer 等")
    table_code: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="来源表编码")
    column_code: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="来源字段编码")
    hierarchy_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="层级结构 JSON 字符串")


class NqeBusinessRule(NqeIdMixin, NqeRequiredDomainMixin, NqeSourceMixin, NqeLifecycleMixin, Base):
    """NQE 业务规则语义资产表。"""

    __tablename__ = "nqe_business_rule"
    __table_args__ = (
        UniqueConstraint("code", name="uk_nqe_business_rule_code"),
        UniqueConstraint("rule_code", name="uk_nqe_business_rule_rule_code"),
        Index("idx_nqe_business_rule_domain", "domain_code"),
        {"comment": "NQE 业务规则语义资产表"},
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False, comment="规则稳定编码")
    rule_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="规则编码")
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="规则类型：clarify/fallback/safety/business")
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="规则标题")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="规则名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="规则说明")
    rule_text: Mapped[str] = mapped_column(Text, nullable=False, comment="规则正文")
    applies_to_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="适用对象 JSON 字符串")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, comment="优先级，数值越小越优先")
    requires_clarification: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否需要澄清")
    fallback_required: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否必须降级")
    visible_to_user: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否可向用户展示")


class NqeRetrievalChunk(NqeIdMixin, NqeRequiredDomainMixin, NqeSourceMixin, NqeLifecycleMixin, Base):
    """NQE 元数据召回块表。"""

    __tablename__ = "nqe_retrieval_chunk"
    __table_args__ = (
        UniqueConstraint("code", name="uk_nqe_retrieval_chunk_code"),
        UniqueConstraint("chunk_code", name="uk_nqe_retrieval_chunk_chunk_code"),
        Index("idx_nqe_retrieval_chunk_asset", "asset_type", "asset_code"),
        Index("idx_nqe_retrieval_chunk_domain", "domain_code"),
        {"comment": "NQE 元数据召回块表"},
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False, comment="召回块稳定编码")
    chunk_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="召回块编码")
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="资产类型：table/column/metric/dimension/rule")
    asset_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="资产技术 ID")
    asset_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="资产编码")
    name: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="召回块名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="召回块说明")
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False, comment="召回文本")
    keywords_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="关键词 JSON 字符串")
    synonyms_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="同义词 JSON 字符串")
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="向量模型名称")
    embedding_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="向量内容哈希")
    index_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", comment="索引状态")
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最近索引时间")


class NqeQueryTrace(NqeIdMixin, NqeOptionalDomainMixin, NqeSourceMixin, NqeLifecycleMixin, Base):
    """NQE 查询运行追踪表。"""

    __tablename__ = "nqe_query_trace"
    __table_args__ = (
        UniqueConstraint("code", name="uk_nqe_query_trace_code"),
        UniqueConstraint("trace_id", name="uk_nqe_query_trace_trace_id"),
        Index("idx_nqe_query_trace_domain", "domain_code"),
        Index("idx_nqe_query_trace_status", "final_status"),
        {"comment": "NQE 查询运行追踪表"},
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False, comment="追踪稳定编码")
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="查询追踪 ID")
    user_question: Mapped[str] = mapped_column(Text, nullable=False, comment="用户原始问题")
    gray_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="shadow", comment="灰度模式")
    route_status: Mapped[str] = mapped_column(String(32), nullable=False, comment="路由状态")
    final_status: Mapped[str] = mapped_column(String(32), nullable=False, comment="最终状态")
    selected_tables_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="选中表 JSON 字符串")
    selected_metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="选中指标 JSON 字符串")
    final_sql_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="最终 SQL 哈希")
    result_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="结果行数")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="总耗时毫秒")
    fallback_used: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否使用降级")
    old_query_log_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="旧链路查询日志 ID")
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="错误编码")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")


class NqeQueryTraceStep(NqeIdMixin, NqeOptionalDomainMixin, NqeSourceMixin, NqeLifecycleMixin, Base):
    """NQE 查询运行步骤表。"""

    __tablename__ = "nqe_query_trace_step"
    __table_args__ = (
        UniqueConstraint("code", name="uk_nqe_query_trace_step_code"),
        UniqueConstraint("trace_id", "step_order", name="uk_nqe_trace_step_trace_order"),
        Index("idx_nqe_trace_step_trace", "trace_id"),
        {"comment": "NQE 查询运行步骤表"},
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False, comment="步骤稳定编码")
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="查询追踪 ID")
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, comment="步骤顺序")
    node_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="节点名称")
    step_status: Mapped[str] = mapped_column(String(32), nullable=False, comment="步骤状态")
    input_summary_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="输入摘要 JSON 字符串")
    output_summary_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="输出摘要 JSON 字符串")
    prompt_code: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="提示词编码")
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="提示词版本")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="步骤耗时毫秒")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")


class NqeSqlRevision(NqeIdMixin, NqeOptionalDomainMixin, NqeSourceMixin, NqeLifecycleMixin, Base):
    """NQE SQL 修订与安全校验记录表。"""

    __tablename__ = "nqe_sql_revision"
    __table_args__ = (
        UniqueConstraint("code", name="uk_nqe_sql_revision_code"),
        UniqueConstraint("trace_id", "revision_no", name="uk_nqe_sql_revision_trace_no"),
        Index("idx_nqe_sql_revision_trace", "trace_id"),
        {"comment": "NQE SQL 修订与安全校验记录表"},
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False, comment="SQL 修订稳定编码")
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="查询追踪 ID")
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="SQL 修订序号")
    source: Mapped[str] = mapped_column(String(64), nullable=False, comment="SQL 来源：draft/rewrite/final")
    sql_hash: Mapped[str] = mapped_column(String(128), nullable=False, comment="SQL 哈希")
    sql_redacted: Mapped[str] = mapped_column(Text, nullable=False, comment="脱敏后的 SQL 文本")
    metadata_version: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="使用的元数据版本")
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="提示词版本")
    safety_status: Mapped[str] = mapped_column(String(32), nullable=False, comment="安全校验状态")
    explain_status: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="EXPLAIN 状态")
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="错误编码")


class NqeMetadataVersion(NqeIdMixin, NqeOptionalDomainMixin, NqeSourceMixin, NqeLifecycleMixin, Base):
    """NQE 元数据发布版本表。"""

    __tablename__ = "nqe_metadata_version"
    __table_args__ = (
        UniqueConstraint("code", name="uk_nqe_metadata_version_code"),
        UniqueConstraint("metadata_version", name="uk_nqe_metadata_version_no"),
        Index("idx_nqe_metadata_version_domain", "domain_code"),
        {"comment": "NQE 元数据发布版本表"},
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False, comment="版本稳定编码")
    metadata_version: Mapped[str] = mapped_column(String(64), nullable=False, comment="元数据版本号")
    name: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="版本名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="版本说明")
    version_status: Mapped[str] = mapped_column(String(32), nullable=False, comment="版本状态：draft/published/rollback")
    published_by: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="发布人")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="发布时间")
    rollback_from_version: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="回滚来源版本")
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True, comment="变更说明")


class NqeQualityGate(NqeIdMixin, NqeOptionalDomainMixin, NqeSourceMixin, NqeLifecycleMixin, Base):
    """NQE 元数据质量门禁表。"""

    __tablename__ = "nqe_quality_gate"
    __table_args__ = (
        UniqueConstraint("code", name="uk_nqe_quality_gate_code"),
        UniqueConstraint("gate_code", "metadata_version", name="uk_nqe_quality_gate_code_version"),
        Index("idx_nqe_quality_gate_version", "metadata_version"),
        Index("idx_nqe_quality_gate_status", "gate_status"),
        {"comment": "NQE 元数据质量门禁表"},
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False, comment="质量门禁稳定编码")
    gate_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="质量门禁编码")
    gate_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="门禁类型：metadata/retrieval/sql/safety/regression")
    metadata_version: Mapped[str] = mapped_column(String(64), nullable=False, comment="元数据版本号")
    name: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="门禁名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="门禁说明")
    gate_status: Mapped[str] = mapped_column(String(32), nullable=False, comment="门禁状态：passed/failed/warn")
    passed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="通过数量")
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="失败数量")
    report_ref: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="报告逻辑引用")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")


__all__ = [
    "NqeDomain",
    "NqeDataSource",
    "NqeTableInfo",
    "NqeColumnInfo",
    "NqeValueInfo",
    "NqeValueIndex",
    "NqeMetricInfo",
    "NqeDimensionInfo",
    "NqeBusinessRule",
    "NqeRetrievalChunk",
    "NqeQueryTrace",
    "NqeQueryTraceStep",
    "NqeSqlRevision",
    "NqeMetadataVersion",
    "NqeQualityGate",
]
