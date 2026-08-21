from app.models.sentiment_model import analyze_sentiment


def analyze_student_sentiment(text: str) -> str:
    """
    Analyze the sentiment of a student's query.

    The actual AI model is kept inside sentiment_model.py.
    This service acts as the bridge between the API and the model.
    """

    text = text.strip()

    if not text:
        return "neutral"

    return analyze_sentiment(text)