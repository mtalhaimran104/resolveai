from fastapi import APIRouter

from app.core.ai_service_helper import AIServiceHelper

from app.schemas.sentiment import (
    SentimentData,
    SentimentRequest,
    SentimentResponse,
)

from app.services.sentiment_service import (
    analyze_student_sentiment,
)


router = APIRouter(
    prefix="/api/v1/sentiment",
    tags=["Sentiment Analysis"],
)


@router.post(
    "/predict",
    response_model=SentimentResponse,
)
def predict_sentiment(
    request: SentimentRequest,
) -> SentimentResponse:

    ticket_text = AIServiceHelper.getTicketTextById(
        request.ticket_id
    )

    if ticket_text is None:
        return SentimentResponse(
            status=False,
            message="Ticket not found",
            data=None,
        )

    sentiment, confidence_score = analyze_student_sentiment(
        ticket_text
    )

    return SentimentResponse(
        status=True,
        message="Success",
        data=SentimentData(
            ticket_id=request.ticket_id,
            sentiment=sentiment,
            model_version="v1",
            confidence_score=confidence_score,
        ),
    )
