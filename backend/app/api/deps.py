from functools import lru_cache

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.db.session import get_db
from backend.app.domains.business_analysis.services.inventory_sales_production.qa_service import (
    InventorySalesProductionQaService,
)
from backend.app.domains.logistics.repositories.query_repository import LogisticsQueryRepository
from backend.app.domains.logistics.services.import_service import LogisticsHistoryImportService
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.domains.logistics.services.nl2query_service import LogisticsNL2QueryService
from backend.app.domains.logistics.services.query_service import LogisticsQueryService as DomainLogisticsQueryService
from backend.app.domains.logistics.services.rag_service import LogisticsRagService
from backend.app.domains.logistics.services.serving_refresh_service import LogisticsServingRefreshService
from backend.app.domains.logistics.services.sync_service import LogisticsSystemSyncService
from backend.app.domains.plan_bom.repositories.import_repository import PlanBomImportRepository
from backend.app.domains.plan_bom.repositories.power_model_repository import PowerModelRepository
from backend.app.domains.plan_bom.repositories.query_repository import PlanBomQueryRepository
from backend.app.domains.plan_bom.services.answer_presentation_service import PlanBomAnswerPresentationService
from backend.app.domains.plan_bom.services.excel_import_service import PlanBomExcelImportService
from backend.app.domains.plan_bom.services.nlu_center_service import PlanBomNluCenterService
from backend.app.domains.plan_bom.services.power_model_service import PowerModelService
from backend.app.domains.plan_bom.services.power_config_resolver_service import PlanBomPowerConfigResolverService
from backend.app.domains.plan_bom.services.power_prediction_engine import PowerPredictionEngine
from backend.app.domains.plan_bom.services.power_recommendation_service import PowerRecommendationService
from backend.app.domains.plan_bom.services.qa_service import PlanBomQaService
from backend.app.domains.plan_bom.services.query_service import PlanBomQueryService
from backend.app.domains.query_planning.services.logistics_adapter import LogisticsQueryPlanningAdapter
from backend.app.domains.query_planning.services.plan_bom_adapter import PlanBomQueryPlanningAdapter
from backend.app.domains.query_planning.services.query_planning_v2_service import QueryPlanningV2Service
from backend.app.domains.query_planning.services.shadow_report_service import QueryPlanningV2ShadowReportService
from backend.app.repositories.logistics_query_repo import InMemoryLogisticsQueryRepository
from backend.app.repositories.task_repo import InMemoryTaskRepository
from backend.app.services.chat_service import ChatService
from backend.app.services.compare_service import CompareService
from backend.app.services.health_service import HealthService
from backend.app.services.query_log_service import QueryLogService
from backend.app.services.query_service import QueryService
from backend.app.services.task_service import TaskService
from backend.app.services.upload_service import UploadService


@lru_cache
def get_logistics_query_repository() -> InMemoryLogisticsQueryRepository:
    return InMemoryLogisticsQueryRepository()


@lru_cache
def get_task_repository() -> InMemoryTaskRepository:
    return InMemoryTaskRepository()


def get_health_service(
    settings: Settings = Depends(get_settings),
) -> HealthService:
    return HealthService(settings)


def get_query_log_service(
    db: Session = Depends(get_db),
) -> QueryLogService:
    """查询历史服务依赖。

    当前直接复用主库会话和物流查询仓储，避免再增加一套独立日志读写层。
    """
    return QueryLogService(db=db)


def get_query_service(
    repository: InMemoryLogisticsQueryRepository = Depends(get_logistics_query_repository),
) -> QueryService:
    return QueryService(repository)


def get_compare_service(
    query_service: QueryService = Depends(get_query_service),
) -> CompareService:
    return CompareService(query_service)


def get_task_service(
    task_repository: InMemoryTaskRepository = Depends(get_task_repository),
) -> TaskService:
    return TaskService(task_repository)


def get_upload_service(
    task_repository: InMemoryTaskRepository = Depends(get_task_repository),
    settings: Settings = Depends(get_settings),
) -> UploadService:
    return UploadService(task_repository=task_repository, settings=settings)


def get_chat_service(
    query_service: QueryService = Depends(get_query_service),
    compare_service: CompareService = Depends(get_compare_service),
) -> ChatService:
    return ChatService(query_service=query_service, compare_service=compare_service)


def get_domain_query_service(
    db: Session = Depends(get_db),
    query_service: QueryService = Depends(get_query_service),
    compare_service: CompareService = Depends(get_compare_service),
) -> DomainLogisticsQueryService:
    return DomainLogisticsQueryService(
        db=db,
        fallback_query_service=query_service,
        fallback_compare_service=compare_service,
    )


def get_domain_import_service(
    upload_service: UploadService = Depends(get_upload_service),
) -> LogisticsHistoryImportService:
    return LogisticsHistoryImportService(upload_service=upload_service)


def get_domain_serving_refresh_service() -> LogisticsServingRefreshService:
    return LogisticsServingRefreshService()


def get_domain_sync_service(
) -> LogisticsSystemSyncService:
    return LogisticsSystemSyncService()


def get_domain_nl2query_service(
    domain_query_service: DomainLogisticsQueryService = Depends(get_domain_query_service),
) -> LogisticsNL2QueryService:
    return LogisticsNL2QueryService(query_service=domain_query_service)


def get_logistics_rag_service(
    settings: Settings = Depends(get_settings),
) -> LogisticsRagService:
    """物流 RAG 服务依赖。

    当前优先返回最小本地版 RAG 服务：
    1. 文档索引落本地 JSON；
    2. 查询走本地向量检索；
    3. 不依赖当前环境必须先接通 Milvus/LLM。
    """
    return LogisticsRagService(settings=settings)


def get_logistics_data_qa_service(
    db: Session = Depends(get_db),
) -> LogisticsDataQaService:
    """物流数据问答服务依赖。

    当前用于物流结构化数据问答 MVP：
    1. 负责自然语言到受控查询计划的转换；
    2. 负责执行白名单 SQL 查询；
    3. 不承担 BOM 查询、RAG 检索或 Agent 工作流能力。
    """
    return LogisticsDataQaService(db=db)


def get_inventory_sales_production_qa_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> InventorySalesProductionQaService:
    """产销存经营分析问答服务依赖。

    M8 灰度模式：
        1. off/shadow/assist 模式仍使用规则规划器；
        2. nl2sql 模式注入 S3 LLM Catalog Recall 规划器；
        3. 默认 off（上线前不意外激活 NL2SQL 链路）。
    """

    live_gate_enabled = settings.isp_live_qa_gate_enabled
    live_gate_mode = settings.isp_live_qa_gate_mode
    if live_gate_enabled and live_gate_mode == "nl2sql":
        # nl2sql 模式：使用 LLM Catalog Recall 规划器
        from backend.app.domains.business_analysis.services.inventory_sales_production.nl2sql_query_planner import (
            InventorySalesProductionNl2SqlQueryPlanner,
        )

        nl2sql_planner = InventorySalesProductionNl2SqlQueryPlanner(
            llm_api_key=settings.llm_api_key or "",
            llm_base_url=settings.llm_base_url or "",
            llm_model=settings.llm_model or "qwen-max",
            timeout=15.0,
        )
        return InventorySalesProductionQaService(
            db=db,
            nl2sql_planner=nl2sql_planner,
            live_gate_enabled=True,
            live_gate_mode="nl2sql",
        )

    return InventorySalesProductionQaService(
        db=db,
        live_gate_enabled=live_gate_enabled,
        live_gate_mode=live_gate_mode,
    )


def get_plan_bom_import_service(
    db: Session = Depends(get_db),
) -> PlanBomExcelImportService:
    """计划 BOM Excel 入库服务依赖。

    当前只用于 Excel 读取、解析和批次入库，不提供查询、导出或 SAP 接入能力。
    """
    return PlanBomExcelImportService(repository=PlanBomImportRepository(db))


def get_plan_bom_query_service(
    db: Session = Depends(get_db),
) -> PlanBomQueryService:
    """计划 BOM 基础查询服务依赖。

    当前用于基础材料查询和 compare 里程碑 1 的骨架候选链路，
    不提供 compare 差异算法、导出或 SAP 接入能力。
    """
    return PlanBomQueryService(repository=PlanBomQueryRepository(db))



def require_plan_power_write_access(
    settings: Settings = Depends(get_settings),
) -> None:
    """功率模型写操作的临时环境保护。

    参数：
        settings: 当前应用配置，用于判断运行环境。

    返回：
        无返回值。非生产环境允许继续执行，生产环境在正式用户/权限模块接入前阻断写操作。

    业务说明：
        用户已明确废弃旧的功率模型管理令牌，因此这里不再校验临时 token。
        为避免生产环境在权限模块接入前暴露模型上传/生效切换能力，先以环境门禁兜底。
    """
    if settings.app_env == "prod":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="功率模型写操作需要用户权限模块授权后才能在生产环境执行。",
        )


def require_query_planning_internal_access(
    settings: Settings = Depends(get_settings),
) -> None:
    """Query Planning V2 内部诊断接口的临时环境保护。

    参数：
        settings: 当前应用配置，用于判断运行环境。

    返回：
        无返回值。非生产环境允许内部诊断；生产环境在正式用户/权限模块接入前阻断访问。

    业务说明：
        Query Planning V2 Phase 4 仍处于 shadow 诊断阶段，接口会暴露规划、槽位和 Guardrail
        审计信息。为避免生产环境误暴露内部诊断面，先用环境门禁 fail closed，后续由正式用户
        权限模块接管，不引入临时 token。
    """

    if settings.app_env == "prod":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Query Planning V2 内部诊断接口需要用户权限模块授权后才能在生产环境访问。",
        )


def get_plan_power_model_service(
    db: Session = Depends(get_db),
) -> PowerModelService:
    """计划 BOM 功率模型版本服务依赖。

    当前只用于 M2 xlsm 模型导入、版本查询和激活；
    不接入 PlanBom QA，不承担正式功率预测计算。
    """
    return PowerModelService(repository=PowerModelRepository(db))


def get_plan_bom_qa_service(
    db: Session = Depends(get_db),
) -> PlanBomQaService:
    """计划 BOM 自然语言问答服务依赖。

    当前复用计划 BOM 已有 repository/query service，并补充独立 NLU 与表达层；
    不复用物流 query_key，也不让 LLM 直接生成事实性答案。
    """
    repository = PlanBomQueryRepository(db)
    engine = PowerPredictionEngine(db)
    return PlanBomQaService(
        repository=repository,
        query_service=PlanBomQueryService(repository=repository),
        nlu_service=PlanBomNluCenterService(repository=repository),
        presentation_service=PlanBomAnswerPresentationService(),
        power_config_resolver=PlanBomPowerConfigResolverService(db, repository=repository),
        power_prediction_engine=engine,
        power_recommendation_service=PowerRecommendationService(db, engine=engine),
    )


def get_query_planning_v2_service(
    db: Session = Depends(get_db),
) -> QueryPlanningV2Service:
    """Query Planning V2 诊断服务依赖。

    说明：
        1. 只为内部诊断接口生成 shadow query_plan_v2；
        2. 物流侧只实例化规则 planner adapter；
        3. BOM 侧只注入 NLU Center adapter，不调用 PlanBomQaService.ask。
    """

    plan_bom_repository = PlanBomQueryRepository(db)
    return QueryPlanningV2Service(
        logistics_adapter=LogisticsQueryPlanningAdapter(),
        plan_bom_adapter=PlanBomQueryPlanningAdapter(
            nlu_service=PlanBomNluCenterService(repository=plan_bom_repository),
        ),
    )


def get_query_planning_v2_shadow_report_service(
    service: QueryPlanningV2Service = Depends(get_query_planning_v2_service),
    db: Session = Depends(get_db),
) -> QueryPlanningV2ShadowReportService:
    """Query Planning V2 shadow / gray 对比报表服务依赖。

    参数：
        service: 已构造的 Query Planning V2 统一服务。
        db: 当前数据库会话；仅用于 Phase 5 只读 sys_query_log 灰度报表。

    返回：
        可回放 shadow query_plan，并可只读聚合真实 sys_query_log 的报表服务。
    """

    return QueryPlanningV2ShadowReportService(
        planning_service=service,
        query_log_repository=LogisticsQueryRepository(),
        db=db,
    )
