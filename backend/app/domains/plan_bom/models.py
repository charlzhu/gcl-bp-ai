from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Index, Integer, Numeric, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.domains.plan_bom.constants import (
    SOURCE_TAG_MANUAL_IMPORT,
    SOURCE_TYPE_EXCEL,
    STATUS_PENDING,
)

# 生产库建议使用 BigInteger；测试环境常用 SQLite 需要 INTEGER PRIMARY KEY 才能自动递增。
PLAN_BOM_ID_TYPE = BigInteger().with_variant(Integer, "sqlite")


class PlanBomImportBatch(Base):
    """计划 BOM Excel 导入批次表。

    设计说明：
    1. 本表只记录一次 Excel 入库的批次级信息；
    2. 真实解析、入库和覆盖策略在后续里程碑实现；
    3. 当前模型先固化批次号、来源、文件、状态和统计字段，便于后续追溯。
    """

    __tablename__ = "plan_bom_import_batch"

    batch_id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="导入批次号")
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SOURCE_TYPE_EXCEL,
        comment="数据来源类型，一期为 EXCEL，后续可扩展 SAP",
    )
    source_tag: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=SOURCE_TAG_MANUAL_IMPORT,
        comment="来源标记，Excel 开发期固定为 manual_import_source",
    )
    file_name: Mapped[str] = mapped_column(String(512), nullable=False, comment="原始文件名")
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True, comment="文件哈希，用于防重复导入")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=STATUS_PENDING, index=True, comment="导入批次状态")
    total_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="本批次文件数量")
    total_headers: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="解析出的 BOM 头数量")
    total_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="解析出的材料行数量")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="内部失败原因")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="完成时间")


class PlanBomHeader(Base):
    """计划 BOM 头表。

    设计说明：
    1. 业务唯一键为“订单号 + 版本号”；
    2. Excel 开发期额外引入 `order_identity_key` 作为内部实例键，用于区分同订单号下的不同实例；
    3. `file_instance_key` 只服务于“同一业务实例、同一版本下多文件并存”的开发期场景；
    4. `order_identity_key` 与 `file_instance_key` 都不替代正式业务主键；
    5. 查询层必须按来源优先级折算业务唯一版本，不能让 Excel 覆盖 SAP。
    """

    __tablename__ = "plan_bom_header"
    __table_args__ = (
        UniqueConstraint(
            "order_identity_key",
            "file_instance_key",
            "version_no",
            "source_type",
            name="uk_plan_bom_header_identity_file_version_source",
        ),
        Index("idx_plan_bom_header_order", "order_no"),
        Index("idx_plan_bom_header_order_name", "order_name"),
        Index("idx_plan_bom_header_effective", "order_no", "effective_date"),
        Index("idx_plan_bom_header_identity", "order_identity_key"),
        Index("idx_plan_bom_header_identity_version_source", "order_identity_key", "version_no", "source_type"),
        Index("idx_plan_bom_header_file_instance", "file_instance_key"),
    )

    id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, primary_key=True, autoincrement=True, comment="技术主键")
    order_no: Mapped[str] = mapped_column(String(128), nullable=False, comment="订单号，评审号别名最终也查该字段")
    version_no: Mapped[str] = mapped_column(String(64), nullable=False, comment="版本号，例如 A0、A1、A10")
    order_identity_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Excel 开发期内部实例键，仅用于导入覆盖、定位和候选识别，不替代业务主键",
    )
    file_instance_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Excel 开发期文件实例键，仅用于同业务实例同版本多文件并存，不替代业务主键",
    )
    file_no: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="BOM 文件号")
    order_name: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="订单名称，支持模糊查询")
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="生效日期，当前版本排序优先字段")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default=SOURCE_TYPE_EXCEL, comment="来源类型")
    source_tag: Mapped[str] = mapped_column(String(64), nullable=False, default=SOURCE_TAG_MANUAL_IMPORT, comment="来源标记")
    import_batch_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="导入批次号")
    raw_file_name: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="原始文件名")
    raw_sheet_name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="原始 sheet 名")
    is_active: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, comment="是否当前有效记录，1 表示有效")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )


class PlanBomMaterialLine(Base):
    """计划 BOM 材料明细表。

    设计说明：
    1. 业务唯一键为“订单号 + 版本号 + SAP编码”；
    2. Excel 开发期额外引入 `order_identity_key`，避免同订单号的不同实例互相覆盖；
    3. `file_instance_key` 只用于同一业务实例同版本多文件的并存控制；
    4. line_no 只用于展示和排查，不参与一期稳定唯一键；
    5. material_category 是系统归类字段，后续按“物料名称 + 描述”计算。
    """

    __tablename__ = "plan_bom_material_line"
    __table_args__ = (
        UniqueConstraint(
            "order_identity_key",
            "file_instance_key",
            "version_no",
            "sap_code",
            "source_type",
            name="uk_plan_bom_line_identity_file_version_sap_source",
        ),
        Index("idx_plan_bom_line_order_version", "order_no", "version_no"),
        Index("idx_plan_bom_line_category", "material_category"),
        Index("idx_plan_bom_line_sap", "sap_code"),
        Index("idx_plan_bom_line_identity_version", "order_identity_key", "version_no"),
        Index("idx_plan_bom_line_identity_file_version", "order_identity_key", "file_instance_key", "version_no"),
    )

    id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, primary_key=True, autoincrement=True, comment="技术主键")
    order_no: Mapped[str] = mapped_column(String(128), nullable=False, comment="订单号")
    version_no: Mapped[str] = mapped_column(String(64), nullable=False, comment="版本号")
    order_identity_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Excel 开发期内部实例键，仅用于导入覆盖和精确定位，不替代业务主键",
    )
    file_instance_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Excel 开发期文件实例键，仅用于同业务实例同版本多文件并存，不替代业务主键",
    )
    sap_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="SAP 编码，材料行唯一键组成部分")
    line_no: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="Excel 原始序号，不作为稳定主键")
    material_name: Mapped[str] = mapped_column(String(256), nullable=False, comment="原始物料名称")
    material_category: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="系统材料归类")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="原始规格描述")
    standard_usage: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True, comment="标准用量")
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="单位")
    production_loss: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="生产损耗，保留原始文本")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    replacement_marker: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="明确替代标识，仅原样展示")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default=SOURCE_TYPE_EXCEL, comment="来源类型")
    source_tag: Mapped[str] = mapped_column(String(64), nullable=False, default=SOURCE_TAG_MANUAL_IMPORT, comment="来源标记")
    import_batch_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="导入批次号")
    raw_row_no: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="原始 Excel 行号")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )


class PlanBomRevision(Base):
    """计划 BOM 修订区表。

    设计说明：
    1. 修订区用于当前版本判定和修订内容展示；
    2. 如果 Excel 修订区无法稳定拆行，后续入库服务可先保留原始修订内容；
    3. `file_instance_key` 用于同业务实例同版本多文件时保留各自修订事实；
    4. effective_date 和 version_no 是当前版本判定的核心字段。
    """

    __tablename__ = "plan_bom_revision"
    __table_args__ = (
        Index("idx_plan_bom_revision_order", "order_no"),
        Index("idx_plan_bom_revision_version", "order_no", "version_no"),
        Index("idx_plan_bom_revision_effective", "order_no", "effective_date"),
        Index("idx_plan_bom_revision_identity_version", "order_identity_key", "version_no"),
        Index("idx_plan_bom_revision_identity_file_version", "order_identity_key", "file_instance_key", "version_no"),
    )

    id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, primary_key=True, autoincrement=True, comment="技术主键")
    order_no: Mapped[str] = mapped_column(String(128), nullable=False, comment="订单号")
    version_no: Mapped[str] = mapped_column(String(64), nullable=False, comment="版本号")
    order_identity_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Excel 开发期内部实例键，仅用于定位同订单号下的不同实例",
    )
    file_instance_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Excel 开发期文件实例键，仅用于同业务实例同版本多文件并存，不替代业务主键",
    )
    revision_version: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="修订版本")
    revision_content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="修订内容")
    reviser: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="修订人")
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="生效日期")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default=SOURCE_TYPE_EXCEL, comment="来源类型")
    source_tag: Mapped[str] = mapped_column(String(64), nullable=False, default=SOURCE_TAG_MANUAL_IMPORT, comment="来源标记")
    import_batch_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="导入批次号")
    raw_row_no: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="原始 Excel 行号")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")


class PlanBomExportTask(Base):
    """计划 BOM 异步导出任务表。

    设计说明：
    1. 导出任务必须基于当前查询结果或查询历史快照；
    2. 单文件最多 500 行，分段文件由 PlanBomExportFile 记录；
    3. 本里程碑只定义模型，不实现导出任务调度和文件生成。
    """

    __tablename__ = "plan_bom_export_task"
    __table_args__ = (
        Index("idx_plan_bom_export_query_log", "query_log_id"),
        Index("idx_plan_bom_export_status", "status"),
    )

    export_id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="导出任务 ID")
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="导出批次号")
    query_log_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="关联 sys_query_log.id")
    query_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="导出对应的查询类型")
    export_format: Mapped[str] = mapped_column(String(16), nullable=False, comment="导出格式，xlsx 或 csv")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=STATUS_PENDING, comment="导出任务状态")
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="导出总行数")
    part_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="总分段数")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="文件过期时间")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="内部失败原因")
    user_message: Mapped[str | None] = mapped_column(String(256), nullable=True, comment="用户可见提示")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )


class PlanBomExportFile(Base):
    """计划 BOM 导出分段文件表。

    设计说明：
    1. 一个导出任务可产生多个分段文件；
    2. 每段最多 500 行且必须带表头；
    3. 本模型只固化分段元数据，不负责文件写入。
    """

    __tablename__ = "plan_bom_export_file"
    __table_args__ = (
        UniqueConstraint("export_id", "part_no", name="uk_plan_bom_export_file_part"),
        Index("idx_plan_bom_export_file_export", "export_id"),
        Index("idx_plan_bom_export_file_status", "status"),
    )

    id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, primary_key=True, autoincrement=True, comment="技术主键")
    export_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="导出任务 ID")
    part_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="第几段，从 1 开始")
    part_total: Mapped[int] = mapped_column(Integer, nullable=False, comment="总段数")
    row_start: Mapped[int] = mapped_column(Integer, nullable=False, comment="起始行")
    row_end: Mapped[int] = mapped_column(Integer, nullable=False, comment="结束行")
    file_name: Mapped[str] = mapped_column(String(512), nullable=False, comment="文件名")
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, comment="服务端存储路径")
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="文件大小")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=STATUS_PENDING, comment="分段文件状态")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")


__all__ = [
    "PlanBomImportBatch",
    "PlanBomHeader",
    "PlanBomMaterialLine",
    "PlanBomRevision",
    "PlanBomExportTask",
    "PlanBomExportFile",
]
