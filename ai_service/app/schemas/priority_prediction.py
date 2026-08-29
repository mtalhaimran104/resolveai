from typing import Optional
from pydantic import BaseModel, Field
class PriorityPredictionRequest(BaseModel):
    ticket_id: int = Field(
        gt=0,
        description="Existing Django ticket database ID.",
    )
class PriorityPredictionData(BaseModel):
    ticket_id: int
    priority: str
    confidence: float
class PriorityPredictionResponse(BaseModel):
    status: bool
    message: str
    data: Optional[PriorityPredictionData] = None
class PriorityModelMetricsData(BaseModel):
    accuracy: float
    precision: float
    recall: float
    f1_score: float
class PriorityModelMetricsResponse(BaseModel):
    status: bool
    message: str
    data: Optional[PriorityModelMetricsData] = None
