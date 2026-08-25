from fastapi import APIRouter
from app.schemas.classification import (
    ClassificationRequest,
    ClassificationResponse,
)
from app.services.classification_service import classify_ticket
router = APIRouter(
    prefix="/api/v1/classification",
    tags=["Classification"],
)
@router.post(
    "/predict",
    response_model=ClassificationResponse,
)
def predict_classification(
    request: ClassificationRequest,
) -> ClassificationResponse:
    # Fetch ticket details from DB where id = request.ticket_id
    # 
    #
    # 
    category, confidence = classify_ticket(request.text)
          
    return ClassificationResponse(
        ticket_id=request.ticket_id,
        category=category,
        confidence=confidence,
    )
