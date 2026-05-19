from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base

# 说明：生产库建议使用 BigInteger；SQLite 测试库需要 INTEGER PRIMARY KEY 才能自动递增。
BA_ISP_ID_TYPE = BigInteger().with_variant(Integer, "sqlite")


class BaIspExcelWorkbook(Base):
    """产销存 Excel 工作簿 ODS 表。

    业务含义：
        记录一次产销存 Excel 文件版本，保留文件哈希、业务年份、数据截止月份、
        解析质量信息和解析器版本，用于后续问答结果追溯。
    """

    __tablename__ = "ods_ba_isp_excel_workbook"
    __table_args__ = (
        UniqueConstraint("source_file_sha256", name="uk_ba_isp_workbook_sha256"),
        Index("idx_ba_isp_workbook_year", "business_year"),
        Index("idx_ba_isp_workbook_cutoff", "business_year", "data_cutoff_month"),
        {"comment": "经营分析产销存 Excel 工作簿版本表"},
    )

    id: Mapped[int] = mapped_column(BA_ISP_ID_TYPE, primary_key=True, autoincrement=True, comment="技术主键")
    source_file_name: Mapped[str] = mapped_column(String(512), nullable=False, comment="原始 Excel 文件名")
    source_file_sha256: Mapped[str] = mapped_column(String(128), nullable=False, comment="文件 SHA256，用于幂等导入")
    source_file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="文件字节数")
    business_year: Mapped[int] = mapped_column(Integer, nullable=False, comment="业务年份")
    data_cutoff_month: Mapped[int] = mapped_column(Integer, nullable=False, comment="数据截止月份，只导入该月之前的已发布月")
    source_version_label: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="来源版本标签，如 2026.04")
    upload_batch_no: Mapped[str] = mapped_column(String(64), nullable=False, comment="导入批次号")
    sheet_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="工作簿 sheet 数")
    has_vba: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否存在 VBA，xlsx 正常为 0")
    external_link_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="外部链接数量")
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False, comment="解析器版本")
    quality_status: Mapped[str] = mapped_column(String(32), nullable=False, default="success", comment="解析质量状态")
    quality_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="解析质量摘要")
    quality_flags: Mapped[str | None] = mapped_column(Text, nullable=True, comment="解析质量标记 JSON")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )


class BaIspExcelSheet(Base):
    """产销存 Excel Sheet ODS 表。

    业务含义：
        记录每个 sheet 的结构、范围、公式数量、隐藏列和表头信息；
        不作为问答事实来源，只用于审计和问题追溯。
    """

    __tablename__ = "ods_ba_isp_excel_sheet"
    __table_args__ = (
        UniqueConstraint("workbook_id", "sheet_name", name="uk_ba_isp_sheet_workbook_name"),
        Index("idx_ba_isp_sheet_workbook", "workbook_id"),
        {"comment": "经营分析产销存 Excel Sheet 结构表"},
    )

    id: Mapped[int] = mapped_column(BA_ISP_ID_TYPE, primary_key=True, autoincrement=True, comment="技术主键")
    workbook_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ods_ba_isp_excel_workbook.id", ondelete="CASCADE"), nullable=False, comment="工作簿 ID")
    sheet_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="原始 sheet 名")
    sheet_role: Mapped[str] = mapped_column(String(64), nullable=False, default="summary", comment="sheet 角色：summary/detail/unknown")
    dimension_ref: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="Excel 范围，如 A1:S43")
    max_row: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="最大行号")
    max_col: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="最大列号")
    formula_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="公式单元格数量")
    merged_cell_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="合并单元格数量")
    hidden_rows: Mapped[str | None] = mapped_column(Text, nullable=True, comment="隐藏行 JSON")
    hidden_cols: Mapped[str | None] = mapped_column(Text, nullable=True, comment="隐藏列 JSON")
    header_rows: Mapped[str | None] = mapped_column(Text, nullable=True, comment="表头行 JSON")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")


class BaIspMonthlyFact(Base):
    """产销存 DWD 标准月度事实长表。

    粒度：
        一个来源工作簿 + 一个 sheet + 一个原始行项目 + 一个标准指标 + 一个已发布月份。

    业务边界：
        1. 只保存已发布月份；
        2. 年度、季度、预算达成率等期间结果后续由 DWS/查询服务按策略重算；
        3. 该表是后续 QueryPlan/NL2SQL 的主事实表，不让 LLM 直接读 Excel。
    """

    __tablename__ = "dwd_ba_isp_monthly_fact"
    __table_args__ = (
        UniqueConstraint(
            "workbook_id",
            "source_sheet",
            "source_row_index",
            "source_col_index",
            "metric_code",
            name="uk_ba_isp_monthly_fact_source_cell_metric",
        ),
        Index("idx_ba_isp_fact_year_month", "business_year", "business_month"),
        Index("idx_ba_isp_fact_metric", "metric_code"),
        Index("idx_ba_isp_fact_metric_year", "metric_code", "business_year"),
        Index("idx_ba_isp_fact_base", "base_name"),
        Index("idx_ba_isp_fact_model", "model_type"),
        {"comment": "经营分析产销存标准月度事实长表"},
    )

    id: Mapped[int] = mapped_column(BA_ISP_ID_TYPE, primary_key=True, autoincrement=True, comment="技术主键")
    workbook_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ods_ba_isp_excel_workbook.id", ondelete="CASCADE"), nullable=False, comment="来源工作簿 ID")
    sheet_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("ods_ba_isp_excel_sheet.id", ondelete="CASCADE"), nullable=True, comment="来源 sheet ID")
    business_year: Mapped[int] = mapped_column(Integer, nullable=False, comment="业务年份")
    business_month: Mapped[int] = mapped_column(Integer, nullable=False, comment="业务月份")
    period_label: Mapped[str] = mapped_column(String(16), nullable=False, comment="期间标签，如 2025-12")
    period_start_date: Mapped[date] = mapped_column(Date, nullable=False, comment="期间开始日期")
    period_end_date: Mapped[date] = mapped_column(Date, nullable=False, comment="期间结束日期")
    data_cutoff_month: Mapped[int] = mapped_column(Integer, nullable=False, comment="来源文件截止月份")
    is_published_month: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, comment="是否已发布月份，M2 事实均为 1")
    domain: Mapped[str] = mapped_column(String(64), nullable=False, default="business_analysis", comment="业务域")
    sub_domain: Mapped[str] = mapped_column(String(128), nullable=False, default="inventory_sales_production", comment="子业务域")
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="标准指标编码")
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="标准指标中文名")
    metric_category: Mapped[str] = mapped_column(String(64), nullable=False, comment="指标分类")
    aggregation_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="聚合类型：flow_sum/period_end/calculated_ratio")
    value_decimal: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False, comment="标准数值")
    unit_standard: Mapped[str] = mapped_column(String(32), nullable=False, default="MW", comment="标准单位")
    base_name: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="基地名称")
    factory_name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="工厂名称")
    model_type: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="版型")
    production_mode: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="生产模式")
    trade_scope: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="交易范围")
    is_outsourced: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否委外/代工")
    is_consigned: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否寄存")
    is_default_external_sales: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否默认对外销量口径")
    source_file_name: Mapped[str] = mapped_column(String(512), nullable=False, comment="来源文件名")
    source_file_sha256: Mapped[str] = mapped_column(String(128), nullable=False, comment="来源文件 SHA256")
    source_sheet: Mapped[str] = mapped_column(String(128), nullable=False, comment="来源 sheet")
    source_row_index: Mapped[int] = mapped_column(Integer, nullable=False, comment="来源行号")
    source_col_index: Mapped[int] = mapped_column(Integer, nullable=False, comment="来源列号")
    source_cell_ref: Mapped[str] = mapped_column(String(32), nullable=False, comment="来源单元格坐标")
    raw_category: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="原始分类")
    raw_item: Mapped[str] = mapped_column(String(256), nullable=False, comment="原始项目")
    raw_unit: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="原始单位")
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False, comment="解析器版本")
    quality_flags: Mapped[str | None] = mapped_column(Text, nullable=True, comment="质量标记 JSON")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )


class BaIspMetric(Base):
    """产销存标准指标维表。

    用途：
        为后续受控 QueryPlan / NL2SQL 提供指标白名单、聚合策略和业务说明。
    """

    __tablename__ = "dim_ba_isp_metric"
    __table_args__ = ({"comment": "经营分析产销存标准指标维表"},)

    metric_code: Mapped[str] = mapped_column(String(128), primary_key=True, comment="标准指标编码")
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="标准指标中文名")
    metric_category: Mapped[str] = mapped_column(String(64), nullable=False, comment="指标分类")
    aggregation_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="聚合类型")
    unit_standard: Mapped[str] = mapped_column(String(32), nullable=False, default="MW", comment="标准单位")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="业务说明")
    calculation_formula: Mapped[str | None] = mapped_column(Text, nullable=True, comment="后端计算公式说明")
    requires_budget: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否需要预算数据")
    is_default_for_sales: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否作为销量默认指标")
    is_active: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, comment="是否启用")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")


class BaIspMetricAlias(Base):
    """产销存指标别名维表。

    用途：
        保存用户问法、Excel 原始字段和业务同义词到标准指标的映射，
        后续用于 QueryPlan/NL2SQL 召回，不在 M2 直接做问答解析。
    """

    __tablename__ = "dim_ba_isp_metric_alias"
    __table_args__ = (
        UniqueConstraint("alias_text", "metric_code", "alias_type", name="uk_ba_isp_metric_alias_text_metric_type"),
        Index("idx_ba_isp_metric_alias_metric", "metric_code"),
        {"comment": "经营分析产销存指标别名表"},
    )

    id: Mapped[int] = mapped_column(BA_ISP_ID_TYPE, primary_key=True, autoincrement=True, comment="技术主键")
    alias_text: Mapped[str] = mapped_column(String(128), nullable=False, comment="别名文本")
    metric_code: Mapped[str] = mapped_column(String(128), ForeignKey("dim_ba_isp_metric.metric_code", ondelete="CASCADE"), nullable=False, comment="标准指标编码")
    alias_type: Mapped[str] = mapped_column(String(64), nullable=False, default="synonym", comment="别名类型")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, comment="匹配优先级，数值越小越优先")
    requires_explicit_phrase: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否必须显式触发")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True, comment="说明")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")


__all__ = [
    "BaIspExcelWorkbook",
    "BaIspExcelSheet",
    "BaIspMonthlyFact",
    "BaIspMetric",
    "BaIspMetricAlias",
]
