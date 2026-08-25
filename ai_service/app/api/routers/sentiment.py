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
    sentiment = analyze_student_sentiment(
        request.text
    )

    return SentimentResponse(
        text=request.text,
        sentiment=sentiment,
        analysis_type="SENTIMENT",
        model_name="resolveai-sentiment",
        model_version="v1",
        result_json={
            "sentiment": sentiment,
        },
        confidence_score=None,
        status="SUCCESS",
    )