import hashlib
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from tickets.models import Ticket
from .models import AIAnalysis, AIFeedback
from .services import (
    AIServiceError,
    call_classification_service,
    call_priority_service,
)
def _get_ticket_id(request):
    """Extract and validate ticket_id from a JSON request body."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, JsonResponse(
            {"error": "Request body must contain valid JSON."},
            status=400,
        )
    ticket_id = data.get("ticket_id")
    if not isinstance(ticket_id, int) or isinstance(ticket_id, bool):
        return None, JsonResponse(
            {"error": "ticket_id must be a positive integer."},
            status=400,
        )
    if ticket_id <= 0:
        return None, JsonResponse(
            {"error": "ticket_id must be a positive integer."},
            status=400,
        )
    return ticket_id, None
def _build_ticket_text(ticket):
    """Build the text sent to the trained AI model."""
    return f"{ticket.subject}\n\n{ticket.description}".strip()
def _create_input_hash(text):
    """Create a SHA-256 hash for the exact AI model input."""
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()
def _record_failed_analysis(
    *,
    ticket,
    analysis_type,
    model_name,
    input_hash,
    error_message,
):
    """Record a failed AI analysis attempt for traceability."""
    return AIAnalysis.objects.create(
        ticket=ticket,
        analysis_type=analysis_type,
        model_name=model_name,
        model_version="1.0.0",
        input_hash=input_hash,
        result_json={},
        confidence_score=None,
        status=AIAnalysis.Status.FAILED,
        error_message=str(error_message),
    )
@csrf_exempt
@require_POST
def classify_ticket(request):
    """Fetch a ticket, classify it, store the analysis, and return JSON."""
    ticket_id, error_response = _get_ticket_id(request)
    if error_response:
        return error_response
    try:
        ticket = Ticket.objects.get(pk=ticket_id)
    except Ticket.DoesNotExist:
        return JsonResponse(
            {"error": "Ticket not found."},
            status=404,
        )
    text = _build_ticket_text(ticket)
    input_hash = _create_input_hash(text)
    try:
        result = call_classification_service(
            ticket_id=ticket.id,
            text=text,
        )
        category = result["category"]
        confidence = result["confidence"]
    except AIServiceError as exc:
        _record_failed_analysis(
            ticket=ticket,
            analysis_type=AIAnalysis.AnalysisType.CLASSIFICATION,
            model_name="ticket_classification_model",
            input_hash=input_hash,
            error_message=str(exc),
        )
        return JsonResponse(
            {"error": str(exc)},
            status=503,
        )
    except (KeyError, TypeError) as exc:
        error_message = (
            "Classification service returned an invalid response."
        )
        _record_failed_analysis(
            ticket=ticket,
            analysis_type=AIAnalysis.AnalysisType.CLASSIFICATION,
            model_name="ticket_classification_model",
            input_hash=input_hash,
            error_message=error_message,
        )
        return JsonResponse(
            {"error": error_message},
            status=502,
        )
    analysis = AIAnalysis.objects.create(
        ticket=ticket,
        analysis_type=AIAnalysis.AnalysisType.CLASSIFICATION,
        model_name="ticket_classification_model",
        model_version="1.0.0",
        input_hash=input_hash,
        result_json={
            "category": category,
            "confidence": confidence,
        },
        confidence_score=confidence,
        status=AIAnalysis.Status.SUCCESS,
    )
    return JsonResponse(
        {
            "ticket_id": ticket.id,
            "category": category,
            "confidence": confidence,
            "analysis_id": analysis.id,
        },
        status=200,
    )
@csrf_exempt
@require_POST
def predict_ticket_priority(request):
    """Fetch a ticket, predict priority, store the analysis, and return JSON."""
    ticket_id, error_response = _get_ticket_id(request)
    if error_response:
        return error_response
    try:
        ticket = Ticket.objects.get(pk=ticket_id)
    except Ticket.DoesNotExist:
        return JsonResponse(
            {"error": "Ticket not found."},
            status=404,
        )
    text = _build_ticket_text(ticket)
    input_hash = _create_input_hash(text)
    try:
        result = call_priority_service(
            ticket_id=ticket.id,
            text=text,
        )
        priority = result["priority"]
        confidence = result["confidence"]
    except AIServiceError as exc:
        _record_failed_analysis(
            ticket=ticket,
            analysis_type=AIAnalysis.AnalysisType.PRIORITY,
            model_name="priority_prediction_model",
            input_hash=input_hash,
            error_message=str(exc),
        )
        return JsonResponse(
            {"error": str(exc)},
            status=503,
        )
    except (KeyError, TypeError) as exc:
        error_message = (
            "Priority prediction service returned an invalid response."
        )
        _record_failed_analysis(
            ticket=ticket,
            analysis_type=AIAnalysis.AnalysisType.PRIORITY,
            model_name="priority_prediction_model",
            input_hash=input_hash,
            error_message=error_message,
        )
        return JsonResponse(
            {"error": error_message},
            status=502,
        )
    analysis = AIAnalysis.objects.create(
        ticket=ticket,
        analysis_type=AIAnalysis.AnalysisType.PRIORITY,
        model_name="priority_prediction_model",
        model_version="1.0.0",
        input_hash=input_hash,
        result_json={
            "priority": priority,
            "confidence": confidence,
        },
        confidence_score=confidence,
        status=AIAnalysis.Status.SUCCESS,
    )
    return JsonResponse(
        {
            "ticket_id": ticket.id,
            "priority": priority,
            "confidence": confidence,
            "analysis_id": analysis.id,
        },
        status=200,
    )
def _get_feedback_request_data(request):
    """Extract and validate the JSON body for an AI feedback request."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, JsonResponse(
            {"error": "Request body must contain valid JSON."},
            status=400,
        )
    analysis_id = data.get("analysis_id")
    if not isinstance(analysis_id, int) or isinstance(analysis_id, bool) or analysis_id <= 0:
        return None, JsonResponse(
            {"error": "analysis_id must be a positive integer."},
            status=400,
        )
    feedback_type = data.get("feedback_type")
    valid_feedback_types = {
        AIFeedback.FeedbackType.ACCEPTED,
        AIFeedback.FeedbackType.CORRECTED,
        AIFeedback.FeedbackType.REJECTED,
    }
    if feedback_type not in valid_feedback_types:
        return None, JsonResponse(
            {
                "error": (
                    "feedback_type must be one of: "
                    "ACCEPTED, CORRECTED, REJECTED."
                )
            },
            status=400,
        )
    corrected_prediction = data.get("corrected_prediction")
    if feedback_type == AIFeedback.FeedbackType.CORRECTED:
        if not isinstance(corrected_prediction, dict) or not corrected_prediction:
            return None, JsonResponse(
                {
                    "error": (
                        "corrected_prediction must be a non-empty "
                        "JSON object when feedback_type is CORRECTED."
                    )
                },
                status=400,
            )
    elif corrected_prediction is not None:
        return None, JsonResponse(
            {
                "error": (
                    "corrected_prediction is only allowed when "
                    "feedback_type is CORRECTED."
                )
            },
            status=400,
        )
    feedback_comment = data.get("feedback_comment", "")
    if not isinstance(feedback_comment, str):
        return None, JsonResponse(
            {"error": "feedback_comment must be a string."},
            status=400,
        )
    return {
        "analysis_id": analysis_id,
        "feedback_type": feedback_type,
        "corrected_prediction": corrected_prediction,
        "feedback_comment": feedback_comment.strip(),
    }, None
@csrf_exempt
@require_POST
def review_ai_analysis(request):
    """Record authorized human feedback for an AI analysis."""
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Authentication is required."},
            status=401,
        )
    if not request.user.has_permission("ai.review_analysis"):
        return JsonResponse(
            {"error": "You do not have permission to review AI analyses."},
            status=403,
        )
    data, error_response = _get_feedback_request_data(request)
    if error_response:
        return error_response
    try:
        analysis = AIAnalysis.objects.select_related("ticket").get(
            pk=data["analysis_id"]
        )
    except AIAnalysis.DoesNotExist:
        return JsonResponse(
            {"error": "AI analysis not found."},
            status=404,
        )
    if analysis.status == AIAnalysis.Status.FAILED:
        return JsonResponse(
            {"error": "Failed AI analyses cannot be reviewed."},
            status=400,
        )
    feedback_type = data["feedback_type"]
    is_retraining_eligible = feedback_type in {
        AIFeedback.FeedbackType.ACCEPTED,
        AIFeedback.FeedbackType.CORRECTED,
    }
    retraining_status = (
        AIFeedback.RetrainingStatus.PENDING
        if is_retraining_eligible
        else AIFeedback.RetrainingStatus.EXCLUDED
    )
    feedback = AIFeedback.objects.create(
        analysis=analysis,
        ticket=analysis.ticket,
        feedback_type=feedback_type,
        original_prediction=analysis.result_json,
        corrected_prediction=data["corrected_prediction"],
        feedback_comment=data["feedback_comment"],
        reviewed_by=request.user,
        is_retraining_eligible=is_retraining_eligible,
        retraining_status=retraining_status,
    )
    return JsonResponse(
        {
            "feedback_id": feedback.id,
            "analysis_id": analysis.id,
            "ticket_id": analysis.ticket_id,
            "feedback_type": feedback.feedback_type,
            "original_prediction": feedback.original_prediction,
            "corrected_prediction": feedback.corrected_prediction,
            "reviewed_by": request.user.id,
            "created_at": feedback.created_at.isoformat(),
        },
        status=201,
    )


