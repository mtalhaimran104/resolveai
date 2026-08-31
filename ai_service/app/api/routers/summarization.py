from fastapi import APIRouter

from app.core.ai_service_helper import AIServiceHelper

from app.schemas.summarization import (
    SummarizationData,
    SummarizationRequest,
    SummarizationResponse,
)

from app.services.summarization_service import (
    summarize_student_query,
)


router = APIRouter(
    prefix="/api/v1/summarization",
    tags=["Summarization"],
)


@router.post(
    "/predict",
    response_model=SummarizationResponse,
)
def summarize(
    request: SummarizationRequest,
) -> SummarizationResponse:

    # Get ticket text from database
    ticket_text = AIServiceHelper.getTicketTextById(
        request.ticket_id
    )

    # Ticket does not exist
    if ticket_text is None:
        return SummarizationResponse(
            status=False,
            message="Ticket not found",
            data=None,
        )

    # Generate summary
    summary = summarize_student_query(
        ticket_text
    )

    return SummarizationResponse(
        status=True,
        message="Success",
        data=SummarizationData(
            ticket_id=request.ticket_id,
            summary=summary,
            model_name="resolveai-extractive-summarizer",
            model_version="v1",
            confidence_score=None,
        ),
    )