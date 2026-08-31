from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    path("", views.reports_dashboard, name="dashboard"),
    path("ticket-volume/", views.ticket_volume_report, name="ticket_volume"),
    path("resolution-time/", views.resolution_time_report, name="resolution_time"),
    path("agent-performance/", views.agent_performance_report, name="agent_performance"),
    path("department/", views.department_report, name="department"),
    path("category/", views.category_report, name="category"),
    path("ai-accuracy/", views.ai_accuracy_report, name="ai_accuracy"),

    path(
        "ai-accuracy/low-confidence/",
        views.low_confidence_results,
        name="low_confidence_results",
    ),
    path("customer-satisfaction/", views.customer_satisfaction_report, name="customer_satisfaction"),
]