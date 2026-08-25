import hashlib
import json
from fastapi import APIRouter
from sqlalchemy import text
from app.core.database import engine
from app.schemas.priority_prediction import (
    PriorityPredictionData,
    PriorityPredictionRequest,
    PriorityPredictionResponse,
)
from app.services.priority_prediction_service import (
    predict_priority,
)
router = APIRouter(
    prefix="/api/v1/priority",
    tags=["Priority Prediction"],
)
@router.post(
    "/predict",
    response_model=PriorityPredictionResponse,
)
def predict_ticket_priority(
    request: PriorityPredictionRequest,
) -> PriorityPredictionResponse:
    ticket_query = text(
        """
        SELECT id, subject, description
        FROM tickets
        WHERE id = :ticket_id
        """
    )
    with engine.connect() as connection:
        ticket = connection.execute(
            ticket_query,
            {"ticket_id": request.ticket_id},
        ).mappings().first()
    if ticket is None:
        return PriorityPredictionResponse(
            status=False,
            message="Ticket not found",
            data=None,
        )
    ticket_text = (
        f"{ticket['subject']}\n\n"
        f"{ticket['description']}"
    ).strip()
    priority, confidence = predict_priority(
        ticket_text
    )
    input_hash = hashlib.sha256(
        ticket_text.encode("utf-8")
    ).hexdigest()
    result_json = {
        "priority": priority,
        "confidence": confidence,
    }
    analysis_insert = text(
        """
        INSERT INTO ai_analyses (
            ticket_id,
            analysis_type,
            model_name,
            model_version,
            input_hash,
            result_json,
            confidence_score,
            status,
            error_message,
            created_at,
            updated_at
        )
        VALUES (
            :ticket_id,
            :analysis_type,
            :model_name,
            :model_version,
            :input_hash,
            :result_json,
            :confidence_score,
            :status,
            :error_message,
            NOW(),
            NOW()
        )
        """
    )
    with engine.begin() as connection:
        connection.execute(
            analysis_insert,
            {
                "ticket_id": request.ticket_id,
                "analysis_type": "PRIORITY",
                "model_name": "priority_prediction_model",
                "model_version": "1.0",
                "input_hash": input_hash,
                "result_json": json.dumps(result_json),
                "confidence_score": confidence,
                "status": "SUCCESS",
                "error_message": "",
            },
        )
    return PriorityPredictionResponse(
        status=True,
        message="Success",
        data=PriorityPredictionData(
            ticket_id=request.ticket_id,
            priority=priority,
            confidence=confidence,
        ),
    )
