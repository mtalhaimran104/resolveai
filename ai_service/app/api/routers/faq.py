# app/api/routers/faq.py

from fastapi import APIRouter

from app.schemas.faq import (
    FAQRequest,
    FAQResponse
)

from app.services.faq_service import (
    find_faq_answer
)


# ============================================================
# FAQ ROUTER
# ============================================================

router = APIRouter(
    prefix="/faq",
    tags=["FAQ"]
)


# ============================================================
# FAQ SEARCH ENDPOINT
# ============================================================

@router.post(
    "/",
    response_model=FAQResponse
)
def faq_search(
    request: FAQRequest
):
    """
    Search the IUB FAQ knowledge base.

    The user's question is passed to the FAQ service,
    which retrieves the most relevant verified answer.
    """

    return find_faq_answer(
        request.question
    )