from pydantic import BaseModel


class SummarizationRequest(BaseModel):
    text: str


class SummarizationResponse(BaseModel):
    text: str
    summary: str