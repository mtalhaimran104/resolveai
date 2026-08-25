from typing import Any, Dict, Optional

from pydantic import BaseModel


class SummarizationRequest(BaseModel):
    text: str


class SummarizationResponse(BaseModel):
    text: str
    summary: str

    analysis_type: str = "SUMMARY"
    model_name: str = "resolveai-extractive-summarizer"
    model_version: str = "v1"

    result_json: Dict[str, Any]

    confidence_score: Optional[float] = None

    status: str = "SUCCESS"