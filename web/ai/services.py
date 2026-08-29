import requests
from django.conf import settings
class AIServiceError(Exception):
    """Raised when the AI service cannot process a request."""
def call_classification_service(ticket_id: int, text: str) -> dict:
    """Send ticket text to the classification model service."""
    url = f"{settings.AI_SERVICE_URL}/api/v1/classification/predict"
    try:
        response = requests.post(
            url,
            json={
                "ticket_id": ticket_id,
                "text": text,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise AIServiceError(
            "Classification service is unavailable."
        ) from exc
def call_priority_service(ticket_id: int, text: str) -> dict:
    """Send ticket text to the priority prediction model service."""
    url = f"{settings.AI_SERVICE_URL}/api/v1/priority/predict"
    try:
        response = requests.post(
            url,
            json={
                "ticket_id": ticket_id,
                "text": text,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise AIServiceError(
            "Priority prediction service is unavailable."
        ) from exc
def get_priority_model_metrics() -> dict:
    """Get priority model performance metrics from the AI service."""
    url = f"{settings.AI_SERVICE_URL}/api/v1/priority/metrics"
    try:
        response = requests.get(
            url,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise AIServiceError(
            "Priority model metrics service is unavailable."
        ) from exc
