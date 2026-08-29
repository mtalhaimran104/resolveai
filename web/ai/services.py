import requests

from django.conf import settings


class AIServiceError(Exception):
    """Raised when the AI service cannot process a request."""


def _post(url: str, payload: dict, timeout: int = 30) -> dict:
    try:
        response = requests.post(
            url,
            json=payload,
            timeout=timeout,
        )

        response.raise_for_status()
        return response.json()

    except requests.RequestException as exc:
        raise AIServiceError(
            "AI service is unavailable."
        ) from exc


def call_classification_service(ticket_id: int, text: str) -> dict:
    return _post(
        f"{settings.AI_SERVICE_URL}/api/v1/classification/predict",
        {
            "ticket_id": ticket_id,
            "text": text,
        },
    )


def call_priority_service(ticket_id: int, text: str) -> dict:
    return _post(
        f"{settings.AI_SERVICE_URL}/api/v1/priority/predict",
        {
            "ticket_id": ticket_id,
            "text": text,
        },
    )


def get_priority_model_metrics() -> dict:
    try:
        response = requests.get(
            f"{settings.AI_SERVICE_URL}/api/v1/priority/metrics",
            timeout=30,
        )

        response.raise_for_status()
        return response.json()

    except requests.RequestException as exc:
        raise AIServiceError(
            "Priority model metrics service is unavailable."
        ) from exc


def call_sentiment_service(ticket_id: int) -> dict:
    """Send ticket ID to the sentiment analysis service."""

    url = f"{settings.AI_SERVICE_URL}/api/v1/sentiment/predict"

    try:
        response = requests.post(
            url,
            json={
                "ticket_id": ticket_id,
            },
            timeout=30,
        )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as exc:
        raise AIServiceError(
            "Sentiment analysis service is unavailable."
        ) from exc


def call_summarization_service(text: str) -> dict:
    return _post(
        f"{settings.AI_SERVICE_URL}/summarization/",
        {
            "text": text,
        },
        timeout=60,
    )


def call_faq_service(question: str) -> dict:
    return _post(
        f"{settings.AI_SERVICE_URL}/faq/",
        {
            "question": question,
        },
    )