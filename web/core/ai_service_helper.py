import json
import requests

from django.conf import settings


class AiServiceHelper:

    @staticmethod
    def call_api(endpoint, request_type="POST", payload=None):
        base_url = settings.AI_SERVICE_URL.rstrip("/")
        endpoint = endpoint.lstrip("/")

        url = f"{base_url}/{endpoint}"

        payload = json.dumps(payload) if payload is not None else None

        headers = {
            "Content-Type": "application/json"
        }

        response = requests.request(
            request_type,
            url,
            headers=headers,
            data=payload,
        )

        return response