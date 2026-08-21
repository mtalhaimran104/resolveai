from pydantic import BaseModel, Field


class StudentQueryRequest(BaseModel):

    question: str = Field(
        ...,
        min_length=1,
        description="Student's question"
    )


class StudentQueryResponse(BaseModel):

    question: str
    answer: str
    similarity_score: float
    confidence_level: str