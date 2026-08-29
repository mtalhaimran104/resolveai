from datetime import timedelta
from pathlib import Path
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Avg
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.db.models import Count
User = get_user_model()
from accounts.decorators import admin_required
from tickets.models import Ticket, TicketHistory
from ai.models import AIAnalysis
from ai.services import get_priority_model_metrics, AIServiceError


# ---------------------------------------------------------------------
# DASHBOARD
#
# This used to always render dashboard/index.html with hardcoded mock
# data regardless of who was logged in, even though role-specific
# templates (index-agent/-requester/-supervisor.html) already existed
# unused. It now picks the right template per role and fills it with
# real data from the Ticket/TicketHistory tables.
# ---------------------------------------------------------------------

@login_required
def dashboard(request):
    user = request.user

    # Admin gets Admin dashboard
    if user.is_admin:
        return _admin_dashboard(request)

    # Supervisor gets Supervisor dashboard
    if user.has_role("SUPERVISOR"):
        return _supervisor_dashboard(request)

    # Agent gets Agent dashboard
    if user.has_role("AGENT"):
        return _agent_dashboard(request)

    # Everyone else gets Requester dashboard
    return _requester_dashboard(request)


def _admin_dashboard(request):
    tickets = Ticket.objects.select_related(
        "requester",
        "assigned_to",
        "department",
        "category",
    ).all()

    total = tickets.count()

    # ---------------------------------------------------------------
    # DEMO DASHBOARD CHART DATA
    # ---------------------------------------------------------------

    # User Growth
    user_growth_labels = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"
    ]

    user_growth_data = [
        42, 58, 76, 103, 141, 188, 235
    ]

    # Ticket Trend
    ticket_trend_labels = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"
    ]

    ticket_trend_data = [
        24, 31, 45, 39, 57, 68, 82
    ]

    # Tickets by Department
    department_labels = [
        "IT Support",
        "Finance",
        "Examination",
        "General",
    ]

    department_ticket_data = [
        82, 64, 78, 55
    ]

    # ---------------------------------------------------------------
    # EXISTING TICKET STATISTICS
    # ---------------------------------------------------------------

    def pct(count):
        return round((count / total) * 100) if total else 0

    status_counts = {
        code: tickets.filter(status=code).count()
        for code, _ in Ticket.Status.choices
    }

    status_colors = {
        Ticket.Status.OPEN: "primary",
        Ticket.Status.IN_PROGRESS: "info",
        Ticket.Status.WAITING_FOR_USER: "warning",
        Ticket.Status.RESOLVED: "success",
        Ticket.Status.CLOSED: "secondary",
    }

    status_summary = [
        {
            "label": label,
            "count": status_counts[code],
            "percent": pct(status_counts[code]),
            "color": status_colors[code],
        }
        for code, label in Ticket.Status.choices
    ]

    resolved_today = tickets.filter(
        status=Ticket.Status.RESOLVED,
        updated_at__date=timezone.now().date(),
    ).count()

    summary_cards = [
        {
            "label": "Open Tickets",
            "value": status_counts[Ticket.Status.OPEN],
            "icon": "bi-envelope-open-fill",
            "color": "primary",
        },
        {
            "label": "In Progress",
            "value": status_counts[Ticket.Status.IN_PROGRESS],
            "icon": "bi-arrow-repeat",
            "color": "info",
        },
        {
            "label": "Waiting for User",
            "value": status_counts[Ticket.Status.WAITING_FOR_USER],
            "icon": "bi-hourglass-split",
            "color": "warning",
        },
        {
            "label": "Resolved Today",
            "value": resolved_today,
            "icon": "bi-check-circle-fill",
            "color": "success",
        },
    ]

    recent_tickets = [
        {
            "number": t.ticket_number,
            "subject": t.subject,
            "requester": (
                t.requester.get_full_name()
                or t.requester.username
            ),
            "priority": t.get_priority_display(),
            "status": t.get_status_display(),
            "status_class": t.status.lower().replace("_", "-"),
            "assigned_to": (
                t.assigned_to.get_full_name()
                or t.assigned_to.username
            ) if t.assigned_to else "Unassigned",
            "updated": t.updated_at,
        }
        for t in tickets.order_by("-updated_at")[:8]
        
    ]
    activities = (
    TicketHistory.objects
    .select_related("ticket", "actor")
    .order_by("-created_at")[:10]
)
    return render(request, "dashboard/index.html", {
        "page_title": "Dashboard",
        
        "summary_cards": summary_cards,
        "recent_tickets": recent_tickets,
        "status_summary": status_summary,

        # Stat cards
        "total_users": User.objects.count(),
        "active_agents": 18,
        "total_tickets": total,
        "open_tickets": 82,
        "knowledge_articles": 64,
        "ai_status": "Operational",
        "ai_status_class": "up",

        # User Growth chart
        "user_growth_labels": user_growth_labels,
        "user_growth_data": user_growth_data,

        # Ticket Trend chart
        "ticket_trend_labels": ticket_trend_labels,
        "ticket_trend_data": ticket_trend_data,

        # Department donut chart
        "department_labels": department_labels,
        "department_ticket_data": department_ticket_data,

        # Timeline
        "activities": activities,
    })
    # return render(request, "dashboard/index.html", {
    #     "page_title": "Dashboard",
    #     "summary_cards": summary_cards,
    #     "recent_tickets": recent_tickets,
    #     "status_summary": status_summary,
    # })


def _supervisor_dashboard(request):
    tickets = Ticket.objects.select_related("requester", "assigned_to", "department", "category")
    unassigned = tickets.filter(assigned_to__isnull=True).order_by("-created_at")

    resolved_today = tickets.filter(
        status=Ticket.Status.RESOLVED,
        updated_at__date=timezone.now().date(),
    ).count()

    recent_history = (
        TicketHistory.objects.select_related("ticket", "actor")
        .order_by("-created_at")[:8]
    )

    return render(request, "dashboard/index-supervisor.html", {
        "page_title": "Dashboard",
        "welcome_name": request.user.get_full_name() or request.user.username,
        "unassigned_count": unassigned.count(),
        "assigned_count": tickets.filter(assigned_to__isnull=False).count(),
        "critical_count": tickets.filter(priority=Ticket.Priority.CRITICAL).exclude(
            status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]
        ).count(),
        "resolved_today": resolved_today,
        "unassigned_tickets": unassigned[:8],
        "recent_history": recent_history,
    })


def _agent_dashboard(request):
    user = request.user
    my_tickets = Ticket.objects.select_related("requester", "department", "category") \
        .filter(assigned_to=user)

    open_tickets = Ticket.objects.exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED])

    priority_counts = {
        code: my_tickets.filter(priority=code).count() for code, _ in Ticket.Priority.choices
    }

    category_qs = (
        my_tickets.values("category__name")
        .order_by("category__name")
    )
    category_totals = {}
    for row in category_qs:
        name = row["category__name"] or "Uncategorized"
        category_totals[name] = category_totals.get(name, 0) + 1

    recent_activity = (
        TicketHistory.objects.select_related("ticket")
        .filter(ticket__assigned_to=user)
        .order_by("-created_at")[:8]
    )

    return render(request, "dashboard/index-agent.html", {
        "page_title": "Dashboard",
        "welcome_name": user.get_full_name() or user.username,
        "assigned_to_me_count": my_tickets.count(),
        "open_count": my_tickets.filter(status=Ticket.Status.OPEN).count(),
        "critical_count": my_tickets.filter(priority=Ticket.Priority.CRITICAL).count(),
        "waiting_count": my_tickets.filter(status=Ticket.Status.WAITING_FOR_USER).count(),
        "my_tickets": my_tickets.order_by("-updated_at")[:8],
        "recent_activity": recent_activity,
        "priority_labels": [label for _, label in Ticket.Priority.choices],
        "priority_values": [priority_counts[code] for code, _ in Ticket.Priority.choices],
        "category_labels": list(category_totals.keys()),
        "category_values": list(category_totals.values()),
    })


def _requester_dashboard(request):
    user = request.user
    my_tickets = Ticket.objects.select_related("assigned_to", "department", "category") \
        .filter(requester=user)

    return render(request, "dashboard/index-requester.html", {
        "page_title": "Dashboard",
        "welcome_name": user.get_full_name() or user.username,
        "open_count": my_tickets.exclude(
            status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]
        ).count(),
        "resolved_count": my_tickets.filter(
            status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]
        ).count(),
        "recent_tickets": my_tickets.order_by("-updated_at")[:8],
    })


# ---------------------------------------------------------------------
# SYSTEM / SETTINGS placeholder pages
#
# The sidebar (templates/includes/sidebar.html) already links to all of
# these for admins, but none of them had a view or url — visiting any
# page as an admin raised NoReverseMatch when the sidebar tried to
# render those links. There's no Notification/AuditLog/SystemSetting
# model yet, so these render the existing static templates; wire real
# data in once those models/phases exist. Activity Log already has a
# real model to back it (TicketHistory), so it does.
# ---------------------------------------------------------------------

@admin_required
def notifications(request):
    return render(request, "notifications/list.html", {
        "page_title": "Notifications",
        "notifications": [],
    })


@admin_required
def notification_settings(request):
    return render(request, "notifications/list.html", {
        "page_title": "Notification Settings",
        "notifications": [],
    })


@admin_required
def general_settings(request):
    return render(request, "settings/general-settings.html", {"page_title": "General Settings"})


@admin_required
def email_settings(request):
    return render(request, "settings/email-settings.html", {"page_title": "Email Settings"})


@admin_required
def security_settings(request):
    return render(request, "settings/security-settings.html", {"page_title": "Security Settings"})


@admin_required
def ticket_settings(request):
    return render(request, "settings/ticket-settings.html", {"page_title": "Ticket Settings"})


@admin_required
def system_health(request):
    return render(request, "settings/system-health.html", {"page_title": "System Health"})


@admin_required
def activity_log(request):
    history = (
        TicketHistory.objects.select_related("ticket", "actor")
        .order_by("-created_at")[:200]
    )
    return render(request, "audit/activity-log.html", {
        "page_title": "Audit / Activity Log",
        "history": history,
    })


# ---------------------------------------------------------------------
# DEMO KNOWLEDGE BASE / AI PAGES
#
# These AI pages are copied from the supplied ResolveAI HTML template demo
# unchanged. They are exposed only to Admin and Agent sidebars.
# The Knowledge Base pages that used to live here have real CRUD now —
# see the `knowledge` app.
# ---------------------------------------------------------------------

def _demo_page(request, template_name):
    if not (request.user.is_superuser or request.user.is_admin or request.user.has_role_agent):
        return HttpResponseForbidden("You do not have permission to view this page.")
    return render(request, template_name)


def demo_ai_overview(request):
    return _demo_page(request, "ai/ai-overview.html")


def demo_ai_analysis_list(request):
    return _demo_page(request, "ai/ai-analysis-list.html")


def demo_ai_analysis_detail(request):
    return _demo_page(request, "ai/ai-analysis-detail.html")


def demo_ai_suggestions(request):
    return _demo_page(request, "ai/ai-suggestions.html")


def demo_ai_low_confidence(request):
    return _demo_page(request, "ai/low-confidence-results.html")


def demo_ai_model_performance(request):
    try:
        metrics_response = get_priority_model_metrics()
        if metrics_response.get("status"):
            priority_model = metrics_response.get("data", {})
        else:
            priority_model = {}
    except AIServiceError:
        priority_model = {}
    priority_analyses = AIAnalysis.objects.filter(
        analysis_type=AIAnalysis.AnalysisType.PRIORITY,
        status=AIAnalysis.Status.SUCCESS,
    )
    priority_total_predictions = priority_analyses.count()
    priority_avg_response_time = priority_analyses.aggregate(
        average=Avg("response_time_ms")
    )["average"]
    return render(
        request,
        "ai/model-performance.html",
        {
            "priority_model": priority_model,
            "priority_total_predictions": priority_total_predictions,
            "priority_avg_response_time": priority_avg_response_time,
        },
    )

def demo_ai_service_status(request):
    return _demo_page(request, "ai/ai-service-status.html")




# from datetime import timedelta

# from django.contrib.auth.decorators import login_required
# from django.shortcuts import render
from django.db.models import Avg
# from django.http import HttpResponseForbidden
# from django.utils import timezone

# from accounts.decorators import admin_required
# from tickets.models import Ticket, TicketHistory
from ai.models import AIAnalysis
from ai.services import get_priority_model_metrics, AIServiceError
# from core.pagination import paginate_queryset


# # ---------------------------------------------------------------------
# # DASHBOARD
# #
# # This used to always render dashboard/index.html with hardcoded mock
# # data regardless of who was logged in, even though role-specific
# # templates (index-agent/-requester/-supervisor.html) already existed
# # unused. It now picks the right template per role and fills it with
# # real data from the Ticket/TicketHistory tables.
# # ---------------------------------------------------------------------

# @login_required
# def dashboard(request):
#     user = request.user

#     if user.is_admin:
#         return _admin_dashboard(request)
#     if user.has_role_supervisor:
#         return _supervisor_dashboard(request)
#     if user.has_role_agent:
#         return _agent_dashboard(request)
#     return _requester_dashboard(request)


# def _admin_dashboard(request):
#     tickets = Ticket.objects.select_related("requester", "assigned_to").all()
#     total = tickets.count()

#     def pct(count):
#         return round((count / total) * 100) if total else 0

#     status_counts = {
#         code: tickets.filter(status=code).count() for code, _ in Ticket.Status.choices
#     }
#     status_colors = {
#         Ticket.Status.OPEN: "primary",
#         Ticket.Status.IN_PROGRESS: "info",
#         Ticket.Status.WAITING_FOR_USER: "warning",
#         Ticket.Status.RESOLVED: "success",
#         Ticket.Status.CLOSED: "secondary",
#     }
#     status_summary = [
#         {
#             "label": label,
#             "count": status_counts[code],
#             "percent": pct(status_counts[code]),
#             "color": status_colors[code],
#         }
#         for code, label in Ticket.Status.choices
#     ]

#     resolved_today = tickets.filter(
#         status=Ticket.Status.RESOLVED,
#         updated_at__date=timezone.now().date(),
#     ).count()

#     summary_cards = [
#         {"label": "Open Tickets", "value": status_counts[Ticket.Status.OPEN],
#          "icon": "bi-envelope-open-fill", "color": "primary"},
#         {"label": "In Progress", "value": status_counts[Ticket.Status.IN_PROGRESS],
#          "icon": "bi-arrow-repeat", "color": "info"},
#         {"label": "Waiting for User", "value": status_counts[Ticket.Status.WAITING_FOR_USER],
#          "icon": "bi-hourglass-split", "color": "warning"},
#         {"label": "Resolved Today", "value": resolved_today,
#          "icon": "bi-check-circle-fill", "color": "success"},
#     ]

#     recent_tickets = [
#         {
#             "number": t.ticket_number,
#             "subject": t.subject,
#             "requester": t.requester.get_full_name() or t.requester.username,
#             "priority": t.get_priority_display(),
#             "status": t.get_status_display(),
#             "status_class": t.status.lower().replace("_", "-"),
#             "assigned_to": (t.assigned_to.get_full_name() or t.assigned_to.username) if t.assigned_to else "Unassigned",
#             "updated": t.updated_at,
#         }
#         for t in tickets.order_by("-updated_at")[:8]
#     ]

#     return render(request, "dashboard/index.html", {
#         "page_title": "Dashboard",
#         "summary_cards": summary_cards,
#         "recent_tickets": recent_tickets,
#         "status_summary": status_summary,
#     })


# def _supervisor_dashboard(request):
#     tickets = Ticket.objects.select_related("requester", "assigned_to", "department", "category")
#     unassigned = tickets.filter(assigned_to__isnull=True).order_by("-created_at")

#     resolved_today = tickets.filter(
#         status=Ticket.Status.RESOLVED,
#         updated_at__date=timezone.now().date(),
#     ).count()

#     recent_history = (
#         TicketHistory.objects.select_related("ticket", "actor")
#         .order_by("-created_at")[:8]
#     )

#     return render(request, "dashboard/index-supervisor.html", {
#         "page_title": "Dashboard",
#         "welcome_name": request.user.get_full_name() or request.user.username,
#         "unassigned_count": unassigned.count(),
#         "assigned_count": tickets.filter(assigned_to__isnull=False).count(),
#         "critical_count": tickets.filter(priority=Ticket.Priority.CRITICAL).exclude(
#             status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]
#         ).count(),
#         "resolved_today": resolved_today,
#         "unassigned_tickets": unassigned[:8],
#         "recent_history": recent_history,
#     })


# def _agent_dashboard(request):
#     user = request.user
#     my_tickets = Ticket.objects.select_related("requester", "department", "category") \
#         .filter(assigned_to=user)

#     open_tickets = Ticket.objects.exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED])

#     priority_counts = {
#         code: my_tickets.filter(priority=code).count() for code, _ in Ticket.Priority.choices
#     }

#     category_qs = (
#         my_tickets.values("category__name")
#         .order_by("category__name")
#     )
#     category_totals = {}
#     for row in category_qs:
#         name = row["category__name"] or "Uncategorized"
#         category_totals[name] = category_totals.get(name, 0) + 1

#     recent_activity = (
#         TicketHistory.objects.select_related("ticket")
#         .filter(ticket__assigned_to=user)
#         .order_by("-created_at")[:8]
#     )

#     return render(request, "dashboard/index-agent.html", {
#         "page_title": "Dashboard",
#         "welcome_name": user.get_full_name() or user.username,
#         "assigned_to_me_count": my_tickets.count(),
#         "open_count": my_tickets.filter(status=Ticket.Status.OPEN).count(),
#         "critical_count": my_tickets.filter(priority=Ticket.Priority.CRITICAL).count(),
#         "waiting_count": my_tickets.filter(status=Ticket.Status.WAITING_FOR_USER).count(),
#         "my_tickets": my_tickets.order_by("-updated_at")[:8],
#         "recent_activity": recent_activity,
#         "priority_labels": [label for _, label in Ticket.Priority.choices],
#         "priority_values": [priority_counts[code] for code, _ in Ticket.Priority.choices],
#         "category_labels": list(category_totals.keys()),
#         "category_values": list(category_totals.values()),
#     })


# def _requester_dashboard(request):
#     user = request.user
#     my_tickets = Ticket.objects.select_related("assigned_to", "department", "category") \
#         .filter(requester=user)

#     return render(request, "dashboard/index-requester.html", {
#         "page_title": "Dashboard",
#         "welcome_name": user.get_full_name() or user.username,
#         "open_count": my_tickets.exclude(
#             status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]
#         ).count(),
#         "resolved_count": my_tickets.filter(
#             status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]
#         ).count(),
#         "recent_tickets": my_tickets.order_by("-updated_at")[:8],
#     })


# # ---------------------------------------------------------------------
# # SYSTEM / SETTINGS placeholder pages
# #
# # The sidebar (templates/includes/sidebar.html) already links to all of
# # these for admins, but none of them had a view or url — visiting any
# # page as an admin raised NoReverseMatch when the sidebar tried to
# # render those links. There's no Notification/AuditLog/SystemSetting
# # model yet, so these render the existing static templates; wire real
# # data in once those models/phases exist. Activity Log already has a
# # real model to back it (TicketHistory), so it does.
# # ---------------------------------------------------------------------

# @admin_required
# def notifications(request):
#     return render(request, "notifications/list.html", {
#         "page_title": "Notifications",
#         "notifications": [],
#     })


# @admin_required
# def notification_settings(request):
#     return render(request, "notifications/list.html", {
#         "page_title": "Notification Settings",
#         "notifications": [],
#     })


# @admin_required
# def general_settings(request):
#     return render(request, "settings/general-settings.html", {"page_title": "General Settings"})


# @admin_required
# def email_settings(request):
#     return render(request, "settings/email-settings.html", {"page_title": "Email Settings"})


# @admin_required
# def security_settings(request):
#     return render(request, "settings/security-settings.html", {"page_title": "Security Settings"})


# @admin_required
# def ticket_settings(request):
#     return render(request, "settings/ticket-settings.html", {"page_title": "Ticket Settings"})


# @admin_required
# def system_health(request):
#     return render(request, "settings/system-health.html", {"page_title": "System Health"})


# @admin_required
# def activity_log(request):
#     history = TicketHistory.objects.select_related("ticket", "actor").order_by("-created_at")
#     page_obj = paginate_queryset(history, request)
#     return render(request, "audit/activity-log.html", {
#         "page_title": "Audit / Activity Log",
#         "history": page_obj,
#         "page_obj": page_obj,
#     })


# # ---------------------------------------------------------------------
# # DEMO KNOWLEDGE BASE / AI PAGES
# #
# # These pages are copied from the supplied ResolveAI HTML template demo
# # unchanged. They are exposed only to Admin and Agent sidebars.
# # ---------------------------------------------------------------------

# def _demo_page(request, template_name):
#     if not (request.user.is_superuser or request.user.is_admin or request.user.has_role_agent):
#         return HttpResponseForbidden("You do not have permission to view this page.")
#     return render(request, template_name)


# def demo_kb_article_list(request):
#     return _demo_page(request, "knowledge-base/article-list.html")


# def demo_kb_article_create(request):
#     return _demo_page(request, "knowledge-base/article-create.html")


# def demo_kb_public(request):
#     return _demo_page(request, "knowledge-base/public-knowledge-base.html")


# def demo_kb_article_detail(request):
#     return _demo_page(request, "knowledge-base/article-detail.html")


# def demo_kb_article_edit(request):
#     return _demo_page(request, "knowledge-base/article-edit.html")


# def demo_kb_article_versions(request):
#     return _demo_page(request, "knowledge-base/article-versions.html")


# def demo_ai_overview(request):
#     return _demo_page(request, "ai/ai-overview.html")


# def demo_ai_analysis_list(request):
#     return _demo_page(request, "ai/ai-analysis-list.html")


# def demo_ai_analysis_detail(request):
#     return _demo_page(request, "ai/ai-analysis-detail.html")


# def demo_ai_suggestions(request):
#     return _demo_page(request, "ai/ai-suggestions.html")


# def demo_ai_low_confidence(request):
#     return _demo_page(request, "ai/low-confidence-results.html")


# def demo_ai_model_performance(request):
#     return _demo_page(request, "ai/model-performance.html")


# def demo_ai_service_status(request):
#     return _demo_page(request, "ai/ai-service-status.html")

















