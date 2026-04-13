import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.app.core.logging import reset_trace_id, set_trace_id


class TraceIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, header_name: str = "X-Trace-Id") -> None:
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get(self.header_name, uuid.uuid4().hex)
        request.state.trace_id = trace_id
        token = set_trace_id(trace_id)
        try:
            response = await call_next(request)
        finally:
            reset_trace_id(token)
        response.headers[self.header_name] = trace_id
        return response
