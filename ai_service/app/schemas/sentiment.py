from pydantic import BaseModel, Field
from typing import Optional


class SentimentRequest(BaseModel):
    ticket_id: int = Field(
        ...,
        description="ID of the ticket for sentiment analysis",
    )


class SentimentData(BaseModel):
    ticket_id: int
    sentiment: str
    model_version: str
    confidence_score: Optional[float] = None


class SentimentError(BaseModel):
    code: str
    ticket_id: int


class SentimentResponse(BaseModel):
    status: bool
    message: str
    data: Optional[SentimentData] = None
    error: Optional[SentimentError] = None