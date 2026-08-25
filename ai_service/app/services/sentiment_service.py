from app.models.sentiment_model import analyze_sentiment


def analyze_student_sentiment(text: str):
    """
    Analyze the sentiment of a student's query.

    The actual AI model remains inside sentiment_model.py.
    This service only acts as the bridge between
    the API and the sentiment model.
    """

    text = text.strip()

    if not text:
        return "neutral", 0.0

    sentiment, confidence_score = analyze_sentiment(text)

    return sentiment, confidence_score