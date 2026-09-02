from pydantic import BaseModel, Field


class FAQRequest(BaseModel):
    ticket_id: int = Field(
        ...,
        gt=0,
        description="ID of the ticket for FAQ retrieval",
    )


class FAQData(BaseModel):
    ticket_id: int
    question: str
    answer: str
    similarity_score: float
    confidence_score: float
    confidence_level: str
    source: str
    model_name: str
    model_version: str
    found: bool


class FAQError(BaseModel):
    code: str
    ticket_id: int


class FAQResponse(BaseModel):
    status: bool
    message: str
    data: FAQData | None = None
    error: FAQError | None = None