import hashlib
import json
from fastapi import APIRouter
from sqlalchemy import text
from app.core.database import engine
from app.core.ai_service_helper import AIServiceHelper
from app.schemas.classification import (
    ClassificationData,
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
    ticket = AIServiceHelper.getTicketDetailsById(
        request.ticket_id
    )
    if ticket is None:
        return ClassificationResponse(
            status=False,
            message="Ticket not found",
            data=None,
        )
    ticket_text = (
        f"{ticket['subject']}\n\n"
        f"{ticket['description']}"
    ).strip()
    category, confidence = classify_ticket(
        ticket_text
    )
    category_query = text(
        """
        SELECT id, name
        FROM ticket_categories
        WHERE name = :category_name
        AND is_active = TRUE
        """
    )
    with engine.connect() as connection:
        category_record = connection.execute(
            category_query,
            {"category_name": category},
        ).mappings().first()
    if category_record is None:
        return ClassificationResponse(
            status=False,
            message="Predicted category not found",
            data=None,
        )
    category_id = category_record["id"]
    category_title = category_record["name"]
    input_hash = hashlib.sha256(
        ticket_text.encode("utf-8")
    ).hexdigest()
    result_json = {
        "category_id": category_id,
        "category_title": category_title,
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
                "analysis_type": "CLASSIFICATION",
                "model_name": "ticket_classification_model",
                "model_version": "1.0",
                "input_hash": input_hash,
                "result_json": json.dumps(result_json),
                "confidence_score": confidence,
                "status": "SUCCESS",
                "error_message": "",
            },
        )
    return ClassificationResponse(
        status=True,
        message="Success",
        data=ClassificationData(
            ticket_id=request.ticket_id,
            category_id=category_id,
            category_title=category_title,
            confidence=confidence,
        ),
    )

