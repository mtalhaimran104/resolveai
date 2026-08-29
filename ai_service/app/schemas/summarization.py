from typing import Optional

from pydantic import BaseModel


class SummarizationRequest(BaseModel):
    text: str


class SummarizationResponse(BaseModel):
    text: str
    summary: str

    model_version: str = "v1"
    confidence_score: Optional[float] = None