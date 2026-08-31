from pydantic import BaseModel, Field


class SummarizationRequest(BaseModel):
    ticket_id: int = Field(
        ...,
        description="ID of the ticket to summarize",
    )


class SummarizationData(BaseModel):
    ticket_id: int
    summary: str
    model_name: str
    model_version: str
    confidence_score: float | None = None


class SummarizationResponse(BaseModel):
    status: bool
    message: str
    data: SummarizationData | None = None