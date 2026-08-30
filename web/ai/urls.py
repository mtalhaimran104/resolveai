from django.urls import path
from . import views


app_name = "ai"


urlpatterns = [
    path(
        "classification/",
        views.classify_ticket,
        name="classify_ticket",
    ),
    path(
        "priority/",
        views.predict_ticket_priority,
        name="predict_ticket_priority",
    ),

    # Sentiment
    path(
        "sentiment/",
        views.analyze_ticket_sentiment,
        name="analyze_ticket_sentiment",
    ),

    # Summarization
    path(
        "summary/",
        views.summarize_ticket,
        name="summarize_ticket",
    ),

    # FAQ
    path(
        "faq/",
        views.answer_ticket_faq,
        name="answer_ticket_faq",
    ),

    # Feedback
    path(
        "feedback/",
        views.review_ai_analysis,
        name="review_ai_analysis",
    ),
]