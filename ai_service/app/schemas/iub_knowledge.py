from pydantic import BaseModel, Field


class IUBKnowledgeRequest(BaseModel):

    question: str = Field(
        ...,
        min_length=1,
        description="IUB student question"
    )


class IUBKnowledgeResponse(BaseModel):

    answer: str

    similarity_score: float

    confidence_level: str

    query_type: str