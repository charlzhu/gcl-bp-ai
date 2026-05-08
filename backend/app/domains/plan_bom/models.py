from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, Numeric, SmallInteger, String, Text, UniqueConstraint, func
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


class PlanPowerModelVersion(Base):
    """计划 BOM 功率模型版本表。

    设计说明：
    1. 每次导入 xlsm 后生成一个可追溯模型版本；
    2. 使用 file_hash 做幂等防重复，避免同一源文件重复入库；
    3. M2 只保存解析结构和问题清单，不承载正式功率计算结果。
    """

    __tablename__ = "plan_power_model_version"
    __table_args__ = (
        UniqueConstraint("file_hash", name="uk_plan_power_model_version_file_hash"),
        Index("idx_plan_power_model_version_active", "is_active"),
        Index("idx_plan_power_model_version_status", "parse_status"),
    )

    id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, primary_key=True, autoincrement=True, comment="技术主键")
    file_name: Mapped[str] = mapped_column(String(512), nullable=False, comment="原始 xlsm 文件名")
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False, comment="文件 SHA256，用于防重复导入")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="xlsm", comment="来源类型，M2 固定为 xlsm")
    business_version_label: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="业务版本标签，例如 TOPCon 26.04.13")
    formula_policy: Mapped[str] = mapped_column(String(64), nullable=False, default="semantic_fixed_mode", comment="公式策略，M2 固定为 semantic_fixed_mode")
    vba_project_sha256: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="VBA 工程 SHA256，用于宏来源追溯")
    is_active: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否当前激活版本，1 表示激活")
    parse_status: Mapped[str] = mapped_column(String(32), nullable=False, default="success", comment="解析状态：success / warning / failed")
    sheet_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Workbook sheet 总数")
    model_sheet_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="有效模型页数量")
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="解析 warning 数量")
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="解析 error 数量")
    parse_summary_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="解析摘要 JSON")
    warning_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="解析 warning JSON")
    change_history_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="更改履历 JSON，用于模型版本追溯")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="激活时间")


class PlanPowerModelSheet(Base):
    """计划 BOM 功率模型 Sheet 表。

    设计说明：
    1. 保存每个版型模型页的稳定元数据；
    2. 原始 sheet_name 保留尾随空格等 Excel 事实；
    3. normalized_model_code 用于后续 M3/M4 按版型查询模型。
    """

    __tablename__ = "plan_power_model_sheet"
    __table_args__ = (
        UniqueConstraint("version_id", "sheet_name", name="uk_plan_power_model_sheet_version_sheet"),
        Index("idx_plan_power_model_sheet_version", "version_id"),
        Index("idx_plan_power_model_sheet_model_code", "normalized_model_code"),
    )

    id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, primary_key=True, autoincrement=True, comment="技术主键")
    version_id: Mapped[int] = mapped_column(
        PLAN_BOM_ID_TYPE,
        ForeignKey("plan_power_model_version.id", ondelete="CASCADE"),
        nullable=False,
        comment="模型版本 ID",
    )
    sheet_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="Excel 原始 Sheet 名")
    normalized_model_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="归一化版型编码")
    cell_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="组件电池片数量，例如 66 / 78")
    base_power: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True, comment="基础功率，来源 J1 缓存值")
    center_power_cell: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="中心功率单元格，当前为 I36")
    area_default: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True, comment="默认面积，来源 B14")
    std_dev_default: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True, comment="默认标准差，来源 B15")
    source_range: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="原始 sheet 数据范围")
    raw_meta_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Sheet 原始元数据 JSON")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")


class PlanPowerFactorOption(Base):
    """计划 BOM 功率模型配置选项表。

    设计说明：
    1. 保存配置项、选项名、影响值与原始单元格；
    2. 占位选项和缺失影响值会保留为无效项，便于后续排查 Excel 模板质量；
    3. M2 不做正式配置匹配，只提供可查询结构化模型。
    """

    __tablename__ = "plan_power_factor_option"
    __table_args__ = (
        Index("idx_plan_power_factor_option_version", "version_id"),
        Index("idx_plan_power_factor_option_sheet", "sheet_id"),
        Index("idx_plan_power_factor_option_key", "factor_key"),
        Index("idx_plan_power_factor_option_valid", "is_valid"),
    )

    id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, primary_key=True, autoincrement=True, comment="技术主键")
    version_id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, ForeignKey("plan_power_model_version.id", ondelete="CASCADE"), nullable=False, comment="模型版本 ID")
    sheet_id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, ForeignKey("plan_power_model_sheet.id", ondelete="CASCADE"), nullable=False, comment="模型 Sheet ID")
    factor_key: Mapped[str] = mapped_column(String(64), nullable=False, comment="配置项 key，例如 ribbon / glass / supplier")
    option_label: Mapped[str] = mapped_column(String(256), nullable=False, comment="Excel 原始选项名")
    normalized_option_label: Mapped[str] = mapped_column(String(256), nullable=False, comment="归一化选项名")
    effect_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True, comment="功率影响值")
    area_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True, comment="电池尺寸对应面积")
    std_dev_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True, comment="电池尺寸对应标准差")
    source_cell_ref: Mapped[str] = mapped_column(String(32), nullable=False, comment="选项原始单元格")
    is_default: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否 Excel 当前默认选中项")
    is_valid: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, comment="是否有效业务选项")
    invalid_reason: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="无效原因")
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="原始解析 JSON")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")


class PlanPowerSupplierEfficiencyDistribution(Base):
    """计划 BOM 功率模型供应商效率分布表。

    设计说明：
    1. 保存有效供应商在各效率段的比例；
    2. 无效供应商标题只记录 parse issue，不作为有效供应商分布入库；
    3. M3 计算引擎将基于本表做效率段加权。
    """

    __tablename__ = "plan_power_supplier_efficiency_distribution"
    __table_args__ = (
        Index("idx_plan_power_supplier_distribution_version", "version_id"),
        Index("idx_plan_power_supplier_distribution_sheet", "sheet_id"),
        Index("idx_plan_power_supplier_distribution_supplier", "normalized_supplier_name"),
    )

    id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, primary_key=True, autoincrement=True, comment="技术主键")
    version_id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, ForeignKey("plan_power_model_version.id", ondelete="CASCADE"), nullable=False, comment="模型版本 ID")
    sheet_id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, ForeignKey("plan_power_model_sheet.id", ondelete="CASCADE"), nullable=False, comment="模型 Sheet ID")
    supplier_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="Excel 原始供应商名称")
    normalized_supplier_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="归一化供应商名称")
    efficiency_value: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, comment="效率段值")
    ratio_value: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False, comment="该效率段比例")
    source_cell_ref: Mapped[str] = mapped_column(String(32), nullable=False, comment="比例来源单元格")
    is_valid: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, comment="是否有效")
    invalid_reason: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="无效原因")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")


class PlanPowerPowerBin(Base):
    """计划 BOM 功率模型功率档位表。"""

    __tablename__ = "plan_power_power_bin"
    __table_args__ = (
        UniqueConstraint("sheet_id", "bin_order", name="uk_plan_power_power_bin_sheet_order"),
        Index("idx_plan_power_power_bin_version", "version_id"),
        Index("idx_plan_power_power_bin_sheet", "sheet_id"),
    )

    id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, primary_key=True, autoincrement=True, comment="技术主键")
    version_id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, ForeignKey("plan_power_model_version.id", ondelete="CASCADE"), nullable=False, comment="模型版本 ID")
    sheet_id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, ForeignKey("plan_power_model_sheet.id", ondelete="CASCADE"), nullable=False, comment="模型 Sheet ID")
    power_bin: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment="功率档位")
    bin_order: Mapped[int] = mapped_column(Integer, nullable=False, comment="档位顺序，从 1 开始")
    source_cell_ref: Mapped[str] = mapped_column(String(32), nullable=False, comment="档位来源单元格")
    is_valid: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, comment="是否有效功率档")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")


class PlanPowerBenchmarkFactor(Base):
    """计划 BOM 功率模型标板基准表。"""

    __tablename__ = "plan_power_benchmark_factor"
    __table_args__ = (
        Index("idx_plan_power_benchmark_version", "version_id"),
        Index("idx_plan_power_benchmark_model", "model_code"),
    )

    id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, primary_key=True, autoincrement=True, comment="技术主键")
    version_id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, ForeignKey("plan_power_model_version.id", ondelete="CASCADE"), nullable=False, comment="模型版本 ID")
    model_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="版型编码")
    benchmark_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="Excel 原始标板列名")
    normalized_benchmark_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="系统归一标板名称")
    effect_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True, comment="标板影响值；功率最优列可为空")
    source_sheet_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="来源 Sheet 名")
    source_cell_ref: Mapped[str] = mapped_column(String(32), nullable=False, comment="来源单元格")
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="原始解析 JSON")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")


class PlanPowerModelValidationCase(Base):
    """计划 BOM 功率模型校验用例预留表。

    设计说明：
    M2 只建表预留，M3 才会写入 Excel parity / 抽样校验结果。
    """

    __tablename__ = "plan_power_model_validation_case"
    __table_args__ = (
        Index("idx_plan_power_validation_version", "version_id"),
        Index("idx_plan_power_validation_model", "model_code"),
        Index("idx_plan_power_validation_status", "status"),
    )

    id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, primary_key=True, autoincrement=True, comment="技术主键")
    version_id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, ForeignKey("plan_power_model_version.id", ondelete="CASCADE"), nullable=False, comment="模型版本 ID")
    model_code: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="版型编码")
    case_name: Mapped[str | None] = mapped_column(String(256), nullable=True, comment="校验用例名称")
    input_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="输入配置 JSON")
    excel_expected_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Excel 期望值 JSON")
    system_result_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="系统计算值 JSON")
    diff_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="差异 JSON")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", comment="校验状态")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")


class PlanPowerParseIssue(Base):
    """计划 BOM 功率模型解析问题表。"""

    __tablename__ = "plan_power_parse_issue"
    __table_args__ = (
        Index("idx_plan_power_parse_issue_version", "version_id"),
        Index("idx_plan_power_parse_issue_sheet", "sheet_id"),
        Index("idx_plan_power_parse_issue_code", "issue_code"),
        Index("idx_plan_power_parse_issue_level", "level"),
    )

    id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, primary_key=True, autoincrement=True, comment="技术主键")
    version_id: Mapped[int] = mapped_column(PLAN_BOM_ID_TYPE, ForeignKey("plan_power_model_version.id", ondelete="CASCADE"), nullable=False, comment="模型版本 ID")
    sheet_id: Mapped[int | None] = mapped_column(PLAN_BOM_ID_TYPE, ForeignKey("plan_power_model_sheet.id", ondelete="CASCADE"), nullable=True, comment="模型 Sheet ID，可为空")
    level: Mapped[str] = mapped_column(String(32), nullable=False, comment="问题级别：warning / error")
    issue_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="问题编码")
    message: Mapped[str] = mapped_column(Text, nullable=False, comment="问题说明")
    source_sheet_name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="来源 Sheet 名")
    source_cell_ref: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="来源单元格")
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="原始上下文 JSON")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")


__all__ = [
    "PlanBomImportBatch",
    "PlanBomHeader",
    "PlanBomMaterialLine",
    "PlanBomRevision",
    "PlanBomExportTask",
    "PlanBomExportFile",
    "PlanPowerModelVersion",
    "PlanPowerModelSheet",
    "PlanPowerFactorOption",
    "PlanPowerSupplierEfficiencyDistribution",
    "PlanPowerPowerBin",
    "PlanPowerBenchmarkFactor",
    "PlanPowerModelValidationCase",
    "PlanPowerParseIssue",
]
