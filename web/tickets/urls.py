from django.urls import path
from . import views

urlpatterns = [
    # Requester
    path("", views.ticket_list, name="my_tickets"),
    path("create/", views.ticket_create, name="create_ticket"),
    path("<int:pk>/", views.ticket_detail, name="ticket_detail_requester"),
    path("<int:pk>/comment/", views.ticket_add_comment, name="ticket_add_comment"),
    path("<int:pk>/attachment/", views.ticket_add_attachment, name="ticket_add_attachment"),

    # Admin
    path("all/", views.admin_ticket_list, name="admin_ticket_list"),
    path("<int:pk>/status/", views.ticket_update_status, name="ticket_update_status"),

    # Supervisor
    path("supervisor/", views.supervisor_ticket_list, name="supervisor_ticket_list"),
    path("supervisor/unassigned/", views.unassigned_ticket_list, name="unassigned_tickets"),
    path("supervisor/assigned/", views.assigned_ticket_list, name="assigned_tickets"),
    path("<int:pk>/assign/", views.ticket_assign, name="ticket_assign"),

    # Agent
    path("agent/", views.agent_ticket_list, name="agent_ticket_list"),
    path("agent/faqs/", views.agent_faq_list, name="agent_faq_list"),
]