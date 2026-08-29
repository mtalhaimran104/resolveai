# app/schemas/faq.py

from pydantic import BaseModel, Field


# ============================================================
# FAQ REQUEST
# ============================================================

class FAQRequest(BaseModel):
    """
    Request model for an IUB FAQ question.
    """

    question: str = Field(
        ...,
        min_length=1,
        description="Student's IUB-related question"
    )


# ============================================================
# FAQ RESPONSE
# ============================================================

class FAQResponse(BaseModel):
    """
    Response returned by the FAQ service.
    """

    question: str

    answer: str

    similarity_score: float

    confidence_level: str

    source: str

    found: bool