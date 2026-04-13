from typing import Any, Literal

from pydantic import BaseModel, Field

IntentType = Literal["metrics", "compare", "detail", "unknown"]


class ChatQueryRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=200)
    session_id: str | None = Field(default=None, max_length=64)


class ChatQueryResponse(BaseModel):
    intent: IntentType
    answer: str
    normalized_request: dict[str, Any]
    structured_result: dict[str, Any]
