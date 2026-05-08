from functools import lru_cache

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.db.session import get_db
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
from backend.app.domains.plan_bom.services.qa_service import PlanBomQaService
from backend.app.domains.plan_bom.services.query_service import PlanBomQueryService
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


def require_plan_power_admin(
    x_plan_power_admin_token: str | None = Header(default=None, alias="X-Plan-Power-Admin-Token"),
    settings: Settings = Depends(get_settings),
) -> None:
    """校验功率模型管理写接口的管理员令牌。

    参数：
        x_plan_power_admin_token: 请求头里的管理令牌；
        settings: 应用配置，读取 `plan_power_admin_token`。

    返回：
        校验通过时返回 None。

    关键业务逻辑：
        M2 的模型导入和激活会改变后续功率模型版本状态，属于管理写操作。
        本地 / 测试环境若未配置令牌则允许联调；dev/prod 环境必须配置并匹配令牌。
    """
    expected_token = settings.plan_power_admin_token.strip()
    if not expected_token:
        if settings.app_env in {"local", "test"}:
            return None
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="未配置功率模型管理令牌，拒绝执行管理写操作。",
        )
    if x_plan_power_admin_token != expected_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="功率模型管理令牌无效。")
    return None


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
    return PlanBomQaService(
        repository=repository,
        query_service=PlanBomQueryService(repository=repository),
        nlu_service=PlanBomNluCenterService(repository=repository),
        presentation_service=PlanBomAnswerPresentationService(),
    )
