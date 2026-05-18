"""创建经营分析产销存 Excel 与月度事实长表

Revision ID: 20260518_0005
Revises: 20260508_0004
Create Date: 2026-05-18 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260518_0005"
down_revision = "20260508_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建产销存 Excel ODS、DWD 月度事实和指标维表。"""

    op.create_table(
        "ods_ba_isp_excel_workbook",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键"),
        sa.Column("source_file_name", sa.String(length=512), nullable=False, comment="原始 Excel 文件名"),
        sa.Column("source_file_sha256", sa.String(length=128), nullable=False, comment="文件 SHA256，用于幂等导入"),
        sa.Column("source_file_size", sa.BigInteger(), nullable=False, comment="文件字节数"),
        sa.Column("business_year", sa.Integer(), nullable=False, comment="业务年份"),
        sa.Column("data_cutoff_month", sa.Integer(), nullable=False, comment="数据截止月份"),
        sa.Column("source_version_label", sa.String(length=64), nullable=True, comment="来源版本标签"),
        sa.Column("upload_batch_no", sa.String(length=64), nullable=False, comment="导入批次号"),
        sa.Column("sheet_count", sa.Integer(), nullable=False, server_default="0", comment="工作簿 sheet 数"),
        sa.Column("has_vba", sa.SmallInteger(), nullable=False, server_default="0", comment="是否存在 VBA"),
        sa.Column("external_link_count", sa.Integer(), nullable=False, server_default="0", comment="外部链接数量"),
        sa.Column("parser_version", sa.String(length=64), nullable=False, comment="解析器版本"),
        sa.Column("quality_status", sa.String(length=32), nullable=False, server_default="success", comment="解析质量状态"),
        sa.Column("quality_message", sa.Text(), nullable=True, comment="解析质量摘要"),
        sa.Column("quality_flags", sa.Text(), nullable=True, comment="解析质量标记 JSON"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_file_sha256", name="uk_ba_isp_workbook_sha256"),
        comment="经营分析产销存 Excel 工作簿版本表",
    )
    op.create_index("idx_ba_isp_workbook_year", "ods_ba_isp_excel_workbook", ["business_year"], unique=False)
    op.create_index("idx_ba_isp_workbook_cutoff", "ods_ba_isp_excel_workbook", ["business_year", "data_cutoff_month"], unique=False)

    op.create_table(
        "ods_ba_isp_excel_sheet",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键"),
        sa.Column("workbook_id", sa.BigInteger(), nullable=False, comment="工作簿 ID"),
        sa.Column("sheet_name", sa.String(length=128), nullable=False, comment="原始 sheet 名"),
        sa.Column("sheet_role", sa.String(length=64), nullable=False, server_default="summary", comment="sheet 角色"),
        sa.Column("dimension_ref", sa.String(length=64), nullable=True, comment="Excel 范围"),
        sa.Column("max_row", sa.Integer(), nullable=False, server_default="0", comment="最大行号"),
        sa.Column("max_col", sa.Integer(), nullable=False, server_default="0", comment="最大列号"),
        sa.Column("formula_count", sa.Integer(), nullable=False, server_default="0", comment="公式数量"),
        sa.Column("merged_cell_count", sa.Integer(), nullable=False, server_default="0", comment="合并单元格数量"),
        sa.Column("hidden_rows", sa.Text(), nullable=True, comment="隐藏行 JSON"),
        sa.Column("hidden_cols", sa.Text(), nullable=True, comment="隐藏列 JSON"),
        sa.Column("header_rows", sa.Text(), nullable=True, comment="表头行 JSON"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.ForeignKeyConstraint(["workbook_id"], ["ods_ba_isp_excel_workbook.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workbook_id", "sheet_name", name="uk_ba_isp_sheet_workbook_name"),
        comment="经营分析产销存 Excel Sheet 结构表",
    )
    op.create_index("idx_ba_isp_sheet_workbook", "ods_ba_isp_excel_sheet", ["workbook_id"], unique=False)

    op.create_table(
        "dim_ba_isp_metric",
        sa.Column("metric_code", sa.String(length=128), nullable=False, comment="标准指标编码"),
        sa.Column("metric_name", sa.String(length=128), nullable=False, comment="标准指标中文名"),
        sa.Column("metric_category", sa.String(length=64), nullable=False, comment="指标分类"),
        sa.Column("aggregation_type", sa.String(length=64), nullable=False, comment="聚合类型"),
        sa.Column("unit_standard", sa.String(length=32), nullable=False, server_default="MW", comment="标准单位"),
        sa.Column("description", sa.Text(), nullable=True, comment="业务说明"),
        sa.Column("calculation_formula", sa.Text(), nullable=True, comment="后端计算公式说明"),
        sa.Column("requires_budget", sa.SmallInteger(), nullable=False, server_default="0", comment="是否需要预算数据"),
        sa.Column("is_default_for_sales", sa.SmallInteger(), nullable=False, server_default="0", comment="是否作为销量默认指标"),
        sa.Column("is_active", sa.SmallInteger(), nullable=False, server_default="1", comment="是否启用"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.PrimaryKeyConstraint("metric_code"),
        comment="经营分析产销存标准指标维表",
    )

    op.create_table(
        "dim_ba_isp_metric_alias",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键"),
        sa.Column("alias_text", sa.String(length=128), nullable=False, comment="别名文本"),
        sa.Column("metric_code", sa.String(length=128), nullable=False, comment="标准指标编码"),
        sa.Column("alias_type", sa.String(length=64), nullable=False, server_default="synonym", comment="别名类型"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100", comment="匹配优先级"),
        sa.Column("requires_explicit_phrase", sa.SmallInteger(), nullable=False, server_default="0", comment="是否必须显式触发"),
        sa.Column("notes", sa.Text(), nullable=True, comment="说明"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.ForeignKeyConstraint(["metric_code"], ["dim_ba_isp_metric.metric_code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alias_text", "metric_code", "alias_type", name="uk_ba_isp_metric_alias_text_metric_type"),
        comment="经营分析产销存指标别名表",
    )
    op.create_index("idx_ba_isp_metric_alias_metric", "dim_ba_isp_metric_alias", ["metric_code"], unique=False)

    op.create_table(
        "dwd_ba_isp_monthly_fact",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键"),
        sa.Column("workbook_id", sa.BigInteger(), nullable=False, comment="来源工作簿 ID"),
        sa.Column("sheet_id", sa.BigInteger(), nullable=True, comment="来源 sheet ID"),
        sa.Column("business_year", sa.Integer(), nullable=False, comment="业务年份"),
        sa.Column("business_month", sa.Integer(), nullable=False, comment="业务月份"),
        sa.Column("period_label", sa.String(length=16), nullable=False, comment="期间标签"),
        sa.Column("period_start_date", sa.Date(), nullable=False, comment="期间开始日期"),
        sa.Column("period_end_date", sa.Date(), nullable=False, comment="期间结束日期"),
        sa.Column("data_cutoff_month", sa.Integer(), nullable=False, comment="来源文件截止月份"),
        sa.Column("is_published_month", sa.SmallInteger(), nullable=False, server_default="1", comment="是否已发布月份"),
        sa.Column("domain", sa.String(length=64), nullable=False, server_default="business_analysis", comment="业务域"),
        sa.Column("sub_domain", sa.String(length=128), nullable=False, server_default="inventory_sales_production", comment="子业务域"),
        sa.Column("metric_code", sa.String(length=128), nullable=False, comment="标准指标编码"),
        sa.Column("metric_name", sa.String(length=128), nullable=False, comment="标准指标中文名"),
        sa.Column("metric_category", sa.String(length=64), nullable=False, comment="指标分类"),
        sa.Column("aggregation_type", sa.String(length=64), nullable=False, comment="聚合类型"),
        sa.Column("value_decimal", sa.Numeric(precision=24, scale=8), nullable=False, comment="标准数值"),
        sa.Column("unit_standard", sa.String(length=32), nullable=False, server_default="MW", comment="标准单位"),
        sa.Column("base_name", sa.String(length=64), nullable=True, comment="基地名称"),
        sa.Column("factory_name", sa.String(length=128), nullable=True, comment="工厂名称"),
        sa.Column("model_type", sa.String(length=64), nullable=True, comment="版型"),
        sa.Column("production_mode", sa.String(length=64), nullable=True, comment="生产模式"),
        sa.Column("trade_scope", sa.String(length=128), nullable=True, comment="交易范围"),
        sa.Column("is_outsourced", sa.SmallInteger(), nullable=False, server_default="0", comment="是否委外/代工"),
        sa.Column("is_consigned", sa.SmallInteger(), nullable=False, server_default="0", comment="是否寄存"),
        sa.Column("is_default_external_sales", sa.SmallInteger(), nullable=False, server_default="0", comment="是否默认对外销量口径"),
        sa.Column("source_file_name", sa.String(length=512), nullable=False, comment="来源文件名"),
        sa.Column("source_file_sha256", sa.String(length=128), nullable=False, comment="来源文件 SHA256"),
        sa.Column("source_sheet", sa.String(length=128), nullable=False, comment="来源 sheet"),
        sa.Column("source_row_index", sa.Integer(), nullable=False, comment="来源行号"),
        sa.Column("source_col_index", sa.Integer(), nullable=False, comment="来源列号"),
        sa.Column("source_cell_ref", sa.String(length=32), nullable=False, comment="来源单元格坐标"),
        sa.Column("raw_category", sa.String(length=128), nullable=True, comment="原始分类"),
        sa.Column("raw_item", sa.String(length=256), nullable=False, comment="原始项目"),
        sa.Column("raw_unit", sa.String(length=64), nullable=True, comment="原始单位"),
        sa.Column("parser_version", sa.String(length=64), nullable=False, comment="解析器版本"),
        sa.Column("quality_flags", sa.Text(), nullable=True, comment="质量标记 JSON"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.ForeignKeyConstraint(["sheet_id"], ["ods_ba_isp_excel_sheet.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workbook_id"], ["ods_ba_isp_excel_workbook.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workbook_id", "source_sheet", "source_row_index", "source_col_index", "metric_code", name="uk_ba_isp_monthly_fact_source_cell_metric"),
        comment="经营分析产销存标准月度事实长表",
    )
    op.create_index("idx_ba_isp_fact_year_month", "dwd_ba_isp_monthly_fact", ["business_year", "business_month"], unique=False)
    op.create_index("idx_ba_isp_fact_metric", "dwd_ba_isp_monthly_fact", ["metric_code"], unique=False)
    op.create_index("idx_ba_isp_fact_metric_year", "dwd_ba_isp_monthly_fact", ["metric_code", "business_year"], unique=False)
    op.create_index("idx_ba_isp_fact_base", "dwd_ba_isp_monthly_fact", ["base_name"], unique=False)
    op.create_index("idx_ba_isp_fact_model", "dwd_ba_isp_monthly_fact", ["model_type"], unique=False)


def downgrade() -> None:
    """回滚产销存 M2 表。"""

    op.drop_index("idx_ba_isp_fact_model", table_name="dwd_ba_isp_monthly_fact")
    op.drop_index("idx_ba_isp_fact_base", table_name="dwd_ba_isp_monthly_fact")
    op.drop_index("idx_ba_isp_fact_metric_year", table_name="dwd_ba_isp_monthly_fact")
    op.drop_index("idx_ba_isp_fact_metric", table_name="dwd_ba_isp_monthly_fact")
    op.drop_index("idx_ba_isp_fact_year_month", table_name="dwd_ba_isp_monthly_fact")
    op.drop_table("dwd_ba_isp_monthly_fact")
    op.drop_index("idx_ba_isp_metric_alias_metric", table_name="dim_ba_isp_metric_alias")
    op.drop_table("dim_ba_isp_metric_alias")
    op.drop_table("dim_ba_isp_metric")
    op.drop_index("idx_ba_isp_sheet_workbook", table_name="ods_ba_isp_excel_sheet")
    op.drop_table("ods_ba_isp_excel_sheet")
    op.drop_index("idx_ba_isp_workbook_cutoff", table_name="ods_ba_isp_excel_workbook")
    op.drop_index("idx_ba_isp_workbook_year", table_name="ods_ba_isp_excel_workbook")
    op.drop_table("ods_ba_isp_excel_workbook")
