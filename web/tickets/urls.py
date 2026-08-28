from django.urls import path
from . import views

app_name = "tickets"


urlpatterns = [

    # ============================================================
    # REQUESTER
    # ============================================================

    path(
        "",
        views.ticket_list,
        name="my_tickets",
    ),

    path(
        "create/",
        views.ticket_create,
        name="ticket_create",
    ),

    path(
        "<int:pk>/",
        views.ticket_detail,
        name="ticket_detail",
    ),

    path(
        "<int:pk>/history/",
        views.ticket_history,
        name="ticket_history",
    ),

    path(
        "<int:pk>/comment/",
        views.ticket_add_comment,
        name="ticket_add_comment",
    ),

    path(
        "<int:pk>/attachment/",
        views.ticket_add_attachment,
        name="ticket_add_attachment",
    ),


    # ============================================================
    # ADMIN
    # ============================================================

    path(
        "admin/",
        views.admin_ticket_list,
        name="admin_ticket_list",
    ),

    path(
        "<int:pk>/status/",
        views.ticket_update_status,
        name="ticket_update_status",
    ),

    path(
        "<int:pk>/priority/",
        views.ticket_update_priority,
        name="ticket_update_priority",
    ),

    path(
        "<int:pk>/category/",
        views.ticket_update_category,
        name="ticket_update_category",
    ),

    path(
        "<int:pk>/resolve/",
        views.ticket_resolve,
        name="ticket_resolve",
    ),


    # ============================================================
    # SUPERVISOR
    # ============================================================

    path(
        "supervisor/",
        views.supervisor_ticket_list,
        name="supervisor_ticket_list",
    ),

    path(
        "supervisor/unassigned/",
        views.unassigned_ticket_list,
        name="unassigned_tickets",
    ),

    path(
        "supervisor/assigned/",
        views.assigned_ticket_list,
        name="assigned_tickets",
    ),

    path(
        "<int:pk>/assign/",
        views.ticket_assign,
        name="ticket_assign",
    ),

    path(
        "<int:pk>/unassign/",
        views.ticket_unassign,
        name="ticket_unassign",
    ),


    # ============================================================
    # AGENT
    # ============================================================

    path(
        "agent/",
        views.agent_ticket_list,
        name="agent_ticket_list",
    ),

    path(
        "agent/unassigned/",
        views.unassigned_ticket_list,
        name="agent_unassigned_tickets",
    ),

    path(
        "agent/assigned/",
        views.assigned_ticket_list,
        name="agent_assigned_tickets",
    ),

    path(
        "agent/faqs/",
        views.agent_faq_list,
        name="agent_faq_list",
    ),


    # ============================================================
    # SHARED QUEUES
    # ============================================================

    path(
        "department-queue/",
        views.department_queue_list,
        name="department_queue",
    ),

    path(
        "critical/",
        views.critical_ticket_list,
        name="critical_tickets",
    ),

    path(
        "waiting-for-user/",
        views.waiting_for_user_list,
        name="waiting_for_user_tickets",
    ),

    path(
        "resolved/",
        views.resolved_ticket_list,
        name="resolved_tickets",
    ),
]