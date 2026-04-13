import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.app.core.exceptions import AppException

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    """把 FastAPI / Pydantic 校验错误里的不可序列化对象转换成基础类型。"""
    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


def _payload(
    request: Request,
    *,
    code: int,
    message: str,
    data: Any | None = None,
) -> dict[str, Any]:
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    return {
        "code": code,
        "message": message,
        "data": data or {},
        "trace_id": trace_id,
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(
        request: Request,
        exc: AppException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(
                request,
                code=exc.code,
                message=exc.message,
                data=exc.details,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_payload(
                request,
                code=4220,
                message="请求参数校验失败",
                data={"errors": _json_safe(exc.errors())},
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unknown_exception(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception("Unhandled exception raised: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_payload(
                request,
                code=5000,
                message="服务内部异常",
                data={},
            ),
        )
