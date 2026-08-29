from app.models.summarization_model import summarize_text


def summarize_student_query(text: str) -> str:
    """
    Summarize a student's query.

    The actual AI model is kept inside summarization_model.py.
    This service acts as the bridge between the API and the model.
    """

    text = text.strip()

    if not text:
        return ""

    return summarize_text(text)