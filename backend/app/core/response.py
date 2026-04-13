from typing import Generic, TypeVar

from fastapi import Request
from pydantic import BaseModel

T = TypeVar("T")


class ResponseEnvelope(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: T
    trace_id: str


def success_response(request: Request, data: T, message: str = "success") -> ResponseEnvelope[T]:
    trace_id = getattr(request.state, "trace_id", "")
    return ResponseEnvelope(code=0, message=message, data=data, trace_id=trace_id)
