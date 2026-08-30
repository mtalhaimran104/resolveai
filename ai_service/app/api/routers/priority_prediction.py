import hashlib
import json
import time
from pathlib import Path
from fastapi import APIRouter
from sqlalchemy import text
from app.core.database import engine
from app.core.ai_service_helper import AIServiceHelper
from app.schemas.priority_prediction import (
    PriorityPredictionData,
    PriorityPredictionRequest,
    PriorityPredictionResponse,
    PriorityModelMetricsData,
    PriorityModelMetricsResponse,
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
    ticket = AIServiceHelper.getTicketDetailsById(
        request.ticket_id
    )
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
    start_time = time.perf_counter()
    priority, confidence = predict_priority(
        ticket_text
    )
    response_time_ms = round(
        (time.perf_counter() - start_time) * 1000,
        2,
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
            response_time_ms,
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
            :response_time_ms,
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
                "response_time_ms": response_time_ms,
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









@router.get(
    "/metrics",
    response_model=PriorityModelMetricsResponse,
)
def get_priority_model_metrics() -> PriorityModelMetricsResponse:
    metrics_path = (
        Path(__file__).resolve().parent.parent.parent
        / "models"
        / "priority_prediction"
        / "model_metrics.json"
    )
    try:
        with open(
            metrics_path,
            "r",
            encoding="utf-8",
        ) as metrics_file:
            metrics = json.load(metrics_file)
    except (
        FileNotFoundError,
        json.JSONDecodeError,
    ):
        return PriorityModelMetricsResponse(
            status=False,
            message="Priority model metrics not available",
            data=None,
        )
    return PriorityModelMetricsResponse(
        status=True,
        message="Success",
        data=PriorityModelMetricsData(
            model_version=metrics["model_version"],
            accuracy=metrics["accuracy"],
            precision=metrics["precision"],
            recall=metrics["recall"],
            f1_score=metrics["f1_score"],
        ),
    )




