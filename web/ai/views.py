from time import perf_counter
import hashlib
import json
import time

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from tickets.models import Ticket
from .models import AIAnalysis, AIFeedback
from .services import (
AIServiceError,
    call_classification_service,
    call_priority_service,
    call_sentiment_service,
    call_summarization_service,
    call_faq_service,
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
        start_time = perf_counter()
        result = call_classification_service(
            ticket_id=ticket.id,
            text=text,
        )
        response_time_ms = (perf_counter() - start_time) * 1000
        result_data = result["data"]
        category = result_data["category_title"]
        confidence = result_data["confidence"]
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
        response_time_ms=response_time_ms,
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
        result_data = result["data"]
        priority = result_data["priority"]
        confidence = result_data["confidence"]
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


@csrf_exempt
@require_POST
def analyze_ticket_sentiment(request):
    """Run real-time sentiment analysis and store the result."""

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

    start_time = time.perf_counter()

    try:
        result = call_sentiment_service(ticket_id=ticket.id)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        data = result["data"]

        sentiment = data["sentiment"]
        confidence = data["confidence_score"]
        model_version = data.get("model_version", "unknown")

    except AIServiceError as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        _record_failed_analysis(
            ticket=ticket,
            analysis_type=AIAnalysis.AnalysisType.SENTIMENT,
            model_name="sentiment_analysis_model",
            input_hash=input_hash,
            error_message=str(exc),
        )

        return JsonResponse(
            {"error": str(exc)},
            status=503,
        )

    except (KeyError, TypeError):
        return JsonResponse(
            {"error": "Sentiment service returned an invalid response."},
            status=502,
        )

    analysis = AIAnalysis.objects.create(
        ticket=ticket,
        analysis_type=AIAnalysis.AnalysisType.SENTIMENT,
        model_name="sentiment_analysis_model",
        model_version=model_version,
        input_hash=input_hash,
        result_json={
            "sentiment": sentiment,
            "confidence_score": confidence,
        },
        confidence_score=confidence,
        response_time_ms=elapsed_ms,
        status=AIAnalysis.Status.SUCCESS,
    )

    return JsonResponse(
        {
            "ticket_id": ticket.id,
            "sentiment": sentiment,
            "confidence_score": confidence,
            "model_version": model_version,
            "response_time_ms": round(elapsed_ms, 2),
            "analysis_id": analysis.id,
        }
    )


@csrf_exempt
@require_POST
def summarize_ticket(request):
    """Generate a real-time ticket summary and store the result."""

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

    start_time = time.perf_counter()

    try:
        result = call_summarization_service(text)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        summary = result["summary"]
        model_version = result.get("model_version", "unknown")
        confidence = result.get("confidence_score")

    except AIServiceError as exc:
        _record_failed_analysis(
            ticket=ticket,
            analysis_type=AIAnalysis.AnalysisType.SUMMARY,
            model_name="summarization_model",
            input_hash=input_hash,
            error_message=str(exc),
        )

        return JsonResponse(
            {"error": str(exc)},
            status=503,
        )

    except (KeyError, TypeError):
        return JsonResponse(
            {"error": "Summarization service returned an invalid response."},
            status=502,
        )

    analysis = AIAnalysis.objects.create(
        ticket=ticket,
        analysis_type=AIAnalysis.AnalysisType.SUMMARY,
        model_name="summarization_model",
        model_version=model_version,
        input_hash=input_hash,
        result_json={
            "summary": summary,
        },
        confidence_score=confidence,
        response_time_ms=elapsed_ms,
        status=AIAnalysis.Status.SUCCESS,
    )

    return JsonResponse(
        {
            "ticket_id": ticket.id,
            "summary": summary,
            "model_version": model_version,
            "confidence_score": confidence,
            "response_time_ms": round(elapsed_ms, 2),
            "analysis_id": analysis.id,
        }
    )


@csrf_exempt
@require_POST
def answer_ticket_faq(request):
    """Run real-time FAQ retrieval and store the result."""

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

    question = _build_ticket_text(ticket)
    input_hash = _create_input_hash(question)

    start_time = time.perf_counter()

    try:
        result = call_faq_service(question)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        answer = result["answer"]
        similarity_score = result.get("similarity_score")
        confidence_level = result.get("confidence_level")
        source = result.get("source")
        found = result.get("found")

    except AIServiceError as exc:
        _record_failed_analysis(
            ticket=ticket,
            analysis_type=AIAnalysis.AnalysisType.FAQ,
            model_name="faq_retrieval_model",
            input_hash=input_hash,
            error_message=str(exc),
        )

        return JsonResponse(
            {"error": str(exc)},
            status=503,
        )

    except (KeyError, TypeError):
        return JsonResponse(
            {"error": "FAQ service returned an invalid response."},
            status=502,
        )

    analysis = AIAnalysis.objects.create(
        ticket=ticket,
        analysis_type=AIAnalysis.AnalysisType.FAQ,
        model_name="faq_retrieval_model",
        model_version="v1",
        input_hash=input_hash,
        result_json={
            "answer": answer,
            "similarity_score": similarity_score,
            "confidence_level": confidence_level,
            "source": source,
            "found": found,
        },
        confidence_score=similarity_score,
        response_time_ms=elapsed_ms,
        status=AIAnalysis.Status.SUCCESS,
    )

    return JsonResponse(
        {
            "ticket_id": ticket.id,
            "answer": answer,
            "similarity_score": similarity_score,
            "confidence_level": confidence_level,
            "source": source,
            "found": found,
            "model_version": "v1",
            "response_time_ms": round(elapsed_ms, 2),
            "analysis_id": analysis.id,
        }
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
    corrected_prediction = data["corrected_prediction"]

    if feedback_type == AIFeedback.FeedbackType.CORRECTED:
        if analysis.analysis_type == AIAnalysis.AnalysisType.CLASSIFICATION:
            category_id = corrected_prediction.get("category_id")
            if (
                not isinstance(category_id, int)
                or isinstance(category_id, bool)
                or category_id <= 0
            ):
                return JsonResponse(
                    {
                        "error": (
                            "Classification corrections must contain "
                            "a positive integer category_id."
                        )
                    },
                    status=400,
                )
        elif analysis.analysis_type == AIAnalysis.AnalysisType.PRIORITY:
            priority = corrected_prediction.get("priority")
            valid_priorities = {
                "LOW",
                "MEDIUM",
                "HIGH",
                "CRITICAL",
            }
            if priority not in valid_priorities:
                return JsonResponse(
                    {
                        "error": (
                            "Priority corrections must contain one of: "
                            "LOW, MEDIUM, HIGH, CRITICAL."
                        )
                    },
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