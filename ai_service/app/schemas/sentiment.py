from pydantic import BaseModel, Field


class SentimentRequest(BaseModel):
    ticket_id: int = Field(
        ...,
        description="ID of the ticket for sentiment analysis",
    )


class SentimentData(BaseModel):
    ticket_id: int
    sentiment: str
    model_version: str
    confidence_score: float | None = None


class SentimentResponse(BaseModel):
    status: bool
    message: str
    data: SentimentData | None = None