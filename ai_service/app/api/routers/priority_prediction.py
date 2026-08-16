from fastapi import APIRouter

from app.schemas.priority_prediction import (
    PriorityPredictionRequest,
    PriorityPredictionResponse
)

from app.services.priority_prediction_service import predict_priority


router = APIRouter(
    prefix="/priority",
    tags=["Priority Prediction"]
)


@router.post(
    "/predict",
    response_model=PriorityPredictionResponse
)
def predict_ticket_priority(
    request: PriorityPredictionRequest
):
    priority = predict_priority(request.text)

    return {
        "priority": priority
    }