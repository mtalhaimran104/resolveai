from fastapi import APIRouter

from app.schemas.iub_knowledge import (
    IUBKnowledgeRequest,
    IUBKnowledgeResponse
)

from app.services.iub_knowledge_service import (
    search_iub_programs
)


router = APIRouter(
    prefix="/iub",
    tags=["IUB Knowledge"]
)


@router.post(
    "/programs",
    response_model=IUBKnowledgeResponse
)
def iub_program_search(
    request: IUBKnowledgeRequest
):

    return search_iub_programs(
        request.question
    )