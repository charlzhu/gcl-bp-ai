"""产销存 Excel 导入服务。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.app.domains.business_analysis.repositories.inventory_sales_production_repository import (
    InventorySalesProductionRepository,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.excel_parser import (
    InventorySalesProductionExcelParser,
)


@dataclass(slots=True, frozen=True)
class InventorySalesProductionImportReport:
    """产销存导入结果。

    参数：
        workbook_id: 工作簿表 ID；
        import_status: created/existing；
        business_year: 业务年份；
        data_cutoff_month: 数据截止月份；
        sheet_count: sheet 数；
        monthly_fact_count: 月度事实数量；
        source_file_name: 原始文件名。
    """

    workbook_id: int
    import_status: str
    business_year: int
    data_cutoff_month: int
    sheet_count: int
    monthly_fact_count: int
    source_file_name: str


class InventorySalesProductionExcelImportService:
    """产销存 Excel 入库应用服务。

    职责：
        1. 调用解析器将 Excel 转换为标准月度事实；
        2. 调用仓储保存 ODS 和 DWD 表；
        3. 返回导入报告，供后续 CLI/API/任务调度复用。
    """

    def __init__(
        self,
        *,
        repository: InventorySalesProductionRepository,
        parser: InventorySalesProductionExcelParser | None = None,
    ) -> None:
        self.repository = repository
        self.parser = parser or InventorySalesProductionExcelParser()

    def import_file(self, file_path: str | Path) -> InventorySalesProductionImportReport:
        """导入本地产销存 Excel 文件。

        参数：
            file_path: 本地 Excel 路径。

        返回：
            InventorySalesProductionImportReport，说明导入状态与事实数量。
        """
        parsed = self.parser.parse_file(file_path)
        workbook, created = self.repository.save_parsed_workbook(parsed)
        return InventorySalesProductionImportReport(
            workbook_id=workbook.id,
            import_status="created" if created else "existing",
            business_year=workbook.business_year,
            data_cutoff_month=workbook.data_cutoff_month,
            sheet_count=workbook.sheet_count,
            monthly_fact_count=parsed.monthly_fact_count,
            source_file_name=workbook.source_file_name,
        )


__all__ = [
    "InventorySalesProductionExcelImportService",
    "InventorySalesProductionImportReport",
]
