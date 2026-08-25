from typing import Any, Dict, Optional

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

    analysis_type: str = "SENTIMENT"
    model_name: str = "resolveai-sentiment"
    model_version: str = "v1"

    result_json: Dict[str, Any]

    confidence_score: Optional[float] = None

    status: str = "SUCCESS"