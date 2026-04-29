"""为计划 BOM 引入 Excel 开发期内部实例键

Revision ID: 20260418_0002
Revises: 20260416_0001
Create Date: 2026-04-18 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260418_0002"
down_revision = "20260416_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """补充 Excel 开发期内部实例键，并放宽同订单号实例的共存能力。"""

    op.add_column(
        "plan_bom_header",
        sa.Column("order_identity_key", sa.String(length=64), nullable=True, comment="Excel 开发期内部实例键，仅用于导入覆盖和候选识别"),
    )
    op.add_column(
        "plan_bom_material_line",
        sa.Column("order_identity_key", sa.String(length=64), nullable=True, comment="Excel 开发期内部实例键，仅用于导入覆盖和精确定位"),
    )
    op.add_column(
        "plan_bom_revision",
        sa.Column("order_identity_key", sa.String(length=64), nullable=True, comment="Excel 开发期内部实例键，仅用于定位同订单号下的不同实例"),
    )

    op.execute(
        """
        UPDATE plan_bom_header
        SET order_identity_key = CONCAT(
            'excel_inst_',
            SHA1(CONCAT_WS('|', COALESCE(order_no, ''), COALESCE(order_name, ''), COALESCE(raw_file_name, '')))
        )
        WHERE order_identity_key IS NULL
        """
    )
    op.execute(
        """
        UPDATE plan_bom_material_line line
        JOIN plan_bom_header header
          ON line.order_no = header.order_no
         AND line.version_no = header.version_no
         AND line.source_type = header.source_type
        SET line.order_identity_key = header.order_identity_key
        WHERE line.order_identity_key IS NULL
        """
    )
    op.execute(
        """
        UPDATE plan_bom_revision revision
        JOIN plan_bom_header header
          ON revision.order_no = header.order_no
         AND revision.version_no = header.version_no
         AND revision.source_type = header.source_type
        SET revision.order_identity_key = header.order_identity_key
        WHERE revision.order_identity_key IS NULL
        """
    )

    op.alter_column("plan_bom_header", "order_identity_key", existing_type=sa.String(length=64), nullable=False)
    op.alter_column("plan_bom_material_line", "order_identity_key", existing_type=sa.String(length=64), nullable=False)
    op.alter_column("plan_bom_revision", "order_identity_key", existing_type=sa.String(length=64), nullable=False)

    op.drop_constraint("uk_plan_bom_header_order_version_source", "plan_bom_header", type_="unique")
    op.create_unique_constraint(
        "uk_plan_bom_header_identity_version_source",
        "plan_bom_header",
        ["order_identity_key", "version_no", "source_type"],
    )
    op.drop_constraint("uk_plan_bom_line_order_version_sap_source", "plan_bom_material_line", type_="unique")
    op.create_unique_constraint(
        "uk_plan_bom_line_identity_version_sap_source",
        "plan_bom_material_line",
        ["order_identity_key", "version_no", "sap_code", "source_type"],
    )

    op.create_index("idx_plan_bom_header_identity", "plan_bom_header", ["order_identity_key"], unique=False)
    op.create_index("idx_plan_bom_line_identity_version", "plan_bom_material_line", ["order_identity_key", "version_no"], unique=False)
    op.create_index("idx_plan_bom_revision_identity_version", "plan_bom_revision", ["order_identity_key", "version_no"], unique=False)


def downgrade() -> None:
    """回滚 Excel 开发期内部实例键。"""

    op.drop_index("idx_plan_bom_revision_identity_version", table_name="plan_bom_revision")
    op.drop_index("idx_plan_bom_line_identity_version", table_name="plan_bom_material_line")
    op.drop_index("idx_plan_bom_header_identity", table_name="plan_bom_header")

    op.drop_constraint("uk_plan_bom_line_identity_version_sap_source", "plan_bom_material_line", type_="unique")
    op.create_unique_constraint(
        "uk_plan_bom_line_order_version_sap_source",
        "plan_bom_material_line",
        ["order_no", "version_no", "sap_code", "source_type"],
    )
    op.drop_constraint("uk_plan_bom_header_identity_version_source", "plan_bom_header", type_="unique")
    op.create_unique_constraint(
        "uk_plan_bom_header_order_version_source",
        "plan_bom_header",
        ["order_no", "version_no", "source_type"],
    )

    op.drop_column("plan_bom_revision", "order_identity_key")
    op.drop_column("plan_bom_material_line", "order_identity_key")
    op.drop_column("plan_bom_header", "order_identity_key")
