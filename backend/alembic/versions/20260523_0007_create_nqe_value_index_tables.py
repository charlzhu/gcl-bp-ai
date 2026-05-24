"""创建 NQE 字段取值索引表

Revision ID: 20260523_0007
Revises: 20260523_0006
Create Date: 2026-05-23 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260523_0007"
down_revision = "20260523_0006"
branch_labels = None
depends_on = None


def _id_column() -> sa.Column:
    """返回统一技术主键列。"""

    return sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键")


def _source_columns() -> list[sa.Column]:
    """返回逻辑来源列，禁止保存真实连接串或密钥。"""

    return [
        sa.Column("source_type", sa.String(length=64), nullable=True, comment="来源类型"),
        sa.Column("source_ref", sa.String(length=255), nullable=True, comment="来源引用，不保存真实连接串"),
    ]


def _status_columns() -> list[sa.Column]:
    """返回元数据生命周期和审计列。"""

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
    """创建字段取值资产表与检索索引表，并补齐字段元数据索引标记。"""

    op.add_column("nqe_column_info", sa.Column("sample_values_json", sa.Text(), nullable=True, comment="字段安全样例值 JSON 字符串"))
    op.add_column(
        "nqe_column_info",
        sa.Column("value_index_enabled", sa.SmallInteger(), nullable=False, server_default="0", comment="是否允许构建字段取值索引"),
    )
    op.add_column("nqe_column_info", sa.Column("synonyms_json", sa.Text(), nullable=True, comment="字段同义词 JSON 字符串"))
    op.add_column("nqe_column_info", sa.Column("unit", sa.String(length=64), nullable=True, comment="字段单位"))
    op.create_index("idx_nqe_column_info_value_index", "nqe_column_info", ["domain_code", "value_index_enabled"], unique=False)

    op.create_table(
        "nqe_value_info",
        _id_column(),
        sa.Column("code", sa.String(length=128), nullable=False, comment="取值稳定编码"),
        sa.Column("domain_code", sa.String(length=128), nullable=False, comment="业务域编码"),
        sa.Column("table_code", sa.String(length=128), nullable=False, comment="表编码"),
        sa.Column("column_code", sa.String(length=128), nullable=False, comment="字段编码"),
        sa.Column("value_code", sa.String(length=128), nullable=False, comment="取值编码"),
        sa.Column("raw_value", sa.String(length=512), nullable=False, comment="原始取值"),
        sa.Column("normalized_value", sa.String(length=512), nullable=False, comment="标准化取值"),
        sa.Column("display_value", sa.String(length=512), nullable=False, comment="展示取值"),
        sa.Column("aliases_json", sa.Text(), nullable=True, comment="取值别名 JSON 字符串"),
        sa.Column("pinyin_key", sa.String(length=512), nullable=True, comment="拼音或缩写检索键"),
        sa.Column("value_freq", sa.Integer(), nullable=False, server_default="0", comment="取值出现频次"),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True, comment="最近观察时间"),
        sa.Column("quality_status", sa.String(length=32), nullable=False, server_default="trusted", comment="质量状态"),
        *_source_columns(),
        *_status_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_nqe_value_info_code"),
        sa.UniqueConstraint("table_code", "column_code", "normalized_value", name="uk_nqe_value_info_table_column_value"),
        comment="NQE 字段取值资产表",
    )
    op.create_index("idx_nqe_value_info_domain_column_value", "nqe_value_info", ["domain_code", "column_code", "normalized_value"], unique=False)
    op.create_index("idx_nqe_value_info_domain_column_freq", "nqe_value_info", ["domain_code", "column_code", "value_freq"], unique=False)

    op.create_table(
        "nqe_value_index",
        _id_column(),
        sa.Column("code", sa.String(length=128), nullable=False, comment="索引稳定编码"),
        sa.Column("domain_code", sa.String(length=128), nullable=False, comment="业务域编码"),
        sa.Column("table_code", sa.String(length=128), nullable=False, comment="表编码"),
        sa.Column("column_code", sa.String(length=128), nullable=False, comment="字段编码"),
        sa.Column("normalized_value", sa.String(length=512), nullable=False, comment="标准化取值"),
        sa.Column("display_value", sa.String(length=512), nullable=False, comment="展示取值"),
        sa.Column("match_text", sa.String(length=1024), nullable=False, comment="主匹配文本"),
        sa.Column("aliases_text", sa.Text(), nullable=True, comment="别名匹配文本"),
        sa.Column("freq", sa.Integer(), nullable=False, server_default="0", comment="取值频次"),
        sa.Column("quality_score", sa.Integer(), nullable=False, server_default="100", comment="质量分"),
        sa.Column("source_snapshot", sa.Text(), nullable=True, comment="来源快照 JSON 字符串"),
        *_source_columns(),
        *_status_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_nqe_value_index_code"),
        sa.UniqueConstraint("domain_code", "table_code", "column_code", "normalized_value", name="uk_nqe_value_index_domain_table_column_value"),
        comment="NQE 字段取值检索索引表",
    )
    op.create_index("idx_nqe_value_index_domain_column_match", "nqe_value_index", ["domain_code", "column_code", "match_text"], unique=False)
    op.create_index("idx_nqe_value_index_domain_column_freq", "nqe_value_index", ["domain_code", "column_code", "freq"], unique=False)


def downgrade() -> None:
    """反向删除字段取值索引表，并移除字段元数据补充列。"""

    op.drop_index("idx_nqe_value_index_domain_column_freq", table_name="nqe_value_index")
    op.drop_index("idx_nqe_value_index_domain_column_match", table_name="nqe_value_index")
    op.drop_table("nqe_value_index")
    op.drop_index("idx_nqe_value_info_domain_column_freq", table_name="nqe_value_info")
    op.drop_index("idx_nqe_value_info_domain_column_value", table_name="nqe_value_info")
    op.drop_table("nqe_value_info")
    op.drop_index("idx_nqe_column_info_value_index", table_name="nqe_column_info")
    op.drop_column("nqe_column_info", "unit")
    op.drop_column("nqe_column_info", "synonyms_json")
    op.drop_column("nqe_column_info", "value_index_enabled")
    op.drop_column("nqe_column_info", "sample_values_json")
