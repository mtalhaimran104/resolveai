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
]
