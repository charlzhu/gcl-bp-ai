from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from backend.app.api.deps import (
    get_query_planning_v2_service,
    get_query_planning_v2_shadow_report_service,
    require_query_planning_internal_access,
)
from backend.app.domains.query_planning.schemas.query_plan_v2 import QueryPlanningV2DiagnoseRequest
from backend.app.domains.query_planning.services.query_planning_v2_service import QueryPlanningV2Service
from backend.app.domains.query_planning.services.shadow_report_service import QueryPlanningV2ShadowReportService
from backend.app.schemas.common import ApiResponse

router = APIRouter()


@router.post("/v2/diagnose", response_model=ApiResponse)
def diagnose_query_plan_v2(
    payload: QueryPlanningV2DiagnoseRequest,
    request: Request,
    _: None = Depends(require_query_planning_internal_access),
    service: QueryPlanningV2Service = Depends(get_query_planning_v2_service),
) -> ApiResponse:
    """Query Planning V2 内部诊断入口。

    说明：
        1. 该接口只输出 shadow query_plan_v2，不替代物流 / BOM 正式问答入口；
        2. 服务只调用规则 planner 或 NLU Center，不执行 SQL、不查数、不生成最终业务答案；
        3. 默认写入 JSONL 审计日志，便于后续回放和灰度对比。
    """

    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    plan = service.plan(
        question=payload.question,
        domain=payload.domain,
        trace_id=trace_id,
        write_audit=payload.write_audit,
    )
    return ApiResponse.success(plan.model_dump(mode="json"), trace_id=trace_id)


@router.get("/v2/shadow-report", response_model=ApiResponse)
def query_plan_v2_shadow_report(
    request: Request,
    _: None = Depends(require_query_planning_internal_access),
    service: QueryPlanningV2ShadowReportService = Depends(get_query_planning_v2_shadow_report_service),
) -> ApiResponse:
    """Query Planning V2 内部 shadow 对比报表入口。

    说明：
        1. 回放内置 10 类物流 / BOM 问法，只输出 query_plan_v2 对比结果；
        2. 不执行正式 Data QA / BOM QA 查询，不生成业务答案；
        3. 默认不写 JSONL，避免健康检查或人工刷新造成审计噪音。
    """

    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    report = service.build_default_report(trace_id=trace_id, write_audit=False)
    return ApiResponse.success(report.model_dump(mode="json"), trace_id=trace_id)


__all__ = ["router"]
