from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile

from backend.app.api.deps import get_plan_bom_import_service
from backend.app.domains.plan_bom.schemas.import_excel import PlanBomUploadHistoryResponse
from backend.app.domains.plan_bom.services.excel_import_service import PlanBomExcelImportService
from backend.app.schemas.common import ApiResponse

router = APIRouter()


def _upload_failure_payload(
    *,
    message: str,
    file_name: str | None = None,
    file_size: int = 0,
    next_action: str,
    error: str | None = None,
) -> dict:
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
    file: UploadFile = File(...),
    business_type: str = Form(default="plan_bom"),
    source: str = Form(default="manual_upload"),
    overwrite: bool = Form(default=True),
    remark: str | None = Form(default=None),
    service: PlanBomExcelImportService = Depends(get_plan_bom_import_service),
) -> ApiResponse:
    """计划 BOM Excel 上传与导入入口。

    参数：
        file: 必填，支持 `.xls` / `.xlsx` / `.xlsm`；
        business_type: 业务类型，当前默认并限制为 plan_bom；
        source: 上传来源标记，例如 manual_upload / trial_import；
        overwrite: 是否覆盖同一文件实例，当前复用既有导入仓储的幂等覆盖策略；
        remark: 上传备注，仅回传到报告摘要中，不参与事实解析。

    返回：
        面向前端验收的上传结果字段，包含批次号、文件大小、解析数量、质量摘要和下一步动作。
    """

    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    content = await file.read()
    suffix = Path(file.filename or "").suffix.lower()
    max_bytes = 20 * 1024 * 1024
    if business_type != "plan_bom":
        return ApiResponse.success(
            _upload_failure_payload(
                message="当前上传接口仅支持 business_type=plan_bom。",
                file_name=file.filename,
                file_size=len(content),
                next_action="请将 business_type 改为 plan_bom 后重新上传。",
            ),
            trace_id=trace_id,
        )
    if suffix not in {".xls", ".xlsx", ".xlsm"}:
        return ApiResponse.success(
            _upload_failure_payload(
                message="仅支持 .xls / .xlsx / .xlsm 格式的 BOM Excel 文件。",
                file_name=file.filename,
                file_size=len(content),
                next_action="请上传有效的 BOM Excel 文件。",
            ),
            trace_id=trace_id,
        )
    if not content:
        return ApiResponse.success(
            _upload_failure_payload(message="上传文件为空。", file_name=file.filename, file_size=0, next_action="请重新选择非空 Excel 文件。"),
            trace_id=trace_id,
        )
    if len(content) > max_bytes:
        return ApiResponse.success(
            _upload_failure_payload(
                message="上传文件超过 20MB 限制。",
                file_name=file.filename,
                file_size=len(content),
                next_action="请拆分文件或联系管理员调整上传限制。",
            ),
            trace_id=trace_id,
        )

    try:
        report = service.import_bytes(content, file_name=file.filename or "plan_bom.xlsx")
    except Exception as exc:  # noqa: BLE001
        return ApiResponse.success(
            _upload_failure_payload(
                message="BOM Excel 上传解析失败，请确认文件是有效 Excel 且符合计划 BOM 模板。",
                file_name=file.filename,
                file_size=len(content),
                next_action="请修正 Excel 后重新上传。",
                error=str(exc)[:300],
            ),
            trace_id=trace_id,
        )
    quality_summary = {
        "sheet_count": report.sheet_count,
        "revision_count": report.revision_count,
        "persisted_business_data": report.persisted_business_data,
        "rollback_applied": report.rollback_applied,
        "source": source,
        "overwrite": overwrite,
        "remark": remark,
    }
    payload = {
        "success": report.status == "success",
        "message": "BOM Excel 上传解析成功。" if report.status == "success" else "BOM Excel 上传解析失败，请查看错误明细。",
        "import_batch_id": report.batch_id,
        "file_name": report.file_name,
        "file_size": len(content),
        "parsed_orders_count": report.header_count,
        "parsed_materials_count": report.material_line_count,
        "warning_count": report.warning_count,
        "error_count": report.error_count,
        "data_quality_summary": quality_summary,
        "report_path": f"tmp/plan_bom/import_reports/{report.batch_id}.json",
        "next_action": "可以进入 /api/v1/plan-bom/qa/ask 查询。" if report.status == "success" else "请修正 Excel 后重新上传。",
        "errors": [item.model_dump(mode="json") for item in report.errors[:20]],
        "warnings": [item.model_dump(mode="json") for item in report.warnings[:20]],
    }
    return ApiResponse.success(payload, trace_id=trace_id)
