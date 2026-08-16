from pydantic import BaseModel


class ClassificationRequest(BaseModel):
    text: str


class ClassificationResponse(BaseModel):
    category: str