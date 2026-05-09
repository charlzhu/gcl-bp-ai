from __future__ import annotations

from fastapi import APIRouter, Depends, File, Path, Request, UploadFile

from backend.app.api.deps import get_plan_power_model_service, require_plan_power_write_access
from backend.app.domains.plan_bom.schemas.power_model import (
    PowerModelImportResponse,
    PowerModelVersionDetailResponse,
    PowerModelVersionListResponse,
)
from backend.app.domains.plan_bom.services.power_model_service import PowerModelImportError, PowerModelService
from backend.app.schemas.common import ApiResponse

router = APIRouter()


@router.post("/import", response_model=ApiResponse)
async def import_power_model(
    request: Request,
    file: UploadFile = File(...),
    _write_access: None = Depends(require_plan_power_write_access),
    service: PowerModelService = Depends(get_plan_power_model_service),
) -> ApiResponse:
    """导入计划 BOM 功率模型 xlsm。

    参数：
        file: xlsm 文件，M2 只做只读解析和版本化入库。

    返回：
        统一 ApiResponse，data 中包含 import_status、version 和详情摘要。

    权限说明：
        已按用户要求移除旧的临时管理令牌；生产环境在正式用户/权限模块接入前由环境门禁阻断写操作。
    """
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    if not (file.filename or "").lower().endswith(".xlsm"):
        return ApiResponse(code=400, message="功率模型导入仅支持 .xlsm 文件。", data=None, trace_id=trace_id)
    try:
        result = await service.import_upload(file)
    except PowerModelImportError as exc:
        return ApiResponse(code=400, message=str(exc), data=None, trace_id=trace_id)
    payload = PowerModelImportResponse(import_status=result.import_status, version=result.version, detail=result.detail)
    return ApiResponse.success(payload.model_dump(mode="json"), trace_id=trace_id)


@router.get("/versions", response_model=ApiResponse)
def list_power_model_versions(
    request: Request,
    service: PowerModelService = Depends(get_plan_power_model_service),
) -> ApiResponse:
    """查询功率模型版本列表。

    返回：
        统一 ApiResponse，data 中包含 items 和 total。
    """
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    items = service.list_versions()
    payload = PowerModelVersionListResponse(items=items, total=len(items))
    return ApiResponse.success(payload.model_dump(mode="json"), trace_id=trace_id)


@router.get("/versions/{version_id}", response_model=ApiResponse)
def get_power_model_version_detail(
    request: Request,
    version_id: int = Path(..., ge=1, description="功率模型版本 ID"),
    service: PowerModelService = Depends(get_plan_power_model_service),
) -> ApiResponse:
    """查询功率模型版本详情。

    参数：
        version_id: 功率模型版本 ID。

    返回：
        Sheet、配置项、供应商分布、功率档、标板和 issue 详情。
    """
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    try:
        detail = service.get_version_detail(version_id)
    except ValueError as exc:
        return ApiResponse(code=404, message=str(exc), data=None, trace_id=trace_id)
    payload = PowerModelVersionDetailResponse(**detail)
    return ApiResponse.success(payload.model_dump(mode="json"), trace_id=trace_id)


@router.post("/versions/{version_id}/activate", response_model=ApiResponse)
def activate_power_model_version(
    request: Request,
    version_id: int = Path(..., ge=1, description="功率模型版本 ID"),
    _write_access: None = Depends(require_plan_power_write_access),
    service: PowerModelService = Depends(get_plan_power_model_service),
) -> ApiResponse:
    """激活功率模型版本。

    参数：
        version_id: 待激活版本 ID。

    返回：
        激活后的版本摘要。仓储层保证最多一个 active 版本。

    权限说明：
        已按用户要求移除旧的临时管理令牌；生产环境在正式用户/权限模块接入前由环境门禁阻断写操作。
    """
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    try:
        version = service.activate_version(version_id)
    except ValueError as exc:
        return ApiResponse(code=404, message=str(exc), data=None, trace_id=trace_id)
    return ApiResponse.success(version, trace_id=trace_id)


__all__ = ["router"]
