from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import api_router
from backend.app.core.config import get_settings
from backend.app.core.exception_handlers import register_exception_handlers
from backend.app.core.logging import configure_logging
from backend.app.core.middleware import TraceIdMiddleware
from backend.app.middleware.request_context import RequestContextMiddleware


def create_application() -> FastAPI:
    settings = get_settings()
    settings.ensure_runtime_dirs()
    configure_logging(settings.app_debug, log_level=settings.log_level)

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.app_debug,
        description="GCL BP 智能平台后端基础骨架，包含健康检查、查询、任务与自然语言入口。",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(
        RequestContextMiddleware,
        request_id_header_name=settings.request_id_header_name,
    )
    application.add_middleware(
        TraceIdMiddleware,
        header_name=settings.trace_header_name,
    )

    register_exception_handlers(application)
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    if settings.api_v1_prefix != settings.api_v1_prefix:
        application.include_router(api_router, prefix=settings.api_v1_prefix)

    @application.get("/", tags=["Root"])
    async def root() -> dict[str, str]:
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
        }

    return application


app = create_application()
create_app = create_application
