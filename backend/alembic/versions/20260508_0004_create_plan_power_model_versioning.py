"""创建计划 BOM 功率模型版本化表

Revision ID: 20260508_0004
Revises: 20260419_0003
Create Date: 2026-05-08 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260508_0004"
down_revision = "20260419_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 M2 功率模型版本化入库所需的 8 张 plan_power 表。"""

    op.create_table(
        "plan_power_model_version",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键"),
        sa.Column("file_name", sa.String(length=512), nullable=False, comment="原始 xlsm 文件名"),
        sa.Column("file_hash", sa.String(length=128), nullable=False, comment="文件 SHA256，用于防重复导入"),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="xlsm", comment="来源类型，M2 固定为 xlsm"),
        sa.Column("business_version_label", sa.String(length=128), nullable=True, comment="业务版本标签，例如 TOPCon 26.04.13"),
        sa.Column("formula_policy", sa.String(length=64), nullable=False, server_default="semantic_fixed_mode", comment="公式策略"),
        sa.Column("vba_project_sha256", sa.String(length=128), nullable=True, comment="VBA 工程 SHA256，用于宏来源追溯"),
        sa.Column("is_active", sa.SmallInteger(), nullable=False, server_default="0", comment="是否当前激活版本，1 表示激活"),
        sa.Column("parse_status", sa.String(length=32), nullable=False, server_default="success", comment="解析状态"),
        sa.Column("sheet_count", sa.Integer(), nullable=False, server_default="0", comment="Workbook sheet 总数"),
        sa.Column("model_sheet_count", sa.Integer(), nullable=False, server_default="0", comment="有效模型页数量"),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0", comment="解析 warning 数量"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0", comment="解析 error 数量"),
        sa.Column("parse_summary_json", sa.Text(), nullable=True, comment="解析摘要 JSON"),
        sa.Column("warning_json", sa.Text(), nullable=True, comment="解析 warning JSON"),
        sa.Column("change_history_json", sa.Text(), nullable=True, comment="更改履历 JSON，用于模型版本追溯"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("activated_at", sa.DateTime(), nullable=True, comment="激活时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_hash", name="uk_plan_power_model_version_file_hash"),
        comment="计划 BOM 功率模型版本表",
    )
    op.create_index("idx_plan_power_model_version_active", "plan_power_model_version", ["is_active"], unique=False)
    op.create_index("idx_plan_power_model_version_status", "plan_power_model_version", ["parse_status"], unique=False)

    op.create_table(
        "plan_power_model_sheet",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键"),
        sa.Column("version_id", sa.BigInteger(), nullable=False, comment="模型版本 ID"),
        sa.Column("sheet_name", sa.String(length=128), nullable=False, comment="Excel 原始 Sheet 名"),
        sa.Column("normalized_model_code", sa.String(length=128), nullable=False, comment="归一化版型编码"),
        sa.Column("cell_count", sa.Integer(), nullable=True, comment="组件电池片数量"),
        sa.Column("base_power", sa.Numeric(precision=18, scale=6), nullable=True, comment="基础功率，来源 J1 缓存值"),
        sa.Column("center_power_cell", sa.String(length=32), nullable=True, comment="中心功率单元格"),
        sa.Column("area_default", sa.Numeric(precision=18, scale=6), nullable=True, comment="默认面积，来源 B14"),
        sa.Column("std_dev_default", sa.Numeric(precision=18, scale=6), nullable=True, comment="默认标准差，来源 B15"),
        sa.Column("source_range", sa.String(length=64), nullable=True, comment="原始 sheet 数据范围"),
        sa.Column("raw_meta_json", sa.Text(), nullable=True, comment="Sheet 原始元数据 JSON"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.ForeignKeyConstraint(["version_id"], ["plan_power_model_version.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "sheet_name", name="uk_plan_power_model_sheet_version_sheet"),
        comment="计划 BOM 功率模型 Sheet 表",
    )
    op.create_index("idx_plan_power_model_sheet_model_code", "plan_power_model_sheet", ["normalized_model_code"], unique=False)
    op.create_index("idx_plan_power_model_sheet_version", "plan_power_model_sheet", ["version_id"], unique=False)

    op.create_table(
        "plan_power_factor_option",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键"),
        sa.Column("version_id", sa.BigInteger(), nullable=False, comment="模型版本 ID"),
        sa.Column("sheet_id", sa.BigInteger(), nullable=False, comment="模型 Sheet ID"),
        sa.Column("factor_key", sa.String(length=64), nullable=False, comment="配置项 key"),
        sa.Column("option_label", sa.String(length=256), nullable=False, comment="Excel 原始选项名"),
        sa.Column("normalized_option_label", sa.String(length=256), nullable=False, comment="归一化选项名"),
        sa.Column("effect_value", sa.Numeric(precision=18, scale=6), nullable=True, comment="功率影响值"),
        sa.Column("area_value", sa.Numeric(precision=18, scale=6), nullable=True, comment="电池尺寸对应面积"),
        sa.Column("std_dev_value", sa.Numeric(precision=18, scale=6), nullable=True, comment="电池尺寸对应标准差"),
        sa.Column("source_cell_ref", sa.String(length=32), nullable=False, comment="选项原始单元格"),
        sa.Column("is_default", sa.SmallInteger(), nullable=False, server_default="0", comment="是否 Excel 当前默认选中项"),
        sa.Column("is_valid", sa.SmallInteger(), nullable=False, server_default="1", comment="是否有效业务选项"),
        sa.Column("invalid_reason", sa.String(length=512), nullable=True, comment="无效原因"),
        sa.Column("raw_json", sa.Text(), nullable=True, comment="原始解析 JSON"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.ForeignKeyConstraint(["sheet_id"], ["plan_power_model_sheet.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["plan_power_model_version.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="计划 BOM 功率模型配置选项表",
    )
    op.create_index("idx_plan_power_factor_option_key", "plan_power_factor_option", ["factor_key"], unique=False)
    op.create_index("idx_plan_power_factor_option_sheet", "plan_power_factor_option", ["sheet_id"], unique=False)
    op.create_index("idx_plan_power_factor_option_valid", "plan_power_factor_option", ["is_valid"], unique=False)
    op.create_index("idx_plan_power_factor_option_version", "plan_power_factor_option", ["version_id"], unique=False)

    op.create_table(
        "plan_power_supplier_efficiency_distribution",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键"),
        sa.Column("version_id", sa.BigInteger(), nullable=False, comment="模型版本 ID"),
        sa.Column("sheet_id", sa.BigInteger(), nullable=False, comment="模型 Sheet ID"),
        sa.Column("supplier_name", sa.String(length=128), nullable=False, comment="Excel 原始供应商名称"),
        sa.Column("normalized_supplier_name", sa.String(length=128), nullable=False, comment="归一化供应商名称"),
        sa.Column("efficiency_value", sa.Numeric(precision=18, scale=8), nullable=False, comment="效率段值"),
        sa.Column("ratio_value", sa.Numeric(precision=18, scale=10), nullable=False, comment="该效率段比例"),
        sa.Column("source_cell_ref", sa.String(length=32), nullable=False, comment="比例来源单元格"),
        sa.Column("is_valid", sa.SmallInteger(), nullable=False, server_default="1", comment="是否有效"),
        sa.Column("invalid_reason", sa.String(length=512), nullable=True, comment="无效原因"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.ForeignKeyConstraint(["sheet_id"], ["plan_power_model_sheet.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["plan_power_model_version.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="计划 BOM 功率模型供应商效率分布表",
    )
    op.create_index("idx_plan_power_supplier_distribution_sheet", "plan_power_supplier_efficiency_distribution", ["sheet_id"], unique=False)
    op.create_index("idx_plan_power_supplier_distribution_supplier", "plan_power_supplier_efficiency_distribution", ["normalized_supplier_name"], unique=False)
    op.create_index("idx_plan_power_supplier_distribution_version", "plan_power_supplier_efficiency_distribution", ["version_id"], unique=False)

    op.create_table(
        "plan_power_power_bin",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键"),
        sa.Column("version_id", sa.BigInteger(), nullable=False, comment="模型版本 ID"),
        sa.Column("sheet_id", sa.BigInteger(), nullable=False, comment="模型 Sheet ID"),
        sa.Column("power_bin", sa.Numeric(precision=10, scale=2), nullable=False, comment="功率档位"),
        sa.Column("bin_order", sa.Integer(), nullable=False, comment="档位顺序，从 1 开始"),
        sa.Column("source_cell_ref", sa.String(length=32), nullable=False, comment="档位来源单元格"),
        sa.Column("is_valid", sa.SmallInteger(), nullable=False, server_default="1", comment="是否有效功率档"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.ForeignKeyConstraint(["sheet_id"], ["plan_power_model_sheet.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["plan_power_model_version.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sheet_id", "bin_order", name="uk_plan_power_power_bin_sheet_order"),
        comment="计划 BOM 功率模型功率档位表",
    )
    op.create_index("idx_plan_power_power_bin_sheet", "plan_power_power_bin", ["sheet_id"], unique=False)
    op.create_index("idx_plan_power_power_bin_version", "plan_power_power_bin", ["version_id"], unique=False)

    op.create_table(
        "plan_power_benchmark_factor",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键"),
        sa.Column("version_id", sa.BigInteger(), nullable=False, comment="模型版本 ID"),
        sa.Column("model_code", sa.String(length=128), nullable=False, comment="版型编码"),
        sa.Column("benchmark_name", sa.String(length=128), nullable=False, comment="Excel 原始标板列名"),
        sa.Column("normalized_benchmark_name", sa.String(length=128), nullable=False, comment="系统归一标板名称"),
        sa.Column("effect_value", sa.Numeric(precision=18, scale=6), nullable=True, comment="标板影响值；功率最优列可为空"),
        sa.Column("source_sheet_name", sa.String(length=128), nullable=False, comment="来源 Sheet 名"),
        sa.Column("source_cell_ref", sa.String(length=32), nullable=False, comment="来源单元格"),
        sa.Column("raw_json", sa.Text(), nullable=True, comment="原始解析 JSON"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.ForeignKeyConstraint(["version_id"], ["plan_power_model_version.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="计划 BOM 功率模型标板基准表",
    )
    op.create_index("idx_plan_power_benchmark_model", "plan_power_benchmark_factor", ["model_code"], unique=False)
    op.create_index("idx_plan_power_benchmark_version", "plan_power_benchmark_factor", ["version_id"], unique=False)

    op.create_table(
        "plan_power_model_validation_case",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键"),
        sa.Column("version_id", sa.BigInteger(), nullable=False, comment="模型版本 ID"),
        sa.Column("model_code", sa.String(length=128), nullable=True, comment="版型编码"),
        sa.Column("case_name", sa.String(length=256), nullable=True, comment="校验用例名称"),
        sa.Column("input_json", sa.Text(), nullable=True, comment="输入配置 JSON"),
        sa.Column("excel_expected_json", sa.Text(), nullable=True, comment="Excel 期望值 JSON"),
        sa.Column("system_result_json", sa.Text(), nullable=True, comment="系统计算值 JSON"),
        sa.Column("diff_json", sa.Text(), nullable=True, comment="差异 JSON"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending", comment="校验状态"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.ForeignKeyConstraint(["version_id"], ["plan_power_model_version.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="计划 BOM 功率模型校验用例预留表",
    )
    op.create_index("idx_plan_power_validation_model", "plan_power_model_validation_case", ["model_code"], unique=False)
    op.create_index("idx_plan_power_validation_status", "plan_power_model_validation_case", ["status"], unique=False)
    op.create_index("idx_plan_power_validation_version", "plan_power_model_validation_case", ["version_id"], unique=False)

    op.create_table(
        "plan_power_parse_issue",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键"),
        sa.Column("version_id", sa.BigInteger(), nullable=False, comment="模型版本 ID"),
        sa.Column("sheet_id", sa.BigInteger(), nullable=True, comment="模型 Sheet ID，可为空"),
        sa.Column("level", sa.String(length=32), nullable=False, comment="问题级别：warning / error"),
        sa.Column("issue_code", sa.String(length=128), nullable=False, comment="问题编码"),
        sa.Column("message", sa.Text(), nullable=False, comment="问题说明"),
        sa.Column("source_sheet_name", sa.String(length=128), nullable=True, comment="来源 Sheet 名"),
        sa.Column("source_cell_ref", sa.String(length=32), nullable=True, comment="来源单元格"),
        sa.Column("raw_json", sa.Text(), nullable=True, comment="原始上下文 JSON"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.ForeignKeyConstraint(["sheet_id"], ["plan_power_model_sheet.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["plan_power_model_version.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="计划 BOM 功率模型解析问题表",
    )
    op.create_index("idx_plan_power_parse_issue_code", "plan_power_parse_issue", ["issue_code"], unique=False)
    op.create_index("idx_plan_power_parse_issue_level", "plan_power_parse_issue", ["level"], unique=False)
    op.create_index("idx_plan_power_parse_issue_sheet", "plan_power_parse_issue", ["sheet_id"], unique=False)
    op.create_index("idx_plan_power_parse_issue_version", "plan_power_parse_issue", ["version_id"], unique=False)


def downgrade() -> None:
    """回滚 M2 功率模型版本化表。"""

    op.drop_index("idx_plan_power_parse_issue_version", table_name="plan_power_parse_issue")
    op.drop_index("idx_plan_power_parse_issue_sheet", table_name="plan_power_parse_issue")
    op.drop_index("idx_plan_power_parse_issue_level", table_name="plan_power_parse_issue")
    op.drop_index("idx_plan_power_parse_issue_code", table_name="plan_power_parse_issue")
    op.drop_table("plan_power_parse_issue")

    op.drop_index("idx_plan_power_validation_version", table_name="plan_power_model_validation_case")
    op.drop_index("idx_plan_power_validation_status", table_name="plan_power_model_validation_case")
    op.drop_index("idx_plan_power_validation_model", table_name="plan_power_model_validation_case")
    op.drop_table("plan_power_model_validation_case")

    op.drop_index("idx_plan_power_benchmark_version", table_name="plan_power_benchmark_factor")
    op.drop_index("idx_plan_power_benchmark_model", table_name="plan_power_benchmark_factor")
    op.drop_table("plan_power_benchmark_factor")

    op.drop_index("idx_plan_power_power_bin_version", table_name="plan_power_power_bin")
    op.drop_index("idx_plan_power_power_bin_sheet", table_name="plan_power_power_bin")
    op.drop_table("plan_power_power_bin")

    op.drop_index("idx_plan_power_supplier_distribution_version", table_name="plan_power_supplier_efficiency_distribution")
    op.drop_index("idx_plan_power_supplier_distribution_supplier", table_name="plan_power_supplier_efficiency_distribution")
    op.drop_index("idx_plan_power_supplier_distribution_sheet", table_name="plan_power_supplier_efficiency_distribution")
    op.drop_table("plan_power_supplier_efficiency_distribution")

    op.drop_index("idx_plan_power_factor_option_version", table_name="plan_power_factor_option")
    op.drop_index("idx_plan_power_factor_option_valid", table_name="plan_power_factor_option")
    op.drop_index("idx_plan_power_factor_option_sheet", table_name="plan_power_factor_option")
    op.drop_index("idx_plan_power_factor_option_key", table_name="plan_power_factor_option")
    op.drop_table("plan_power_factor_option")

    op.drop_index("idx_plan_power_model_sheet_version", table_name="plan_power_model_sheet")
    op.drop_index("idx_plan_power_model_sheet_model_code", table_name="plan_power_model_sheet")
    op.drop_table("plan_power_model_sheet")

    op.drop_index("idx_plan_power_model_version_status", table_name="plan_power_model_version")
    op.drop_index("idx_plan_power_model_version_active", table_name="plan_power_model_version")
    op.drop_table("plan_power_model_version")
