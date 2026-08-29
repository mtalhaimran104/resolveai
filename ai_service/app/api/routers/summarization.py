from fastapi import APIRouter

from app.schemas.summarization import (
    SummarizationRequest,
    SummarizationResponse,
)

from app.services.summarization_service import (
    summarize_student_query,
)


router = APIRouter(
    prefix="/summarization",
    tags=["Summarization"],
)


@router.post(
    "/",
    response_model=SummarizationResponse,
)
def summarize(
    request: SummarizationRequest,
):
    summary = summarize_student_query(request.text)

    return SummarizationResponse(
        text=request.text,
        summary=summary,
        model_name="resolveai-extractive-summarizer",
        model_version="v1",
        confidence_score=None,
    )