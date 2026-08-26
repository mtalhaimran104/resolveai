from typing import Annotated
from pydantic import BaseModel, Field, field_validator
class PriorityPredictionRequest(BaseModel):
    ticket_id: Annotated[
        int,
        Field(
            gt=0,
            description="Existing Django ticket database ID.",
        ),
    ]
    text: Annotated[
        str,
        Field(
            min_length=1,
            max_length=5000,
            description="Ticket text for priority prediction.",
        ),
    ]
    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(
                "Ticket text cannot be empty or whitespace only."
            )
        return value
class PriorityPredictionResponse(BaseModel):
    ticket_id: int
    priority: str
    confidence: float
