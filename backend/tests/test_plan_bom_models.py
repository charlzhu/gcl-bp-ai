from __future__ import annotations

from sqlalchemy import UniqueConstraint

from backend.app.db.base import Base
from backend.app.domains.plan_bom.models import (
    PlanBomExportFile,
    PlanBomHeader,
    PlanBomMaterialLine,
)
from backend.app.models import PlanBomImportBatch


def _unique_constraint_names(table_name: str) -> set[str]:
    """读取指定表上的唯一约束名称。

    参数：
        table_name: 已注册到 Base.metadata 的表名。

    返回：
        唯一约束名称集合，用于验证模型契约是否符合 BOM 一期设计。
    """
    table = Base.metadata.tables[table_name]
    return {constraint.name for constraint in table.constraints if isinstance(constraint, UniqueConstraint)}


def test_plan_bom_tables_registered_in_metadata() -> None:
    """验证计划 BOM 一期数据表已经注册到 SQLAlchemy 元数据。"""
    expected_tables = {
        "plan_bom_import_batch",
        "plan_bom_header",
        "plan_bom_material_line",
        "plan_bom_revision",
        "plan_bom_export_task",
        "plan_bom_export_file",
    }

    assert expected_tables.issubset(set(Base.metadata.tables))
    assert PlanBomImportBatch.__tablename__ == "plan_bom_import_batch"


def test_plan_bom_unique_keys_match_design_baseline() -> None:
    """验证 BOM 头、材料行和导出文件的唯一键符合当前实例键设计基线。"""
    assert "uk_plan_bom_header_identity_file_version_source" in _unique_constraint_names(PlanBomHeader.__tablename__)
    assert "uk_plan_bom_line_identity_file_version_sap_source" in _unique_constraint_names(PlanBomMaterialLine.__tablename__)
    assert "uk_plan_bom_export_file_part" in _unique_constraint_names(PlanBomExportFile.__tablename__)


def test_plan_bom_source_and_trace_columns_exist() -> None:
    """验证来源追溯和批次追溯字段已覆盖核心业务表。"""
    header_columns = set(PlanBomHeader.__table__.columns.keys())
    line_columns = set(PlanBomMaterialLine.__table__.columns.keys())

    assert {"source_type", "source_tag", "import_batch_id"}.issubset(header_columns)
    assert {"source_type", "source_tag", "import_batch_id", "raw_row_no"}.issubset(line_columns)
