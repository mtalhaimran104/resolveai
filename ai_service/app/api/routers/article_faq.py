from fastapi import APIRouter
from pydantic import BaseModel

from app.retrieval.faq_retrieval import retrieve_faq

router = APIRouter(prefix="/article-faq", tags=["Article FAQ"])


class ArticleFAQRequest(BaseModel):
    title: str
    content: str


@router.post("/")
def article_faq(request: ArticleFAQRequest):
    query = f"{request.title}\n{request.content}".strip()

    result = retrieve_faq(query)

    if not result:
        return {
            "found": False,
            "answer": None,
            "confidence": None,
            "source": None,
        }

    return {
        "found": result.get("found", False),
        "answer": result.get("answer"),
        "confidence": result.get("confidence"),
        "source": result.get("source"),
    }