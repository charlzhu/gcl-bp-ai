from fastapi import APIRouter, Depends, Request

from backend.app.api.deps import get_chat_service
from backend.app.core.response import ResponseEnvelope, success_response
from backend.app.schemas.chat import ChatQueryRequest, ChatQueryResponse
from backend.app.services.chat_service import ChatService

router = APIRouter(prefix="/chat/logistics")


@router.post("/query", response_model=ResponseEnvelope[ChatQueryResponse])
def logistics_chat_query(
    payload: ChatQueryRequest,
    request: Request,
    chat_service: ChatService = Depends(get_chat_service),
) -> ResponseEnvelope[ChatQueryResponse]:
    """

    :param payload:
    :param request:
    :param chat_service:
    :return:
    """
    data = chat_service.ask(payload)
    return success_response(request, data)
