from typing import Optional

from pydantic import BaseModel, Field


class SentimentRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        description="Student query for sentiment analysis"
    )


class SentimentResponse(BaseModel):
    text: str
    sentiment: str

    model_version: str = "v1"
    confidence_score: Optional[float] = None