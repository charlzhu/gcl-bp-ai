from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.db.session import get_db
from backend.app.domains.logistics.services.import_service import LogisticsHistoryImportService
from backend.app.domains.logistics.services.nl2query_service import LogisticsNL2QueryService
from backend.app.domains.logistics.services.query_service import LogisticsQueryService as DomainLogisticsQueryService
from backend.app.domains.logistics.services.serving_refresh_service import LogisticsServingRefreshService
from backend.app.domains.logistics.services.sync_service import LogisticsSystemSyncService
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
