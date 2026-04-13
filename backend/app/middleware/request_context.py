import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, request_id_header_name: str = "X-Request-Id") -> None:
        super().__init__(app)
        self.request_id_header_name = request_id_header_name

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = getattr(request.state, "trace_id", uuid.uuid4().hex)
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        cost_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers[self.request_id_header_name] = request_id
        logger.info(
            "request_id=%s method=%s path=%s status=%s cost_ms=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            cost_ms,
        )
        return response
