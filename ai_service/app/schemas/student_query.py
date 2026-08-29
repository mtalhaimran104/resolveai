from pydantic import BaseModel, Field


class StudentQueryRequest(BaseModel):

    question: str = Field(
        ...,
        min_length=1,
        description="Student's question",
    )


class StudentQueryResponse(BaseModel):

    question: str

    answer: str

    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
    )

    confidence_level: str

    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
    )

    model_name: str = "resolveai-student-query"

    model_version: str = "v1"