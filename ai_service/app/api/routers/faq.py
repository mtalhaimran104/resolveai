from fastapi import APIRouter

from app.core.ai_service_helper import AIServiceHelper

from app.schemas.faq import (
    FAQRequest,
    FAQResponse,
    FAQData,
    FAQError,
)

from app.services.faq_service import find_faq_answer


router = APIRouter(
    prefix="/faq",
    tags=["FAQ"],
)


@router.post(
    "/",
    response_model=FAQResponse,
)
def faq_search(
    request: FAQRequest,
) -> FAQResponse:

    # --------------------------------------------------------
    # Get ticket text from database
    # --------------------------------------------------------

    ticket = AIServiceHelper.getTicketDetailsById(
        request.ticket_id
    )

    # --------------------------------------------------------
    # Ticket does not exist
    # --------------------------------------------------------

    if ticket is None:
        return FAQResponse(
            status=False,
            message="Ticket not found",
            data=None,
            error=FAQError(
                code="TICKET_NOT_FOUND",
                ticket_id=request.ticket_id,
            ),
        )

    # --------------------------------------------------------
    # Build question from ticket
    # --------------------------------------------------------

    question = (
        f"{ticket['subject']}\n\n"
        f"{ticket['description']}"
    ).strip()

    # --------------------------------------------------------
    # FAQ retrieval
    # --------------------------------------------------------

    result = find_faq_answer(question)

    # --------------------------------------------------------
    # Return standard SRS response
    # --------------------------------------------------------

    return FAQResponse(
        status=True,
        message="Success",
        data=FAQData(
            ticket_id=request.ticket_id,
            question=result.get("question", question),
            answer=result.get("answer", ""),
            similarity_score=result.get(
                "similarity_score", 0.0
            ),
            confidence_score=result.get(
                "confidence_score", 0.0
            ),
            confidence_level=result.get(
                "confidence_level", "Low"
            ),
            source=result.get(
                "source",
                "faq_not_found"
            ),
            model_name=result.get(
                "model_name",
                "resolveai-faq-retriever"
            ),
            model_version=result.get(
                "model_version",
                "v1"
            ),
            found=result.get("found", False),
        ),
        error=None,
    )