from typing import Any, Dict

from app.retrieval.faq_retrieval import retrieve_faq


def get_article_faq(article_title: str, article_content: str) -> Dict[str, Any]:
    """
    Generate/retrieve an FAQ response using an existing Knowledge Base article.

    Existing FAQ retrieval logic is reused without modification.
    """
    query = f"{article_title}\n{article_content}".strip()

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
        "raw_result": result,
    }