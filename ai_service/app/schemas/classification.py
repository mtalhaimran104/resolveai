from typing import Optional
from pydantic import BaseModel, Field
class ClassificationRequest(BaseModel):
    ticket_id: int = Field(
        gt=0,
        description="Existing Django ticket database ID.",
    )
class ClassificationData(BaseModel):
    ticket_id: int
    category_id: int
    category_title: str
    confidence: float
class ClassificationResponse(BaseModel):
    status: bool
    message: str
    data: Optional[ClassificationData] = None
