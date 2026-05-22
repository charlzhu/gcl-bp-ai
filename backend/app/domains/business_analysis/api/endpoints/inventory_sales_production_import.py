"""产销存 Excel 导入 API。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.domains.business_analysis.repositories.inventory_sales_production_repository import (
    InventorySalesProductionRepository,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.excel_import_service import (
    InventorySalesProductionExcelImportService,
    InventorySalesProductionImportReport,
)
from backend.app.schemas.common import ApiResponse

router = APIRouter()

ALLOWED_EXCEL_SUFFIXES = {".xls", ".xlsx", ".xlsm"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50MB


@router.post("/import", response_model=ApiResponse)
def import_inventory_sales_production_excel(
    request: Request,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
) -> ApiResponse:
    """上传并导入产销存 Excel 文件。

    说明：
        1. 接受 .xls/.xlsx/.xlsm 文件；
        2. 用解析器转为标准月度事实后入库；
        3. 同一文件（SHA256 相同）重复导入返回 existing 状态；
        4. 导入后自动初始化指标/别名维表。
    """
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))

    if not file.filename:
        return ApiResponse.fail(message="文件名不能为空。", trace_id=trace_id)

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXCEL_SUFFIXES:
        return ApiResponse.fail(
            message=f"不支持的文件类型 {suffix}，仅支持 {ALLOWED_EXCEL_SUFFIXES}。",
            trace_id=trace_id,
        )

    content = file.file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        return ApiResponse.fail(
            message=f"文件超过 {MAX_UPLOAD_BYTES // 1024 // 1024}MB 限制。",
            trace_id=trace_id,
        )

    try:
        # 保存到临时文件后让解析器处理
        from backend.app.domains.business_analysis.services.inventory_sales_production.excel_parser import (
            InventorySalesProductionExcelParser,
        )

        parser = InventorySalesProductionExcelParser()
        parsed = parser.parse_bytes(content, file_name=file.filename)

        repository = InventorySalesProductionRepository(db)
        service = InventorySalesProductionExcelImportService(
            repository=repository,
            parser=parser,
        )
        # 手动调用仓储保存（因为 parser.parse_bytes 不用走 file_path）
        workbook, created = repository.save_parsed_workbook(parsed)
        report = InventorySalesProductionImportReport(
            workbook_id=workbook.id,
            import_status="created" if created else "existing",
            business_year=workbook.business_year,
            data_cutoff_month=workbook.data_cutoff_month,
            sheet_count=workbook.sheet_count,
            monthly_fact_count=parsed.monthly_fact_count,
            source_file_name=workbook.source_file_name,
        )
        return ApiResponse.success(
            data=report.__dict__,
            trace_id=trace_id,
        )
    except Exception as exc:
        return ApiResponse.fail(
            message=f"导入失败：{exc}",
            trace_id=trace_id,
        )


@router.get("/import/history", response_model=ApiResponse)
def list_import_history(
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """查询产销存 Excel 导入历史。"""
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    from backend.app.domains.business_analysis.models import BaIspExcelWorkbook

    rows = (
        db.query(BaIspExcelWorkbook)
        .order_by(BaIspExcelWorkbook.created_at.desc())
        .limit(50)
        .all()
    )
    history = []
    for row in rows:
        history.append({
            "id": row.id,
            "source_file_name": row.source_file_name,
            "business_year": row.business_year,
            "data_cutoff_month": row.data_cutoff_month,
            "sheet_count": row.sheet_count,
            "upload_batch_no": row.upload_batch_no,
            "created_at": str(row.created_at) if row.created_at else "",
            "import_status": "existing" if row.source_file_sha256 else "created",
        })
    return ApiResponse.success(data={"history": history}, trace_id=trace_id)
