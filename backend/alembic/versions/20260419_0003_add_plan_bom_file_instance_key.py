"""为计划 BOM 引入 Excel 开发期文件实例键

Revision ID: 20260419_0003
Revises: 20260418_0002
Create Date: 2026-04-19 18:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260419_0003"
down_revision = "20260418_0002"
branch_labels = None
depends_on = None


def _normalized_file_name_sql(column_name: str) -> str:
    """生成 MySQL 侧文件名归一化表达式。"""
    return (
        "LOWER("
        "REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE("
        f"COALESCE({column_name}, ''), ' ', ''), '_', ''), '-', ''), '(', ''), ')', ''), '（', ''), '）', '')"
        ")"
    )


def upgrade() -> None:
    """补充文件实例键，并允许同一业务实例同版本的多文件并存。"""

    op.add_column(
        "plan_bom_header",
        sa.Column("file_instance_key", sa.String(length=64), nullable=True, comment="Excel 开发期文件实例键，仅用于同业务实例同版本多文件并存"),
    )
    op.add_column(
        "plan_bom_material_line",
        sa.Column("file_instance_key", sa.String(length=64), nullable=True, comment="Excel 开发期文件实例键，仅用于同业务实例同版本多文件并存"),
    )
    op.add_column(
        "plan_bom_revision",
        sa.Column("file_instance_key", sa.String(length=64), nullable=True, comment="Excel 开发期文件实例键，仅用于同业务实例同版本多文件并存"),
    )

    normalized_file_name = _normalized_file_name_sql("header.raw_file_name")
    op.execute(
        f"""
        UPDATE plan_bom_header header
        LEFT JOIN plan_bom_import_batch batch
          ON batch.batch_id = header.import_batch_id
        SET header.file_instance_key = CASE
            WHEN COALESCE(batch.file_hash, '') <> ''
                THEN CONCAT(
                    'excel_file_',
                    SHA1(
                        CONCAT_WS(
                            '|',
                            COALESCE(header.order_identity_key, ''),
                            COALESCE(header.version_no, ''),
                            COALESCE(header.source_type, ''),
                            'hash',
                            batch.file_hash
                        )
                    )
                )
            ELSE CONCAT(
                'excel_file_',
                SHA1(
                    CONCAT_WS(
                        '|',
                        COALESCE(header.order_identity_key, ''),
                        COALESCE(header.version_no, ''),
                        COALESCE(header.source_type, ''),
                        'name',
                        {normalized_file_name}
                    )
                )
            )
        END
        WHERE header.file_instance_key IS NULL
        """
    )
    op.execute(
        """
        UPDATE plan_bom_material_line line
        JOIN plan_bom_header header
          ON line.order_identity_key = header.order_identity_key
         AND line.version_no = header.version_no
         AND line.source_type = header.source_type
         AND line.import_batch_id = header.import_batch_id
        SET line.file_instance_key = header.file_instance_key
        WHERE line.file_instance_key IS NULL
        """
    )
    op.execute(
        """
        UPDATE plan_bom_revision revision
        JOIN plan_bom_header header
          ON revision.order_identity_key = header.order_identity_key
         AND revision.version_no = header.version_no
         AND revision.source_type = header.source_type
         AND revision.import_batch_id = header.import_batch_id
        SET revision.file_instance_key = header.file_instance_key
        WHERE revision.file_instance_key IS NULL
        """
    )

    op.alter_column("plan_bom_header", "file_instance_key", existing_type=sa.String(length=64), nullable=False)
    op.alter_column("plan_bom_material_line", "file_instance_key", existing_type=sa.String(length=64), nullable=False)
    op.alter_column("plan_bom_revision", "file_instance_key", existing_type=sa.String(length=64), nullable=False)

    op.drop_constraint("uk_plan_bom_header_identity_version_source", "plan_bom_header", type_="unique")
    op.create_unique_constraint(
        "uk_plan_bom_header_identity_file_version_source",
        "plan_bom_header",
        ["order_identity_key", "file_instance_key", "version_no", "source_type"],
    )

    op.drop_constraint("uk_plan_bom_line_identity_version_sap_source", "plan_bom_material_line", type_="unique")
    op.create_unique_constraint(
        "uk_plan_bom_line_identity_file_version_sap_source",
        "plan_bom_material_line",
        ["order_identity_key", "file_instance_key", "version_no", "sap_code", "source_type"],
    )

    op.create_index(
        "idx_plan_bom_header_identity_version_source",
        "plan_bom_header",
        ["order_identity_key", "version_no", "source_type"],
        unique=False,
    )
    op.create_index("idx_plan_bom_header_file_instance", "plan_bom_header", ["file_instance_key"], unique=False)
    op.create_index(
        "idx_plan_bom_line_identity_file_version",
        "plan_bom_material_line",
        ["order_identity_key", "file_instance_key", "version_no"],
        unique=False,
    )
    op.create_index(
        "idx_plan_bom_revision_identity_file_version",
        "plan_bom_revision",
        ["order_identity_key", "file_instance_key", "version_no"],
        unique=False,
    )


def downgrade() -> None:
    """回滚 Excel 开发期文件实例键。"""

    op.drop_index("idx_plan_bom_revision_identity_file_version", table_name="plan_bom_revision")
    op.drop_index("idx_plan_bom_line_identity_file_version", table_name="plan_bom_material_line")
    op.drop_index("idx_plan_bom_header_file_instance", table_name="plan_bom_header")
    op.drop_index("idx_plan_bom_header_identity_version_source", table_name="plan_bom_header")

    op.drop_constraint("uk_plan_bom_line_identity_file_version_sap_source", "plan_bom_material_line", type_="unique")
    op.create_unique_constraint(
        "uk_plan_bom_line_identity_version_sap_source",
        "plan_bom_material_line",
        ["order_identity_key", "version_no", "sap_code", "source_type"],
    )

    op.drop_constraint("uk_plan_bom_header_identity_file_version_source", "plan_bom_header", type_="unique")
    op.create_unique_constraint(
        "uk_plan_bom_header_identity_version_source",
        "plan_bom_header",
        ["order_identity_key", "version_no", "source_type"],
    )

    op.drop_column("plan_bom_revision", "file_instance_key")
    op.drop_column("plan_bom_material_line", "file_instance_key")
    op.drop_column("plan_bom_header", "file_instance_key")
