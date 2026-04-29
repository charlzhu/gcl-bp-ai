from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Request

from backend.app.api.deps import get_plan_bom_query_service
from backend.app.domains.plan_bom.schemas.query import PlanBomCompareQueryRequest, PlanBomDetailQueryRequest
from backend.app.domains.plan_bom.services.query_service import PlanBomQueryService
from backend.app.schemas.common import ApiResponse

router = APIRouter()


@router.post("/detail", response_model=ApiResponse)
def detail_query(
    payload: PlanBomDetailQueryRequest,
    request: Request,
    service: PlanBomQueryService = Depends(get_plan_bom_query_service),
) -> ApiResponse:
    """计划 BOM 基础材料查询入口。

    说明：
    1. 当前只支持订单号、订单名称、评审号别名定位；
    2. 当前只返回当前版本下 5 类核心材料或候选列表；
    3. 不实现两订单差异对比、导出或 SAP 接入。
    """
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    result = service.detail(payload)
    return ApiResponse.success(result.model_dump(mode="json"), trace_id=trace_id)


@router.post("/compare", response_model=ApiResponse)
def compare_query(
    payload: PlanBomCompareQueryRequest,
    request: Request,
    service: PlanBomQueryService = Depends(get_plan_bom_query_service),
) -> ApiResponse:
    """计划 BOM compare 查询入口。

    说明：
    1. 当前已实现 compare 骨架、候选链路和核心差异计算；
    2. 当前里程碑补充 compare 历史 / 快照 / 回放最小链路；
    3. 当前不实现运行态抽验、导出或 SAP 接入。
    """
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    result = service.compare(payload, trace_id=trace_id)
    # compare 历史回放依赖 `sys_query_log` 中的快照。
    # 当前 `get_db()` 只负责关闭会话，不会自动提交事务，因此 compare 请求成功后
    # 需要在 endpoint 层显式提交，让 replay 的下一个请求能读到这条历史记录。
    service.repository.db.commit()
    return ApiResponse.success(result.model_dump(mode="json"), trace_id=trace_id)


@router.get("/compare/replay/{log_id}", response_model=ApiResponse)
def compare_replay(
    request: Request,
    log_id: int = Path(..., ge=1, description="compare 查询日志 ID"),
    service: PlanBomQueryService = Depends(get_plan_bom_query_service),
) -> ApiResponse:
    """计划 BOM compare 历史回放入口。

    说明：
    1. 当前只回放 compare 写入 `sys_query_log` 的受控快照；
    2. 回放结果不保证等同于实时再次执行，只保证与历史快照一致；
    3. 当前不在回放阶段重新计算全量差异明细。
    """
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    result = service.compare_replay(log_id=log_id)
    return ApiResponse.success(result.model_dump(mode="json"), trace_id=trace_id)
