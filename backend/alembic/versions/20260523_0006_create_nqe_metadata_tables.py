"""创建 NQE 首批元数据与运行审计表

Revision ID: 20260523_0006
Revises: 20260518_0005
Create Date: 2026-05-23 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260523_0006"
down_revision = "20260518_0005"
branch_labels = None
depends_on = None


NQE_TABLES = [
    "nqe_domain",
    "nqe_data_source",
    "nqe_table_info",
    "nqe_column_info",
    "nqe_metric_info",
    "nqe_dimension_info",
    "nqe_business_rule",
    "nqe_retrieval_chunk",
    "nqe_query_trace",
    "nqe_query_trace_step",
    "nqe_sql_revision",
    "nqe_metadata_version",
    "nqe_quality_gate",
]


def _id_column() -> sa.Column:
    """返回统一技术主键列。"""

    return sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键")


def _status_columns() -> list[sa.Column]:
    """返回元数据表通用状态与审计列。"""

    return [
        sa.Column("version", sa.String(length=64), nullable=False, server_default="v1", comment="元数据版本标签"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft", comment="状态：draft/published/disabled"),
        sa.Column("is_active", sa.SmallInteger(), nullable=False, server_default="1", comment="是否启用"),
        sa.Column("effective_from", sa.DateTime(), nullable=True, comment="生效开始时间"),
        sa.Column("effective_to", sa.DateTime(), nullable=True, comment="生效结束时间"),
        sa.Column("created_by", sa.String(length=128), nullable=True, comment="创建人"),
        sa.Column("updated_by", sa.String(length=128), nullable=True, comment="更新人"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.Column("extra_json", sa.Text(), nullable=True, comment="扩展属性 JSON 字符串"),
    ]


def upgrade() -> None:
    """创建 NQE 首批元数据、召回、运行审计和评测治理表。"""

    op.create_table(
        "nqe_domain",
        _id_column(),
        sa.Column("code", sa.String(length=128), nullable=False, comment="稳定编码"),
        sa.Column("domain_code", sa.String(length=128), nullable=False, comment="业务域编码"),
        sa.Column("name", sa.String(length=255), nullable=False, comment="业务域名称"),
        sa.Column("display_name", sa.String(length=255), nullable=True, comment="用户侧展示名称"),
        sa.Column("description", sa.Text(), nullable=True, comment="业务域说明"),
        sa.Column("source_type", sa.String(length=64), nullable=True, comment="来源类型，仅保存逻辑类型"),
        sa.Column("source_ref", sa.String(length=255), nullable=True, comment="来源引用，不保存真实连接串"),
        *_status_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_nqe_domain_code"),
        sa.UniqueConstraint("domain_code", name="uk_nqe_domain_domain_code"),
        comment="NQE 业务域元数据表",
    )

    op.create_table(
        "nqe_data_source",
        _id_column(),
        sa.Column("code", sa.String(length=128), nullable=False, comment="数据源稳定编码"),
        sa.Column("domain_code", sa.String(length=128), nullable=False, comment="业务域编码"),
        sa.Column("name", sa.String(length=255), nullable=False, comment="数据源名称"),
        sa.Column("description", sa.Text(), nullable=True, comment="数据源说明"),
        sa.Column("source_type", sa.String(length=64), nullable=True, comment="来源类型"),
        sa.Column("source_ref", sa.String(length=255), nullable=True, comment="来源引用，不保存真实连接串"),
        sa.Column("source_kind", sa.String(length=64), nullable=False, comment="数据源类别：middle_db/oracle/mysql/file 等"),
        sa.Column("logical_name", sa.String(length=255), nullable=False, comment="逻辑名称"),
        sa.Column("readonly_required", sa.SmallInteger(), nullable=False, server_default="1", comment="是否强制只读"),
        sa.Column("connection_ref", sa.String(length=255), nullable=True, comment="连接配置逻辑引用，不保存密钥"),
        sa.Column("allow_explain", sa.SmallInteger(), nullable=False, server_default="1", comment="是否允许 EXPLAIN"),
        sa.Column("timeout_ms", sa.Integer(), nullable=False, server_default="30000", comment="查询超时时间毫秒"),
        sa.Column("max_rows", sa.Integer(), nullable=False, server_default="1000", comment="最大返回行数"),
        *_status_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_nqe_data_source_code"),
        comment="NQE 数据源白名单表",
    )
    op.create_index("idx_nqe_data_source_domain", "nqe_data_source", ["domain_code"], unique=False)

    op.create_table(
        "nqe_table_info",
        _id_column(),
        sa.Column("code", sa.String(length=128), nullable=False, comment="表稳定编码"),
        sa.Column("domain_code", sa.String(length=128), nullable=False, comment="业务域编码"),
        sa.Column("data_source_code", sa.String(length=128), nullable=False, comment="数据源编码"),
        sa.Column("name", sa.String(length=255), nullable=False, comment="表业务名称"),
        sa.Column("business_name", sa.String(length=255), nullable=True, comment="业务别名"),
        sa.Column("description", sa.Text(), nullable=True, comment="表说明"),
        sa.Column("physical_table_name", sa.String(length=255), nullable=False, comment="物理表名，仅供后端白名单使用"),
        sa.Column("table_role", sa.String(length=64), nullable=False, comment="表角色：fact/dim/ods/dwd/dws/dm"),
        sa.Column("grain", sa.String(length=255), nullable=True, comment="数据粒度说明"),
        sa.Column("allow_select", sa.SmallInteger(), nullable=False, server_default="1", comment="是否允许查询"),
        sa.Column("allow_detail", sa.SmallInteger(), nullable=False, server_default="0", comment="是否允许明细查询"),
        sa.Column("default_limit_rows", sa.Integer(), nullable=False, server_default="100", comment="默认返回行数"),
        sa.Column("max_limit_rows", sa.Integer(), nullable=False, server_default="1000", comment="最大返回行数"),
        sa.Column("sensitive_level", sa.String(length=64), nullable=False, server_default="normal", comment="敏感等级"),
        sa.Column("source_type", sa.String(length=64), nullable=True, comment="来源类型"),
        sa.Column("source_ref", sa.String(length=255), nullable=True, comment="来源引用，不保存真实连接串"),
        *_status_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_nqe_table_info_code"),
        comment="NQE 查询表白名单与语义说明表",
    )
    op.create_index("idx_nqe_table_info_domain", "nqe_table_info", ["domain_code"], unique=False)
    op.create_index("idx_nqe_table_info_source", "nqe_table_info", ["data_source_code"], unique=False)

    op.create_table(
        "nqe_column_info",
        _id_column(),
        sa.Column("code", sa.String(length=128), nullable=False, comment="字段稳定编码"),
        sa.Column("domain_code", sa.String(length=128), nullable=False, comment="业务域编码"),
        sa.Column("table_code", sa.String(length=128), nullable=False, comment="表编码"),
        sa.Column("column_code", sa.String(length=128), nullable=False, comment="字段编码"),
        sa.Column("name", sa.String(length=255), nullable=False, comment="字段业务名称"),
        sa.Column("business_name", sa.String(length=255), nullable=True, comment="字段业务别名"),
        sa.Column("description", sa.Text(), nullable=True, comment="字段说明"),
        sa.Column("physical_column_name", sa.String(length=255), nullable=False, comment="物理字段名，仅供后端白名单使用"),
        sa.Column("data_type", sa.String(length=128), nullable=False, comment="数据类型"),
        sa.Column("semantic_type", sa.String(length=128), nullable=True, comment="语义类型：time/entity/amount/status 等"),
        sa.Column("is_filterable", sa.SmallInteger(), nullable=False, server_default="0", comment="是否可过滤"),
        sa.Column("is_groupable", sa.SmallInteger(), nullable=False, server_default="0", comment="是否可分组"),
        sa.Column("is_aggregatable", sa.SmallInteger(), nullable=False, server_default="0", comment="是否可聚合"),
        sa.Column("allowed_aggregations", sa.Text(), nullable=True, comment="允许聚合函数 JSON 字符串"),
        sa.Column("sensitive_level", sa.String(length=64), nullable=False, server_default="normal", comment="敏感等级"),
        sa.Column("source_type", sa.String(length=64), nullable=True, comment="来源类型"),
        sa.Column("source_ref", sa.String(length=255), nullable=True, comment="来源引用，不保存真实连接串"),
        *_status_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_nqe_column_info_code"),
        sa.UniqueConstraint("table_code", "column_code", name="uk_nqe_column_table_column"),
        comment="NQE 查询字段白名单与语义说明表",
    )
    op.create_index("idx_nqe_column_info_table", "nqe_column_info", ["table_code"], unique=False)
    op.create_index("idx_nqe_column_info_domain", "nqe_column_info", ["domain_code"], unique=False)

    op.create_table(
        "nqe_metric_info",
        _id_column(),
        sa.Column("code", sa.String(length=128), nullable=False, comment="指标稳定编码"),
        sa.Column("domain_code", sa.String(length=128), nullable=False, comment="业务域编码"),
        sa.Column("metric_code", sa.String(length=128), nullable=False, comment="指标编码"),
        sa.Column("name", sa.String(length=255), nullable=False, comment="指标名称"),
        sa.Column("business_name", sa.String(length=255), nullable=True, comment="指标业务别名"),
        sa.Column("description", sa.Text(), nullable=True, comment="指标说明"),
        sa.Column("metric_type", sa.String(length=64), nullable=False, comment="指标类型：atomic/derived/ratio"),
        sa.Column("default_aggregation", sa.String(length=64), nullable=True, comment="默认聚合方式"),
        sa.Column("formula_text", sa.Text(), nullable=True, comment="业务公式说明"),
        sa.Column("sql_expression_template", sa.Text(), nullable=True, comment="受控 SQL 表达式模板"),
        sa.Column("base_table_code", sa.String(length=128), nullable=True, comment="基础表编码"),
        sa.Column("fallback_required", sa.SmallInteger(), nullable=False, server_default="0", comment="失败时是否必须降级"),
        sa.Column("source_type", sa.String(length=64), nullable=True, comment="来源类型"),
        sa.Column("source_ref", sa.String(length=255), nullable=True, comment="来源引用，不保存真实连接串"),
        *_status_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_nqe_metric_info_code"),
        sa.UniqueConstraint("metric_code", name="uk_nqe_metric_info_metric_code"),
        comment="NQE 指标语义资产表",
    )
    op.create_index("idx_nqe_metric_info_domain", "nqe_metric_info", ["domain_code"], unique=False)
    op.create_index("idx_nqe_metric_info_table", "nqe_metric_info", ["base_table_code"], unique=False)

    op.create_table(
        "nqe_dimension_info",
        _id_column(),
        sa.Column("code", sa.String(length=128), nullable=False, comment="维度稳定编码"),
        sa.Column("domain_code", sa.String(length=128), nullable=False, comment="业务域编码"),
        sa.Column("dimension_code", sa.String(length=128), nullable=False, comment="维度编码"),
        sa.Column("name", sa.String(length=255), nullable=False, comment="维度名称"),
        sa.Column("business_name", sa.String(length=255), nullable=True, comment="维度业务别名"),
        sa.Column("description", sa.Text(), nullable=True, comment="维度说明"),
        sa.Column("dimension_type", sa.String(length=64), nullable=False, comment="维度类型：time/org/product/customer 等"),
        sa.Column("table_code", sa.String(length=128), nullable=True, comment="来源表编码"),
        sa.Column("column_code", sa.String(length=128), nullable=True, comment="来源字段编码"),
        sa.Column("hierarchy_json", sa.Text(), nullable=True, comment="层级结构 JSON 字符串"),
        sa.Column("source_type", sa.String(length=64), nullable=True, comment="来源类型"),
        sa.Column("source_ref", sa.String(length=255), nullable=True, comment="来源引用，不保存真实连接串"),
        *_status_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_nqe_dimension_info_code"),
        sa.UniqueConstraint("dimension_code", name="uk_nqe_dimension_info_dimension_code"),
        comment="NQE 维度语义资产表",
    )
    op.create_index("idx_nqe_dimension_info_domain", "nqe_dimension_info", ["domain_code"], unique=False)

    op.create_table(
        "nqe_business_rule",
        _id_column(),
        sa.Column("code", sa.String(length=128), nullable=False, comment="规则稳定编码"),
        sa.Column("domain_code", sa.String(length=128), nullable=False, comment="业务域编码"),
        sa.Column("rule_code", sa.String(length=128), nullable=False, comment="规则编码"),
        sa.Column("rule_type", sa.String(length=64), nullable=False, comment="规则类型：clarify/fallback/safety/business"),
        sa.Column("title", sa.String(length=255), nullable=False, comment="规则标题"),
        sa.Column("name", sa.String(length=255), nullable=False, comment="规则名称"),
        sa.Column("description", sa.Text(), nullable=True, comment="规则说明"),
        sa.Column("rule_text", sa.Text(), nullable=False, comment="规则正文"),
        sa.Column("applies_to_json", sa.Text(), nullable=True, comment="适用对象 JSON 字符串"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100", comment="优先级，数值越小越优先"),
        sa.Column("requires_clarification", sa.SmallInteger(), nullable=False, server_default="0", comment="是否需要澄清"),
        sa.Column("fallback_required", sa.SmallInteger(), nullable=False, server_default="0", comment="是否必须降级"),
        sa.Column("visible_to_user", sa.SmallInteger(), nullable=False, server_default="0", comment="是否可向用户展示"),
        sa.Column("source_type", sa.String(length=64), nullable=True, comment="来源类型"),
        sa.Column("source_ref", sa.String(length=255), nullable=True, comment="来源引用"),
        *_status_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_nqe_business_rule_code"),
        sa.UniqueConstraint("rule_code", name="uk_nqe_business_rule_rule_code"),
        comment="NQE 业务规则语义资产表",
    )
    op.create_index("idx_nqe_business_rule_domain", "nqe_business_rule", ["domain_code"], unique=False)

    op.create_table(
        "nqe_retrieval_chunk",
        _id_column(),
        sa.Column("code", sa.String(length=128), nullable=False, comment="召回块稳定编码"),
        sa.Column("domain_code", sa.String(length=128), nullable=False, comment="业务域编码"),
        sa.Column("chunk_code", sa.String(length=128), nullable=False, comment="召回块编码"),
        sa.Column("asset_type", sa.String(length=64), nullable=False, comment="资产类型：table/column/metric/dimension/rule"),
        sa.Column("asset_id", sa.BigInteger(), nullable=True, comment="资产技术 ID"),
        sa.Column("asset_code", sa.String(length=128), nullable=False, comment="资产编码"),
        sa.Column("name", sa.String(length=255), nullable=True, comment="召回块名称"),
        sa.Column("description", sa.Text(), nullable=True, comment="召回块说明"),
        sa.Column("chunk_text", sa.Text(), nullable=False, comment="召回文本"),
        sa.Column("keywords_json", sa.Text(), nullable=True, comment="关键词 JSON 字符串"),
        sa.Column("synonyms_json", sa.Text(), nullable=True, comment="同义词 JSON 字符串"),
        sa.Column("embedding_model", sa.String(length=128), nullable=True, comment="向量模型名称"),
        sa.Column("embedding_hash", sa.String(length=128), nullable=True, comment="向量内容哈希"),
        sa.Column("index_status", sa.String(length=32), nullable=False, server_default="pending", comment="索引状态"),
        sa.Column("last_indexed_at", sa.DateTime(), nullable=True, comment="最近索引时间"),
        sa.Column("source_type", sa.String(length=64), nullable=True, comment="来源类型"),
        sa.Column("source_ref", sa.String(length=255), nullable=True, comment="来源引用"),
        *_status_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_nqe_retrieval_chunk_code"),
        sa.UniqueConstraint("chunk_code", name="uk_nqe_retrieval_chunk_chunk_code"),
        comment="NQE 元数据召回块表",
    )
    op.create_index("idx_nqe_retrieval_chunk_asset", "nqe_retrieval_chunk", ["asset_type", "asset_code"], unique=False)
    op.create_index("idx_nqe_retrieval_chunk_domain", "nqe_retrieval_chunk", ["domain_code"], unique=False)

    op.create_table(
        "nqe_query_trace",
        _id_column(),
        sa.Column("code", sa.String(length=128), nullable=False, comment="追踪稳定编码"),
        sa.Column("domain_code", sa.String(length=128), nullable=True, comment="命中的业务域编码"),
        sa.Column("trace_id", sa.String(length=128), nullable=False, comment="查询追踪 ID"),
        sa.Column("user_question", sa.Text(), nullable=False, comment="用户原始问题"),
        sa.Column("gray_mode", sa.String(length=32), nullable=False, server_default="shadow", comment="灰度模式"),
        sa.Column("route_status", sa.String(length=32), nullable=False, comment="路由状态"),
        sa.Column("final_status", sa.String(length=32), nullable=False, comment="最终状态"),
        sa.Column("selected_tables_json", sa.Text(), nullable=True, comment="选中表 JSON 字符串"),
        sa.Column("selected_metrics_json", sa.Text(), nullable=True, comment="选中指标 JSON 字符串"),
        sa.Column("final_sql_hash", sa.String(length=128), nullable=True, comment="最终 SQL 哈希"),
        sa.Column("result_row_count", sa.Integer(), nullable=True, comment="结果行数"),
        sa.Column("latency_ms", sa.Integer(), nullable=True, comment="总耗时毫秒"),
        sa.Column("fallback_used", sa.SmallInteger(), nullable=False, server_default="0", comment="是否使用降级"),
        sa.Column("old_query_log_id", sa.BigInteger(), nullable=True, comment="旧链路查询日志 ID"),
        sa.Column("error_code", sa.String(length=128), nullable=True, comment="错误编码"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="错误信息"),
        sa.Column("source_type", sa.String(length=64), nullable=True, comment="来源类型"),
        sa.Column("source_ref", sa.String(length=255), nullable=True, comment="来源引用"),
        *_status_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_nqe_query_trace_code"),
        sa.UniqueConstraint("trace_id", name="uk_nqe_query_trace_trace_id"),
        comment="NQE 查询运行追踪表",
    )
    op.create_index("idx_nqe_query_trace_domain", "nqe_query_trace", ["domain_code"], unique=False)
    op.create_index("idx_nqe_query_trace_status", "nqe_query_trace", ["final_status"], unique=False)

    op.create_table(
        "nqe_query_trace_step",
        _id_column(),
        sa.Column("code", sa.String(length=128), nullable=False, comment="步骤稳定编码"),
        sa.Column("domain_code", sa.String(length=128), nullable=True, comment="业务域编码"),
        sa.Column("trace_id", sa.String(length=128), nullable=False, comment="查询追踪 ID"),
        sa.Column("step_order", sa.Integer(), nullable=False, comment="步骤顺序"),
        sa.Column("node_name", sa.String(length=128), nullable=False, comment="节点名称"),
        sa.Column("step_status", sa.String(length=32), nullable=False, comment="步骤状态"),
        sa.Column("input_summary_json", sa.Text(), nullable=True, comment="输入摘要 JSON 字符串"),
        sa.Column("output_summary_json", sa.Text(), nullable=True, comment="输出摘要 JSON 字符串"),
        sa.Column("prompt_code", sa.String(length=128), nullable=True, comment="提示词编码"),
        sa.Column("prompt_version", sa.String(length=64), nullable=True, comment="提示词版本"),
        sa.Column("latency_ms", sa.Integer(), nullable=True, comment="步骤耗时毫秒"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="错误信息"),
        sa.Column("source_type", sa.String(length=64), nullable=True, comment="来源类型"),
        sa.Column("source_ref", sa.String(length=255), nullable=True, comment="来源引用"),
        *_status_columns(),
        sa.ForeignKeyConstraint(["trace_id"], ["nqe_query_trace.trace_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_nqe_query_trace_step_code"),
        sa.UniqueConstraint("trace_id", "step_order", name="uk_nqe_trace_step_trace_order"),
        comment="NQE 查询运行步骤表",
    )
    op.create_index("idx_nqe_trace_step_trace", "nqe_query_trace_step", ["trace_id"], unique=False)

    op.create_table(
        "nqe_sql_revision",
        _id_column(),
        sa.Column("code", sa.String(length=128), nullable=False, comment="SQL 修订稳定编码"),
        sa.Column("domain_code", sa.String(length=128), nullable=True, comment="业务域编码"),
        sa.Column("trace_id", sa.String(length=128), nullable=False, comment="查询追踪 ID"),
        sa.Column("revision_no", sa.Integer(), nullable=False, comment="SQL 修订序号"),
        sa.Column("source", sa.String(length=64), nullable=False, comment="SQL 来源：draft/rewrite/final"),
        sa.Column("sql_hash", sa.String(length=128), nullable=False, comment="SQL 哈希"),
        sa.Column("sql_redacted", sa.Text(), nullable=False, comment="脱敏后的 SQL 文本"),
        sa.Column("metadata_version", sa.String(length=64), nullable=True, comment="使用的元数据版本"),
        sa.Column("prompt_version", sa.String(length=64), nullable=True, comment="提示词版本"),
        sa.Column("safety_status", sa.String(length=32), nullable=False, comment="安全校验状态"),
        sa.Column("explain_status", sa.String(length=32), nullable=True, comment="EXPLAIN 状态"),
        sa.Column("error_code", sa.String(length=128), nullable=True, comment="错误编码"),
        sa.Column("source_type", sa.String(length=64), nullable=True, comment="来源类型"),
        sa.Column("source_ref", sa.String(length=255), nullable=True, comment="来源引用"),
        *_status_columns(),
        sa.ForeignKeyConstraint(["trace_id"], ["nqe_query_trace.trace_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_nqe_sql_revision_code"),
        sa.UniqueConstraint("trace_id", "revision_no", name="uk_nqe_sql_revision_trace_no"),
        comment="NQE SQL 修订与安全校验记录表",
    )
    op.create_index("idx_nqe_sql_revision_trace", "nqe_sql_revision", ["trace_id"], unique=False)

    op.create_table(
        "nqe_metadata_version",
        _id_column(),
        sa.Column("code", sa.String(length=128), nullable=False, comment="版本稳定编码"),
        sa.Column("domain_code", sa.String(length=128), nullable=True, comment="业务域编码"),
        sa.Column("metadata_version", sa.String(length=64), nullable=False, comment="元数据版本号"),
        sa.Column("name", sa.String(length=255), nullable=True, comment="版本名称"),
        sa.Column("description", sa.Text(), nullable=True, comment="版本说明"),
        sa.Column("version_status", sa.String(length=32), nullable=False, comment="版本状态：draft/published/rollback"),
        sa.Column("published_by", sa.String(length=128), nullable=True, comment="发布人"),
        sa.Column("published_at", sa.DateTime(), nullable=True, comment="发布时间"),
        sa.Column("rollback_from_version", sa.String(length=64), nullable=True, comment="回滚来源版本"),
        sa.Column("change_note", sa.Text(), nullable=True, comment="变更说明"),
        sa.Column("source_type", sa.String(length=64), nullable=True, comment="来源类型"),
        sa.Column("source_ref", sa.String(length=255), nullable=True, comment="来源引用"),
        *_status_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_nqe_metadata_version_code"),
        sa.UniqueConstraint("metadata_version", name="uk_nqe_metadata_version_no"),
        comment="NQE 元数据发布版本表",
    )
    op.create_index("idx_nqe_metadata_version_domain", "nqe_metadata_version", ["domain_code"], unique=False)

    op.create_table(
        "nqe_quality_gate",
        _id_column(),
        sa.Column("code", sa.String(length=128), nullable=False, comment="质量门禁稳定编码"),
        sa.Column("domain_code", sa.String(length=128), nullable=True, comment="业务域编码"),
        sa.Column("gate_code", sa.String(length=128), nullable=False, comment="质量门禁编码"),
        sa.Column("gate_type", sa.String(length=64), nullable=False, comment="门禁类型：metadata/retrieval/sql/safety/regression"),
        sa.Column("metadata_version", sa.String(length=64), nullable=False, comment="元数据版本号"),
        sa.Column("name", sa.String(length=255), nullable=True, comment="门禁名称"),
        sa.Column("description", sa.Text(), nullable=True, comment="门禁说明"),
        sa.Column("gate_status", sa.String(length=32), nullable=False, comment="门禁状态：passed/failed/warn"),
        sa.Column("passed_count", sa.Integer(), nullable=False, server_default="0", comment="通过数量"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0", comment="失败数量"),
        sa.Column("report_ref", sa.String(length=512), nullable=True, comment="报告逻辑引用"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="错误信息"),
        sa.Column("source_type", sa.String(length=64), nullable=True, comment="来源类型"),
        sa.Column("source_ref", sa.String(length=255), nullable=True, comment="来源引用"),
        *_status_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_nqe_quality_gate_code"),
        sa.UniqueConstraint("gate_code", "metadata_version", name="uk_nqe_quality_gate_code_version"),
        comment="NQE 元数据质量门禁表",
    )
    op.create_index("idx_nqe_quality_gate_version", "nqe_quality_gate", ["metadata_version"], unique=False)
    op.create_index("idx_nqe_quality_gate_status", "nqe_quality_gate", ["gate_status"], unique=False)


def downgrade() -> None:
    """按依赖反向删除 NQE 首批表。"""

    op.drop_index("idx_nqe_quality_gate_status", table_name="nqe_quality_gate")
    op.drop_index("idx_nqe_quality_gate_version", table_name="nqe_quality_gate")
    op.drop_table("nqe_quality_gate")
    op.drop_index("idx_nqe_metadata_version_domain", table_name="nqe_metadata_version")
    op.drop_table("nqe_metadata_version")
    op.drop_index("idx_nqe_sql_revision_trace", table_name="nqe_sql_revision")
    op.drop_table("nqe_sql_revision")
    op.drop_index("idx_nqe_trace_step_trace", table_name="nqe_query_trace_step")
    op.drop_table("nqe_query_trace_step")
    op.drop_index("idx_nqe_query_trace_status", table_name="nqe_query_trace")
    op.drop_index("idx_nqe_query_trace_domain", table_name="nqe_query_trace")
    op.drop_table("nqe_query_trace")
    op.drop_index("idx_nqe_retrieval_chunk_domain", table_name="nqe_retrieval_chunk")
    op.drop_index("idx_nqe_retrieval_chunk_asset", table_name="nqe_retrieval_chunk")
    op.drop_table("nqe_retrieval_chunk")
    op.drop_index("idx_nqe_business_rule_domain", table_name="nqe_business_rule")
    op.drop_table("nqe_business_rule")
    op.drop_index("idx_nqe_dimension_info_domain", table_name="nqe_dimension_info")
    op.drop_table("nqe_dimension_info")
    op.drop_index("idx_nqe_metric_info_table", table_name="nqe_metric_info")
    op.drop_index("idx_nqe_metric_info_domain", table_name="nqe_metric_info")
    op.drop_table("nqe_metric_info")
    op.drop_index("idx_nqe_column_info_domain", table_name="nqe_column_info")
    op.drop_index("idx_nqe_column_info_table", table_name="nqe_column_info")
    op.drop_table("nqe_column_info")
    op.drop_index("idx_nqe_table_info_source", table_name="nqe_table_info")
    op.drop_index("idx_nqe_table_info_domain", table_name="nqe_table_info")
    op.drop_table("nqe_table_info")
    op.drop_index("idx_nqe_data_source_domain", table_name="nqe_data_source")
    op.drop_table("nqe_data_source")
    op.drop_table("nqe_domain")
