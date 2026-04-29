"""创建计划 BOM 一期基础表

Revision ID: 20260416_0001
Revises:
Create Date: 2026-04-16 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260416_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建计划 BOM 一期 6 张基础表和必要索引。"""

    op.create_table(
        "plan_bom_import_batch",
        sa.Column("batch_id", sa.String(length=64), nullable=False, comment="导入批次号"),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="EXCEL", comment="数据来源类型，一期为 EXCEL，后续可扩展 SAP"),
        sa.Column("source_tag", sa.String(length=64), nullable=False, server_default="manual_import_source", comment="来源标记，Excel 开发期固定为 manual_import_source"),
        sa.Column("file_name", sa.String(length=512), nullable=False, comment="原始文件名"),
        sa.Column("file_hash", sa.String(length=128), nullable=True, comment="文件哈希，用于防重复导入"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending", comment="导入批次状态"),
        sa.Column("total_files", sa.Integer(), nullable=False, server_default="0", comment="本批次文件数量"),
        sa.Column("total_headers", sa.Integer(), nullable=False, server_default="0", comment="解析出的 BOM 头数量"),
        sa.Column("total_lines", sa.Integer(), nullable=False, server_default="0", comment="解析出的材料行数量"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="内部失败原因"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("finished_at", sa.DateTime(), nullable=True, comment="完成时间"),
        sa.PrimaryKeyConstraint("batch_id"),
        comment="计划 BOM Excel 导入批次表",
    )
    op.create_index("ix_plan_bom_import_batch_file_hash", "plan_bom_import_batch", ["file_hash"], unique=False)
    op.create_index("ix_plan_bom_import_batch_status", "plan_bom_import_batch", ["status"], unique=False)

    op.create_table(
        "plan_bom_header",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键"),
        sa.Column("order_no", sa.String(length=128), nullable=False, comment="订单号，评审号别名最终也查该字段"),
        sa.Column("version_no", sa.String(length=64), nullable=False, comment="版本号，例如 A0、A1、A10"),
        sa.Column("file_no", sa.String(length=128), nullable=True, comment="BOM 文件号"),
        sa.Column("order_name", sa.String(length=512), nullable=True, comment="订单名称，支持模糊查询"),
        sa.Column("effective_date", sa.Date(), nullable=True, comment="生效日期，当前版本排序优先字段"),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="EXCEL", comment="来源类型"),
        sa.Column("source_tag", sa.String(length=64), nullable=False, server_default="manual_import_source", comment="来源标记"),
        sa.Column("import_batch_id", sa.String(length=64), nullable=False, comment="导入批次号"),
        sa.Column("raw_file_name", sa.String(length=512), nullable=True, comment="原始文件名"),
        sa.Column("raw_sheet_name", sa.String(length=128), nullable=True, comment="原始 sheet 名"),
        sa.Column("is_active", sa.SmallInteger(), nullable=False, server_default="1", comment="是否当前有效记录，1 表示有效"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_no", "version_no", "source_type", name="uk_plan_bom_header_order_version_source"),
        comment="计划 BOM 头表",
    )
    op.create_index("idx_plan_bom_header_effective", "plan_bom_header", ["order_no", "effective_date"], unique=False)
    op.create_index("idx_plan_bom_header_order", "plan_bom_header", ["order_no"], unique=False)
    op.create_index("idx_plan_bom_header_order_name", "plan_bom_header", ["order_name"], unique=False)
    op.create_index("ix_plan_bom_header_import_batch_id", "plan_bom_header", ["import_batch_id"], unique=False)

    op.create_table(
        "plan_bom_material_line",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键"),
        sa.Column("order_no", sa.String(length=128), nullable=False, comment="订单号"),
        sa.Column("version_no", sa.String(length=64), nullable=False, comment="版本号"),
        sa.Column("sap_code", sa.String(length=128), nullable=False, comment="SAP 编码，材料行唯一键组成部分"),
        sa.Column("line_no", sa.String(length=64), nullable=True, comment="Excel 原始序号，不作为稳定主键"),
        sa.Column("material_name", sa.String(length=256), nullable=False, comment="原始物料名称"),
        sa.Column("material_category", sa.String(length=64), nullable=True, comment="系统材料归类"),
        sa.Column("description", sa.Text(), nullable=True, comment="原始规格描述"),
        sa.Column("standard_usage", sa.Numeric(precision=18, scale=6), nullable=True, comment="标准用量"),
        sa.Column("unit", sa.String(length=64), nullable=True, comment="单位"),
        sa.Column("production_loss", sa.String(length=64), nullable=True, comment="生产损耗，保留原始文本"),
        sa.Column("remark", sa.Text(), nullable=True, comment="备注"),
        sa.Column("replacement_marker", sa.String(length=32), nullable=True, comment="明确替代标识，仅原样展示"),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="EXCEL", comment="来源类型"),
        sa.Column("source_tag", sa.String(length=64), nullable=False, server_default="manual_import_source", comment="来源标记"),
        sa.Column("import_batch_id", sa.String(length=64), nullable=False, comment="导入批次号"),
        sa.Column("raw_row_no", sa.Integer(), nullable=True, comment="原始 Excel 行号"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_no", "version_no", "sap_code", "source_type", name="uk_plan_bom_line_order_version_sap_source"),
        comment="计划 BOM 材料明细表",
    )
    op.create_index("idx_plan_bom_line_category", "plan_bom_material_line", ["material_category"], unique=False)
    op.create_index("idx_plan_bom_line_order_version", "plan_bom_material_line", ["order_no", "version_no"], unique=False)
    op.create_index("idx_plan_bom_line_sap", "plan_bom_material_line", ["sap_code"], unique=False)
    op.create_index("ix_plan_bom_material_line_import_batch_id", "plan_bom_material_line", ["import_batch_id"], unique=False)

    op.create_table(
        "plan_bom_revision",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键"),
        sa.Column("order_no", sa.String(length=128), nullable=False, comment="订单号"),
        sa.Column("version_no", sa.String(length=64), nullable=False, comment="版本号"),
        sa.Column("revision_version", sa.String(length=64), nullable=True, comment="修订版本"),
        sa.Column("revision_content", sa.Text(), nullable=True, comment="修订内容"),
        sa.Column("reviser", sa.String(length=128), nullable=True, comment="修订人"),
        sa.Column("effective_date", sa.Date(), nullable=True, comment="生效日期"),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="EXCEL", comment="来源类型"),
        sa.Column("source_tag", sa.String(length=64), nullable=False, server_default="manual_import_source", comment="来源标记"),
        sa.Column("import_batch_id", sa.String(length=64), nullable=False, comment="导入批次号"),
        sa.Column("raw_row_no", sa.Integer(), nullable=True, comment="原始 Excel 行号"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.PrimaryKeyConstraint("id"),
        comment="计划 BOM 修订区表",
    )
    op.create_index("idx_plan_bom_revision_effective", "plan_bom_revision", ["order_no", "effective_date"], unique=False)
    op.create_index("idx_plan_bom_revision_order", "plan_bom_revision", ["order_no"], unique=False)
    op.create_index("idx_plan_bom_revision_version", "plan_bom_revision", ["order_no", "version_no"], unique=False)
    op.create_index("ix_plan_bom_revision_import_batch_id", "plan_bom_revision", ["import_batch_id"], unique=False)

    op.create_table(
        "plan_bom_export_task",
        sa.Column("export_id", sa.String(length=64), nullable=False, comment="导出任务 ID"),
        sa.Column("batch_id", sa.String(length=64), nullable=False, comment="导出批次号"),
        sa.Column("query_log_id", sa.BigInteger(), nullable=True, comment="关联 sys_query_log.id"),
        sa.Column("query_type", sa.String(length=64), nullable=False, comment="导出对应的查询类型"),
        sa.Column("export_format", sa.String(length=16), nullable=False, comment="导出格式，xlsx 或 csv"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending", comment="导出任务状态"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0", comment="导出总行数"),
        sa.Column("part_total", sa.Integer(), nullable=False, server_default="0", comment="总分段数"),
        sa.Column("expires_at", sa.DateTime(), nullable=False, comment="文件过期时间"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="内部失败原因"),
        sa.Column("user_message", sa.String(length=256), nullable=True, comment="用户可见提示"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.PrimaryKeyConstraint("export_id"),
        comment="计划 BOM 异步导出任务表",
    )
    op.create_index("idx_plan_bom_export_query_log", "plan_bom_export_task", ["query_log_id"], unique=False)
    op.create_index("idx_plan_bom_export_status", "plan_bom_export_task", ["status"], unique=False)
    op.create_index("ix_plan_bom_export_task_batch_id", "plan_bom_export_task", ["batch_id"], unique=False)

    op.create_table(
        "plan_bom_export_file",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键"),
        sa.Column("export_id", sa.String(length=64), nullable=False, comment="导出任务 ID"),
        sa.Column("part_no", sa.Integer(), nullable=False, comment="第几段，从 1 开始"),
        sa.Column("part_total", sa.Integer(), nullable=False, comment="总段数"),
        sa.Column("row_start", sa.Integer(), nullable=False, comment="起始行"),
        sa.Column("row_end", sa.Integer(), nullable=False, comment="结束行"),
        sa.Column("file_name", sa.String(length=512), nullable=False, comment="文件名"),
        sa.Column("file_path", sa.String(length=1024), nullable=False, comment="服务端存储路径"),
        sa.Column("file_size", sa.BigInteger(), nullable=True, comment="文件大小"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending", comment="分段文件状态"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("export_id", "part_no", name="uk_plan_bom_export_file_part"),
        comment="计划 BOM 导出分段文件表",
    )
    op.create_index("idx_plan_bom_export_file_export", "plan_bom_export_file", ["export_id"], unique=False)
    op.create_index("idx_plan_bom_export_file_status", "plan_bom_export_file", ["status"], unique=False)


def downgrade() -> None:
    """回滚计划 BOM 一期基础表。"""

    op.drop_index("idx_plan_bom_export_file_status", table_name="plan_bom_export_file")
    op.drop_index("idx_plan_bom_export_file_export", table_name="plan_bom_export_file")
    op.drop_table("plan_bom_export_file")

    op.drop_index("ix_plan_bom_export_task_batch_id", table_name="plan_bom_export_task")
    op.drop_index("idx_plan_bom_export_status", table_name="plan_bom_export_task")
    op.drop_index("idx_plan_bom_export_query_log", table_name="plan_bom_export_task")
    op.drop_table("plan_bom_export_task")

    op.drop_index("ix_plan_bom_revision_import_batch_id", table_name="plan_bom_revision")
    op.drop_index("idx_plan_bom_revision_version", table_name="plan_bom_revision")
    op.drop_index("idx_plan_bom_revision_order", table_name="plan_bom_revision")
    op.drop_index("idx_plan_bom_revision_effective", table_name="plan_bom_revision")
    op.drop_table("plan_bom_revision")

    op.drop_index("ix_plan_bom_material_line_import_batch_id", table_name="plan_bom_material_line")
    op.drop_index("idx_plan_bom_line_sap", table_name="plan_bom_material_line")
    op.drop_index("idx_plan_bom_line_order_version", table_name="plan_bom_material_line")
    op.drop_index("idx_plan_bom_line_category", table_name="plan_bom_material_line")
    op.drop_table("plan_bom_material_line")

    op.drop_index("ix_plan_bom_header_import_batch_id", table_name="plan_bom_header")
    op.drop_index("idx_plan_bom_header_order_name", table_name="plan_bom_header")
    op.drop_index("idx_plan_bom_header_order", table_name="plan_bom_header")
    op.drop_index("idx_plan_bom_header_effective", table_name="plan_bom_header")
    op.drop_table("plan_bom_header")

    op.drop_index("ix_plan_bom_import_batch_status", table_name="plan_bom_import_batch")
    op.drop_index("ix_plan_bom_import_batch_file_hash", table_name="plan_bom_import_batch")
    op.drop_table("plan_bom_import_batch")
