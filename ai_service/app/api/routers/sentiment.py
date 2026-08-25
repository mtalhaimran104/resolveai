from fastapi import APIRouter

from app.schemas.sentiment import (
    SentimentRequest,
    SentimentResponse,
)

from app.services.sentiment_service import (
    analyze_student_sentiment,
)


router = APIRouter(
    prefix="/sentiment",
    tags=["Sentiment Analysis"],
)


@router.post(
    "/",
    response_model=SentimentResponse,
)
def sentiment_analysis(
    request: SentimentRequest,
):
    sentiment, confidence_score = analyze_student_sentiment(
        request.text
    )

    return SentimentResponse(
        text=request.text,
        sentiment=sentiment,
        model_version="v1",
        confidence_score=confidence_score,
    )