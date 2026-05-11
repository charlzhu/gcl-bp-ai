from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile

from backend.app.api.deps import get_plan_bom_import_service
from backend.app.domains.plan_bom.schemas.import_excel import PlanBomImportReport, PlanBomUploadHistoryResponse
from backend.app.domains.plan_bom.services.excel_import_service import PlanBomExcelImportService
from backend.app.schemas.common import ApiResponse

router = APIRouter()

ALLOWED_BOM_EXCEL_SUFFIXES = {".xls", ".xlsx", ".xlsm"}
MAX_SINGLE_BOM_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_BATCH_BOM_UPLOAD_FILES = 50


def _upload_failure_payload(
    *,
    message: str,
    file_name: str | None = None,
    file_size: int = 0,
    next_action: str,
    error: str | None = None,
) -> dict[str, Any]:
    """构造计划 BOM 上传失败响应。

    参数：
        message: 面向用户的失败原因；
        file_name: 上传文件名；
        file_size: 上传文件大小；
        next_action: 下一步处理建议；
        error: 可选技术错误摘要。

    返回：
        与成功响应字段兼容的失败 payload，避免前端和脚本需要猜测字段。
    """

    return {
        "success": False,
        "message": message,
        "import_batch_id": None,
        "file_name": file_name,
        "file_size": file_size,
        "parsed_orders_count": 0,
        "parsed_materials_count": 0,
        "warning_count": 0,
        "error_count": 1 if error else 0,
        "data_quality_summary": {"error": error} if error else {},
        "report_path": None,
        "next_action": next_action,
    }


def _build_quality_summary(
    *,
    report: PlanBomImportReport,
    source: str,
    overwrite: bool,
    remark: str | None,
) -> dict[str, Any]:
    """构造单个 BOM 文件解析质量摘要。

    参数：
        report: 后端 Excel 导入服务返回的解析报告；
        source: 上传来源；
        overwrite: 是否允许覆盖同文件实例；
        remark: 上传备注。

    返回：
        前端可展示、审计可追溯的质量摘要。
    """

    return {
        "sheet_count": report.sheet_count,
        "revision_count": report.revision_count,
        "persisted_business_data": report.persisted_business_data,
        "rollback_applied": report.rollback_applied,
        "source": source,
        "overwrite": overwrite,
        "remark": remark,
    }


def _upload_success_payload(
    *,
    report: PlanBomImportReport,
    file_size: int,
    source: str,
    overwrite: bool,
    remark: str | None,
) -> dict[str, Any]:
    """构造单个计划 BOM Excel 上传成功/解析完成响应。

    参数：
        report: 导入服务返回的解析报告；
        file_size: 上传文件字节数；
        source: 上传来源；
        overwrite: 是否覆盖同一文件实例；
        remark: 上传备注。

    返回：
        与历史单文件接口兼容的 payload。
    """

    return {
        "success": report.status == "success",
        "message": "BOM Excel 上传解析成功。" if report.status == "success" else "BOM Excel 上传解析失败，请查看错误明细。",
        "import_batch_id": report.batch_id,
        "file_name": report.file_name,
        "file_size": file_size,
        "parsed_orders_count": report.header_count,
        "parsed_materials_count": report.material_line_count,
        "warning_count": report.warning_count,
        "error_count": report.error_count,
        "data_quality_summary": _build_quality_summary(report=report, source=source, overwrite=overwrite, remark=remark),
        "report_path": f"tmp/plan_bom/import_reports/{report.batch_id}.json",
        "next_action": "可以进入 /api/v1/plan-bom/qa/ask 查询。" if report.status == "success" else "请修正 Excel 后重新上传。",
        "errors": [item.model_dump(mode="json") for item in report.errors[:20]],
        "warnings": [item.model_dump(mode="json") for item in report.warnings[:20]],
    }


async def _import_one_upload_file(
    *,
    upload_file: UploadFile,
    service: PlanBomExcelImportService,
    source: str,
    overwrite: bool,
    remark: str | None,
) -> dict[str, Any]:
    """读取并导入单个上传文件，返回逐文件结果。

    参数：
        upload_file: FastAPI 上传文件对象；
        service: 计划 BOM Excel 导入服务；
        source: 上传来源；
        overwrite: 是否覆盖同一文件实例；
        remark: 上传备注。

    返回：
        单文件成功或失败 payload。批量上传会逐个调用本函数，确保单个坏文件不阻断其它文件。
    """

    content = await upload_file.read()
    file_name = upload_file.filename or "plan_bom.xlsx"
    suffix = Path(file_name).suffix.lower()
    if suffix not in ALLOWED_BOM_EXCEL_SUFFIXES:
        return _upload_failure_payload(
            message="仅支持 .xls / .xlsx / .xlsm 格式的 BOM Excel 文件。",
            file_name=file_name,
            file_size=len(content),
            next_action="请上传有效的 BOM Excel 文件。",
        )
    if not content:
        return _upload_failure_payload(message="上传文件为空。", file_name=file_name, file_size=0, next_action="请重新选择非空 Excel 文件。")
    if len(content) > MAX_SINGLE_BOM_UPLOAD_BYTES:
        return _upload_failure_payload(
            message="上传文件超过 20MB 限制。",
            file_name=file_name,
            file_size=len(content),
            next_action="请拆分文件或联系管理员调整上传限制。",
        )

    try:
        report = service.import_bytes(content, file_name=file_name)
    except Exception as exc:  # noqa: BLE001
        return _upload_failure_payload(
            message="BOM Excel 上传解析失败，请确认文件是有效 Excel 且符合计划 BOM 模板。",
            file_name=file_name,
            file_size=len(content),
            next_action="请修正 Excel 后重新上传。",
            error=str(exc)[:300],
        )
    return _upload_success_payload(report=report, file_size=len(content), source=source, overwrite=overwrite, remark=remark)


def _batch_upload_payload(
    *,
    items: list[dict[str, Any]],
    source: str,
    overwrite: bool,
    remark: str | None,
) -> dict[str, Any]:
    """汇总多个 BOM 文件的上传结果。

    参数：
        items: 逐文件上传结果；
        source: 上传来源；
        overwrite: 是否覆盖同一文件实例；
        remark: 上传备注。

    返回：
        批量上传汇总 payload，既包含总体成功/失败，也保留逐文件明细。
    """

    total_files = len(items)
    success_count = sum(1 for item in items if item.get("success") is True)
    failed_count = total_files - success_count
    parsed_orders_count = sum(int(item.get("parsed_orders_count") or 0) for item in items)
    parsed_materials_count = sum(int(item.get("parsed_materials_count") or 0) for item in items)
    warning_count = sum(int(item.get("warning_count") or 0) for item in items)
    error_count = sum(int(item.get("error_count") or 0) for item in items)
    if total_files == 0:
        message = "未选择任何 BOM Excel 文件。"
    elif failed_count == 0:
        message = f"BOM Excel 批量上传成功：{success_count} 个文件已完成解析。"
    else:
        message = f"BOM Excel 批量上传完成：成功 {success_count} 个，失败 {failed_count} 个。"
    return {
        "success": total_files > 0 and failed_count == 0,
        "message": message,
        "total_files": total_files,
        "success_count": success_count,
        "failed_count": failed_count,
        "parsed_orders_count": parsed_orders_count,
        "parsed_materials_count": parsed_materials_count,
        "warning_count": warning_count,
        "error_count": error_count,
        "data_quality_summary": {
            "batch_mode": True,
            "source": source,
            "overwrite": overwrite,
            "remark": remark,
        },
        "items": items,
        "next_action": "可以进入 /api/v1/plan-bom/qa/ask 查询。" if failed_count == 0 and total_files > 0 else "请查看逐文件结果，修正失败文件后重新上传。",
    }


def _business_type_failure_response(
    *,
    upload_files: list[UploadFile],
    is_batch_request: bool,
    trace_id: str,
) -> ApiResponse:
    """构造 business_type 非 plan_bom 时的失败响应。

    参数：
        upload_files: 本次请求携带的文件列表；
        is_batch_request: 是否使用批量 files 字段；
        trace_id: 请求追踪号。

    返回：
        单文件保持旧结构，批量 files 字段返回批量结构。
    """

    if is_batch_request:
        items = [
            _upload_failure_payload(
                message="当前上传接口仅支持 business_type=plan_bom。",
                file_name=upload_file.filename,
                file_size=0,
                next_action="请将 business_type 改为 plan_bom 后重新上传。",
            )
            for upload_file in upload_files
        ] or [
            _upload_failure_payload(
                message="当前上传接口仅支持 business_type=plan_bom。",
                file_name=None,
                file_size=0,
                next_action="请将 business_type 改为 plan_bom 后重新上传。",
            )
        ]
        return ApiResponse.success(_batch_upload_payload(items=items, source="invalid_business_type", overwrite=True, remark=None), trace_id=trace_id)
    file_name = upload_files[0].filename if upload_files else None
    return ApiResponse.success(
        _upload_failure_payload(
            message="当前上传接口仅支持 business_type=plan_bom。",
            file_name=file_name,
            file_size=0,
            next_action="请将 business_type 改为 plan_bom 后重新上传。",
        ),
        trace_id=trace_id,
    )


@router.post("/excel", response_model=ApiResponse)
async def import_plan_bom_excel(
    request: Request,
    file: UploadFile = File(...),
    service: PlanBomExcelImportService = Depends(get_plan_bom_import_service),
) -> ApiResponse:
    """计划 BOM Excel 入库入口。

    说明：
    1. 当前接口只做 Excel 读取、解析、批次入库和报告返回；
    2. 不提供查询、导出或 SAP 接入能力；
    3. trace_id 复用现有请求上下文，便于后续日志串联。
    """
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    report = await service.import_upload(file)
    return ApiResponse.success(report.model_dump(), trace_id=trace_id)


@router.get("/upload/history", response_model=ApiResponse)
def list_plan_bom_upload_history(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200, description="最多返回历史批次数量"),
    service: PlanBomExcelImportService = Depends(get_plan_bom_import_service),
) -> ApiResponse:
    """查询计划 BOM Excel 上传历史。

    参数：
        limit: 最多返回的历史批次数量。

    返回：
        历史上传文件批次、解析状态和统计摘要，用于 BOM 数据管理页查看以往上传记录。
    """
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    items = service.list_upload_history(limit=limit)
    payload = PlanBomUploadHistoryResponse(items=items, total=len(items))
    return ApiResponse.success(payload.model_dump(mode="json"), trace_id=trace_id)


@router.post("/upload", response_model=ApiResponse)
async def upload_plan_bom_excel(
    request: Request,
    file: UploadFile | None = File(default=None),
    files: list[UploadFile] | None = File(default=None),
    business_type: str = Form(default="plan_bom"),
    source: str = Form(default="manual_upload"),
    overwrite: bool = Form(default=True),
    remark: str | None = Form(default=None),
    service: PlanBomExcelImportService = Depends(get_plan_bom_import_service),
) -> ApiResponse:
    """计划 BOM Excel 上传与导入入口，兼容单文件和批量上传。

    参数：
        file: 兼容旧前端的单文件字段，支持 `.xls` / `.xlsx` / `.xlsm`；
        files: 批量上传字段，可一次传入多个 BOM Excel；
        business_type: 业务类型，当前默认并限制为 plan_bom；
        source: 上传来源标记，例如 manual_upload / trial_import；
        overwrite: 是否覆盖同一文件实例，当前复用既有导入仓储的幂等覆盖策略；
        remark: 上传备注，仅回传到报告摘要中，不参与事实解析。

    返回：
        单文件请求保持旧响应结构；files 批量请求返回汇总字段和逐文件 items。
    """

    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    is_batch_request = files is not None
    upload_files = [item for item in (files or []) if item is not None]
    if not upload_files and file is not None:
        upload_files = [file]

    if business_type != "plan_bom":
        return _business_type_failure_response(upload_files=upload_files, is_batch_request=is_batch_request, trace_id=trace_id)

    if not upload_files:
        return ApiResponse.success(
            _upload_failure_payload(message="请至少选择一个 BOM Excel 文件。", next_action="请选择 .xls / .xlsx / .xlsm 文件后重新上传。"),
            trace_id=trace_id,
        )

    if is_batch_request and len(upload_files) > MAX_BATCH_BOM_UPLOAD_FILES:
        items = [
            _upload_failure_payload(
                message=f"单次最多支持上传 {MAX_BATCH_BOM_UPLOAD_FILES} 个 BOM Excel 文件。",
                file_name=upload_file.filename,
                next_action="请拆分为多次批量上传。",
            )
            for upload_file in upload_files
        ]
        return ApiResponse.success(_batch_upload_payload(items=items, source=source, overwrite=overwrite, remark=remark), trace_id=trace_id)

    if not is_batch_request:
        item = await _import_one_upload_file(upload_file=upload_files[0], service=service, source=source, overwrite=overwrite, remark=remark)
        return ApiResponse.success(item, trace_id=trace_id)

    items: list[dict[str, Any]] = []
    for upload_file in upload_files:
        items.append(await _import_one_upload_file(upload_file=upload_file, service=service, source=source, overwrite=overwrite, remark=remark))
    return ApiResponse.success(_batch_upload_payload(items=items, source=source, overwrite=overwrite, remark=remark), trace_id=trace_id)
