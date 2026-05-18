"""产销存入库仓储。"""

from __future__ import annotations

import json
from collections.abc import Iterable

from sqlalchemy.orm import Session

from backend.app.domains.business_analysis.models import (
    BaIspExcelSheet,
    BaIspExcelWorkbook,
    BaIspMetric,
    BaIspMetricAlias,
    BaIspMonthlyFact,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.excel_parser import (
    ParsedIspMonthlyFact,
    ParsedIspWorkbook,
)

METRIC_CATALOG: tuple[dict, ...] = (
    {
        "metric_code": "production_actual_including_oem",
        "metric_name": "实际产量（含委外）",
        "metric_category": "production",
        "aggregation_type": "flow_sum",
        "unit_standard": "MW",
        "description": "包含委外/代工的实际产出量，期间聚合按已发布月份求和。",
    },
    {
        "metric_code": "production_actual_excluding_oem",
        "metric_name": "实际产量（不含委外）",
        "metric_category": "production",
        "aggregation_type": "flow_sum",
        "unit_standard": "MW",
        "description": "不含委外的实际产量，期间聚合按已发布月份求和。",
    },
    {
        "metric_code": "production_by_base",
        "metric_name": "基地产量",
        "metric_category": "production",
        "aggregation_type": "flow_sum",
        "unit_standard": "MW",
        "description": "合肥、阜宁、广德等基地口径产量。",
    },
    {
        "metric_code": "production_outsourced",
        "metric_name": "委外加工产量",
        "metric_category": "production",
        "aggregation_type": "flow_sum",
        "unit_standard": "MW",
        "description": "委外加工或委外主体产量。",
    },
    {
        "metric_code": "production_self",
        "metric_name": "自产产量",
        "metric_category": "production",
        "aggregation_type": "flow_sum",
        "unit_standard": "MW",
        "description": "自产及自产基地拆分产量。",
    },
    {
        "metric_code": "production_oem",
        "metric_name": "代工/受托加工产量",
        "metric_category": "production",
        "aggregation_type": "flow_sum",
        "unit_standard": "MW",
        "description": "代工、OEM、受托加工、双经销、TW 等生产模式产量。",
    },
    {
        "metric_code": "production_by_model_type",
        "metric_name": "版型产量",
        "metric_category": "production",
        "aggregation_type": "flow_sum",
        "unit_standard": "MW",
        "description": "P型、N型、182N、183N、210N、210R 等版型产量。",
    },
    {
        "metric_code": "production_budget",
        "metric_name": "产量预算/目标",
        "metric_category": "budget",
        "aggregation_type": "flow_sum",
        "unit_standard": "MW",
        "description": "年度预算、月度产量目标、综合计划书产出目标。",
    },
    {
        "metric_code": "shipment_volume",
        "metric_name": "发货量/销量",
        "metric_category": "shipment",
        "aggregation_type": "flow_sum",
        "unit_standard": "MW",
        "description": "用户确认销量/销售量默认等同发货量。",
        "is_default_for_sales": 1,
    },
    {
        "metric_code": "shipment_by_base",
        "metric_name": "基地发货量/销量",
        "metric_category": "shipment",
        "aggregation_type": "flow_sum",
        "unit_standard": "MW",
        "description": "按合肥、阜宁、广德等基地拆分的发货量。",
    },
    {
        "metric_code": "shipment_external_excluding_internal",
        "metric_name": "对外销量（剔除内部交易）",
        "metric_category": "shipment",
        "aggregation_type": "flow_sum",
        "unit_standard": "MW",
        "description": "2024 组件事业部剔除内部交易，用户确认作为默认对外销量口径。",
        "is_default_for_sales": 1,
    },
    {
        "metric_code": "invoice_sales_volume",
        "metric_name": "开票销量",
        "metric_category": "shipment",
        "aggregation_type": "flow_sum",
        "unit_standard": "MW",
        "description": "仅用户明确问开票时使用，不作为默认销量。",
    },
    {
        "metric_code": "ending_inventory_volume",
        "metric_name": "期末库存/存货",
        "metric_category": "inventory",
        "aggregation_type": "period_end",
        "unit_standard": "MW",
        "description": "库存、存货、库存（SAP数据）完全等价，期间聚合取期末值。",
    },
    {
        "metric_code": "ending_inventory_by_base",
        "metric_name": "基地期末库存/存货",
        "metric_category": "inventory",
        "aggregation_type": "period_end",
        "unit_standard": "MW",
        "description": "按基地拆分的库存/存货期末值。",
    },
    {
        "metric_code": "consigned_inventory_volume",
        "metric_name": "寄存库存",
        "metric_category": "consignment",
        "aggregation_type": "period_end",
        "unit_standard": "MW",
        "description": "寄存仓与寄存合计完全等价，期间聚合取期末值。",
    },
    {
        "metric_code": "consigned_inventory_by_base",
        "metric_name": "基地寄存库存",
        "metric_category": "consignment",
        "aggregation_type": "period_end",
        "unit_standard": "MW",
        "description": "按基地拆分的寄存库存期末值。",
    },
    {
        "metric_code": "operating_volume_unclassified",
        "metric_name": "未分类经营数量",
        "metric_category": "operating",
        "aggregation_type": "flow_sum",
        "unit_standard": "MW",
        "description": "M2 兜底保留的历史特殊经营数量，后续应逐步归入标准指标。",
    },
)

METRIC_ALIASES: tuple[dict, ...] = (
    {"alias_text": "销量", "metric_code": "shipment_volume", "alias_type": "user_phrase", "priority": 10, "notes": "用户确认默认销量=发货量。"},
    {"alias_text": "销售量", "metric_code": "shipment_volume", "alias_type": "user_phrase", "priority": 10, "notes": "用户确认默认销售量=发货量。"},
    {"alias_text": "发货量", "metric_code": "shipment_volume", "alias_type": "user_phrase", "priority": 10},
    {"alias_text": "实际发出量", "metric_code": "shipment_volume", "alias_type": "raw_excel_item", "priority": 20},
    {"alias_text": "组件事业部剔除内部交易", "metric_code": "shipment_external_excluding_internal", "alias_type": "user_phrase", "priority": 5, "notes": "2024 默认对外销量口径。"},
    {"alias_text": "开票", "metric_code": "invoice_sales_volume", "alias_type": "user_phrase", "priority": 5, "requires_explicit_phrase": 1, "notes": "必须显式问开票。"},
    {"alias_text": "库存", "metric_code": "ending_inventory_volume", "alias_type": "synonym", "priority": 10, "notes": "库存、存货、库存（SAP数据）完全等价。"},
    {"alias_text": "存货", "metric_code": "ending_inventory_volume", "alias_type": "synonym", "priority": 10, "notes": "库存、存货、库存（SAP数据）完全等价。"},
    {"alias_text": "库存（SAP数据）", "metric_code": "ending_inventory_volume", "alias_type": "raw_excel_item", "priority": 10, "notes": "库存、存货、库存（SAP数据）完全等价。"},
    {"alias_text": "寄存仓", "metric_code": "consigned_inventory_volume", "alias_type": "synonym", "priority": 10, "notes": "寄存仓与寄存合计完全等价。"},
    {"alias_text": "寄存合计", "metric_code": "consigned_inventory_volume", "alias_type": "synonym", "priority": 10, "notes": "寄存仓与寄存合计完全等价。"},
)


class InventorySalesProductionRepository:
    """产销存 Excel 入库仓储。

    职责：
        1. 保存 ODS 工作簿、sheet 结构和 DWD 月度事实；
        2. 初始化指标/别名维表，为后续 QueryPlan/NL2SQL 做白名单；
        3. 使用文件 SHA256 做幂等控制，同一文件重复导入不重复写事实。
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def save_parsed_workbook(self, parsed: ParsedIspWorkbook) -> tuple[BaIspExcelWorkbook, bool]:
        """保存解析后的工作簿。

        参数：
            parsed: 解析器输出的工作簿结果。

        返回：
            二元组 `(workbook, created)`；created=False 表示同 hash 文件已存在。
        """
        try:
            self._seed_metric_catalog()
            existing = self.get_workbook_by_hash(parsed.file_hash)
            if existing:
                self.db.commit()
                return existing, False

            workbook = BaIspExcelWorkbook(
                source_file_name=parsed.file_name,
                source_file_sha256=parsed.file_hash,
                source_file_size=parsed.file_size,
                business_year=parsed.business_year,
                data_cutoff_month=parsed.data_cutoff_month,
                source_version_label=parsed.source_version_label,
                upload_batch_no=parsed.upload_batch_no,
                sheet_count=parsed.sheet_count,
                has_vba=1 if parsed.has_vba else 0,
                external_link_count=parsed.external_link_count,
                parser_version=parsed.parser_version,
                quality_status=parsed.quality_status,
                quality_message=parsed.quality_message,
                quality_flags=json.dumps(parsed.quality_flags, ensure_ascii=False),
            )
            self.db.add(workbook)
            self.db.flush()

            sheet_id_by_name = self._save_sheets(workbook.id, parsed.sheets)
            self._save_monthly_facts(workbook.id, sheet_id_by_name, parsed.monthly_facts)
            self.db.commit()
            self.db.refresh(workbook)
            return workbook, True
        except Exception:
            self.db.rollback()
            raise

    def get_workbook_by_hash(self, file_hash: str) -> BaIspExcelWorkbook | None:
        """按文件 hash 查询已导入工作簿。"""
        return self.db.query(BaIspExcelWorkbook).filter(BaIspExcelWorkbook.source_file_sha256 == file_hash).one_or_none()

    def _save_sheets(self, workbook_id: int, sheets: Iterable) -> dict[str, int]:
        """保存 sheet 结构并返回 sheet 名到 ID 的映射。"""
        sheet_id_by_name: dict[str, int] = {}
        for sheet in sheets:
            sheet_row = BaIspExcelSheet(
                workbook_id=workbook_id,
                sheet_name=sheet.sheet_name,
                sheet_role=sheet.sheet_role,
                dimension_ref=sheet.dimension_ref,
                max_row=sheet.max_row,
                max_col=sheet.max_col,
                formula_count=sheet.formula_count,
                merged_cell_count=sheet.merged_cell_count,
                hidden_rows=json.dumps(sheet.hidden_rows, ensure_ascii=False),
                hidden_cols=json.dumps(sheet.hidden_cols, ensure_ascii=False),
                header_rows=json.dumps(sheet.header_rows, ensure_ascii=False),
            )
            self.db.add(sheet_row)
            self.db.flush()
            sheet_id_by_name[sheet.sheet_name] = sheet_row.id
        return sheet_id_by_name

    def _save_monthly_facts(self, workbook_id: int, sheet_id_by_name: dict[str, int], facts: Iterable[ParsedIspMonthlyFact]) -> None:
        """批量保存月度事实。"""
        rows = [self._fact_to_model(workbook_id, sheet_id_by_name, fact) for fact in facts]
        if rows:
            self.db.add_all(rows)

    def _fact_to_model(
        self,
        workbook_id: int,
        sheet_id_by_name: dict[str, int],
        fact: ParsedIspMonthlyFact,
    ) -> BaIspMonthlyFact:
        """将内存事实转换为 ORM 对象。"""
        return BaIspMonthlyFact(
            workbook_id=workbook_id,
            sheet_id=sheet_id_by_name.get(fact.source_sheet),
            business_year=fact.business_year,
            business_month=fact.business_month,
            period_label=fact.period_label,
            period_start_date=fact.period_start_date,
            period_end_date=fact.period_end_date,
            data_cutoff_month=fact.data_cutoff_month,
            is_published_month=1 if fact.is_published_month else 0,
            domain="business_analysis",
            sub_domain="inventory_sales_production",
            metric_code=fact.metric_code,
            metric_name=fact.metric_name,
            metric_category=fact.metric_category,
            aggregation_type=fact.aggregation_type,
            value_decimal=fact.value_decimal,
            unit_standard=fact.unit_standard,
            base_name=fact.base_name,
            factory_name=fact.factory_name,
            model_type=fact.model_type,
            production_mode=fact.production_mode,
            trade_scope=fact.trade_scope,
            is_outsourced=1 if fact.is_outsourced else 0,
            is_consigned=1 if fact.is_consigned else 0,
            is_default_external_sales=1 if fact.is_default_external_sales else 0,
            source_file_name=fact.source_file_name,
            source_file_sha256=fact.source_file_sha256,
            source_sheet=fact.source_sheet,
            source_row_index=fact.source_row_index,
            source_col_index=fact.source_col_index,
            source_cell_ref=fact.source_cell_ref,
            raw_category=fact.raw_category,
            raw_item=fact.raw_item,
            raw_unit=fact.raw_unit,
            parser_version=fact.parser_version,
            quality_flags=json.dumps(fact.quality_flags, ensure_ascii=False),
        )

    def _seed_metric_catalog(self) -> None:
        """初始化指标和别名维表。"""
        for metric in METRIC_CATALOG:
            self.db.merge(BaIspMetric(**metric))
        self.db.flush()
        for alias in METRIC_ALIASES:
            existing = (
                self.db.query(BaIspMetricAlias)
                .filter(
                    BaIspMetricAlias.alias_text == alias["alias_text"],
                    BaIspMetricAlias.metric_code == alias["metric_code"],
                    BaIspMetricAlias.alias_type == alias.get("alias_type", "synonym"),
                )
                .one_or_none()
            )
            if existing:
                continue
            self.db.add(
                BaIspMetricAlias(
                    alias_text=alias["alias_text"],
                    metric_code=alias["metric_code"],
                    alias_type=alias.get("alias_type", "synonym"),
                    priority=alias.get("priority", 100),
                    requires_explicit_phrase=alias.get("requires_explicit_phrase", 0),
                    notes=alias.get("notes"),
                )
            )


__all__ = [
    "InventorySalesProductionRepository",
    "METRIC_CATALOG",
    "METRIC_ALIASES",
]
