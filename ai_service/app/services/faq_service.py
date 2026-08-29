from app.retrieval.faq_retrieval import retrieve_faq


# ============================================================
# IUB CONTACT INFORMATION
# ============================================================

IUB_CONTACT = (
    "\n\n"
    "**IUB Information Center/Helpline:** "
    "**0346-9255555, 0347-9255555, 062-9255580**\n"
    "**Email:** **iubhelpline@iub.edu.pk**\n"
    "**Location:** **Basement of Sir Sadiq Muhammad Khan "
    "Library, Baghdad ul Jadeed Campus, Bahawalpur**\n"
    "**Official Website:** **https://www.iub.edu.pk/**"
)


# ============================================================
# MODEL INFORMATION
# ============================================================

MODEL_NAME = "resolveai-faq-retriever"
MODEL_VERSION = "v1"


# ============================================================
# EMPTY QUERY
# ============================================================

def _empty_response(query: str = "") -> dict:

    return {
        "found": False,
        "question": query,
        "answer": (
            "Please enter a valid IUB-related question."
        ),
        "similarity_score": 0.0,
        "confidence_score": 0.0,
        "confidence_level": "Low",
        "source": "empty_query",
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
    }


# ============================================================
# MAIN FAQ SERVICE
# ============================================================

def find_faq_answer(query: str) -> dict:
    """
    Application-facing FAQ service.

    Flow:

        User Question
             |
             v
        Validate Query
             |
             v
        retrieve_faq()
             |
             +---- Reliable Match ----> Return Answer
             |
             +---- No Match ----------> Safe Fallback
    """

    # --------------------------------------------------------
    # Validate None
    # --------------------------------------------------------

    if query is None:
        return _empty_response("")

    # --------------------------------------------------------
    # Convert input to string
    # --------------------------------------------------------

    if not isinstance(query, str):
        query = str(query)

    query = query.strip()

    # --------------------------------------------------------
    # Empty query
    # --------------------------------------------------------

    if not query:
        return _empty_response(query)

    # --------------------------------------------------------
    # Retrieve FAQ
    # --------------------------------------------------------

    try:
        result = retrieve_faq(query)

    except Exception as exc:

        print(
            f"[FAQ SERVICE] Retrieval error: {exc}"
        )

        return {
            "found": False,
            "question": query,
            "answer": (
                "I could not access the IUB FAQ knowledge "
                "base at the moment.\n\n"
                "Please try again shortly or contact the "
                "**IUB Information Center/Helpline**."
                + IUB_CONTACT
            ),
            "similarity_score": 0.0,
            "confidence_score": 0.0,
            "confidence_level": "Low",
            "source": "retrieval_error",
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
        }

    # --------------------------------------------------------
    # Validate retrieval result
    # --------------------------------------------------------

    if not isinstance(result, dict):

        return {
            "found": False,
            "question": query,
            "answer": (
                "I could not process your question against "
                "the current IUB FAQ knowledge base.\n\n"
                "Please try asking your question again or "
                "contact the **IUB Information Center/Helpline**."
                + IUB_CONTACT
            ),
            "similarity_score": 0.0,
            "confidence_score": 0.0,
            "confidence_level": "Low",
            "source": "invalid_retrieval_result",
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
        }

    # --------------------------------------------------------
    # Successful FAQ match
    # --------------------------------------------------------

    if result.get("found") is True:

        return {
            "found": True,

            "question": result.get(
                "question",
                query,
            ),

            "answer": result.get(
                "answer",
                "",
            ),

            "similarity_score": round(
                float(
                    result.get(
                        "similarity_score",
                        0.0,
                    )
                ),
                4,
            ),

            "confidence_score": round(
                float(
                    result.get(
                        "confidence_score",
                        0.0,
                    )
                ),
                4,
            ),

            "confidence_level": result.get(
                "confidence_level",
                "Low",
            ),

            "source": result.get(
                "source",
                "iub_verified_knowledge",
            ),

            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
        }

    # --------------------------------------------------------
    # No reliable FAQ match
    # --------------------------------------------------------

    return {
        "found": False,

        "question": query,

        "answer": (
            "I could not find a sufficiently relevant "
            "answer for this question in the available "
            "IUB FAQ knowledge base.\n\n"
            "I do not want to guess or provide incorrect "
            "university information.\n\n"
            "Please try asking about **IUB admissions, "
            "programs, courses, fees, scholarships, "
            "examinations, student portal, registration, "
            "LMS, university email, library, departments, "
            "offices or other student services**."
            + IUB_CONTACT
        ),

        "similarity_score": round(
            float(
                result.get(
                    "similarity_score",
                    0.0,
                )
            ),
            4,
        ),

        "confidence_score": round(
            float(
                result.get(
                    "confidence_score",
                    0.0,
                )
            ),
            4,
        ),

        "confidence_level": result.get(
            "confidence_level",
            "Low",
        ),

        "source": result.get(
            "source",
            "faq_not_found",
        ),

        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
    }


# ============================================================
# FAQ MODEL RELOAD
# ============================================================

def reload_faq_model():

    from app.retrieval.faq_retrieval import (
        reload_faq_model as reload_retrieval_model
    )

    try:

        reload_retrieval_model()

        return {
            "success": True,
            "message": (
                "IUB FAQ knowledge base reloaded successfully."
            )
        }

    except Exception as exc:

        print(
            f"[FAQ SERVICE] Reload error: {exc}"
        )

        return {
            "success": False,
            "message": (
                "Failed to reload the IUB FAQ knowledge base."
            )
        }