from pydantic import BaseModel


class PriorityPredictionRequest(BaseModel):
    text: str


class PriorityPredictionResponse(BaseModel):
    priority: str