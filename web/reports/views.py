from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.shortcuts import render
from django.utils import timezone

from accounts.models import User, RoleCode
from django.contrib.admin.views.decorators import staff_member_required

from accounts.decorators import admin_required
from tickets.models import Ticket, TicketHistory
from classification.models import TicketCategory


# ---------------------------------------------------------------------
# REPORTS
# Admin only
# ---------------------------------------------------------------------


def _get_ticket_field_names():
    """
    Return the actual fields available on the current Ticket model.

    This keeps the dashboard safe if optional fields such as
    resolved_at / closed_at are not present in the current project.
    """
    return {
        field.name
        for field in Ticket._meta.get_fields()
        if hasattr(field, "name")
    }


def _get_status_values():
    """
    Return the actual status values defined by the Ticket model.
    """
    try:
        return {
            value
            for value, label in Ticket.Status.choices
        }
    except AttributeError:
        return set()


# ---------------------------------------------------------------------
# REPORTS DASHBOARD
# ---------------------------------------------------------------------


@admin_required
def reports_dashboard(request):

    now = timezone.now()

    # ---------------------------------------------------------------
    # Date ranges
    # ---------------------------------------------------------------

    last_30_days = now - timedelta(days=30)
    last_8_weeks = now - timedelta(weeks=8)

    ticket_fields = _get_ticket_field_names()

    # ---------------------------------------------------------------
    # Base queryset
    # ---------------------------------------------------------------

    tickets = Ticket.objects.all()

    last_30_day_tickets = tickets.filter(
        created_at__gte=last_30_days
    )

    # ---------------------------------------------------------------
    # 1. Total tickets - REAL
    # ---------------------------------------------------------------

    total_tickets = last_30_day_tickets.count()

    # ---------------------------------------------------------------
    # 2. Open / Closed - REAL
    # ---------------------------------------------------------------

    open_statuses = [
        "OPEN",
        "IN_PROGRESS",
        "WAITING_FOR_USER",
    ]

    closed_statuses = [
        "RESOLVED",
        "CLOSED",
    ]

    open_tickets = tickets.filter(
        status__in=open_statuses
    ).count()

    closed_tickets = tickets.filter(
        status__in=closed_statuses
    ).count()

    # ---------------------------------------------------------------
    # 3. Status counts - REAL
    # ---------------------------------------------------------------

    status_definitions = [
        ("OPEN", "Open"),
        ("IN_PROGRESS", "In Progress"),
        ("WAITING_FOR_USER", "Waiting"),
        ("RESOLVED", "Resolved"),
        ("CLOSED", "Closed"),
    ]

    status_labels = []
    status_data = []

    for status_value, status_label in status_definitions:

        count = tickets.filter(
            status=status_value
        ).count()

        status_labels.append(status_label)
        status_data.append(count)

    # ---------------------------------------------------------------
    # 4. Priority counts - REAL
    # ---------------------------------------------------------------

    priority_definitions = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("CRITICAL", "Critical"),
    ]

    priority_labels = []
    priority_data = []

    for priority_value, priority_label in priority_definitions:

        count = tickets.filter(
            priority=priority_value
        ).count()

        priority_labels.append(priority_label)
        priority_data.append(count)

    # ---------------------------------------------------------------
    # 5. Category counts - REAL
    # ---------------------------------------------------------------

    category_rows = (
        tickets
        .filter(category__isnull=False)
        .values("category__name")
        .annotate(
            total=Count("id")
        )
        .order_by("-total")
    )

    category_labels = [
        row["category__name"]
        for row in category_rows
    ]

    category_data = [
        row["total"]
        for row in category_rows
    ]

    # Limit dashboard chart to top 10 categories
    category_labels = category_labels[:10]
    category_data = category_data[:10]

    # ---------------------------------------------------------------
    # 6. Department counts - REAL
    # ---------------------------------------------------------------

    department_rows = (
        tickets
        .filter(department__isnull=False)
        .values("department__name")
        .annotate(
            total=Count("id")
        )
        .order_by("-total")
    )

    department_labels = [
        row["department__name"]
        for row in department_rows
    ]

    department_data = [
        row["total"]
        for row in department_rows
    ]

    # ---------------------------------------------------------------
    # 7. Agent workload - REAL
    # ---------------------------------------------------------------

    agent_rows = (
        tickets
        .filter(assigned_to__isnull=False)
        .values(
            "assigned_to_id",
            "assigned_to__first_name",
            "assigned_to__last_name",
            "department__name",
        )
        .annotate(
            open_count=Count(
                "id",
                filter=Q(
                    status__in=open_statuses
                ),
            ),
            resolved_count=Count(
                "id",
                filter=Q(
                    status__in=closed_statuses
                ),
            ),
            total_count=Count("id"),
        )
        .order_by("-total_count")
    )

    agent_workload = []

    for row in agent_rows:

        first_name = row["assigned_to__first_name"] or ""
        last_name = row["assigned_to__last_name"] or ""

        agent_name = f"{first_name} {last_name}".strip()

        if not agent_name:
            agent_name = f"Agent #{row['assigned_to_id']}"

        agent_workload.append({
            "id": row["assigned_to_id"],
            "name": agent_name,
            "department": row["department__name"] or "—",
            "open_count": row["open_count"],
            "resolved_count": row["resolved_count"],
        })

    # Dashboard shows highest workloads first
    agent_workload = agent_workload[:10]

    # ---------------------------------------------------------------
    # 8. Ticket volume - REAL
    # ---------------------------------------------------------------

    volume_labels = []
    new_ticket_data = []
    resolved_ticket_data = []

    for week_index in range(8):

        week_end = now - timedelta(
            weeks=7 - week_index
        )

        week_start = week_end - timedelta(
            days=7
        )

        new_count = tickets.filter(
            created_at__gte=week_start,
            created_at__lt=week_end,
        ).count()

        resolved_count = 0

        if "resolved_at" in ticket_fields:

            resolved_count = tickets.filter(
                resolved_at__isnull=False,
                resolved_at__gte=week_start,
                resolved_at__lt=week_end,
            ).count()

        volume_labels.append(
            week_start.strftime("%b %d")
        )

        new_ticket_data.append(new_count)
        resolved_ticket_data.append(resolved_count)

    # ---------------------------------------------------------------
    # 9. Average resolution time
    # ---------------------------------------------------------------

    average_resolution_minutes = None

    if "resolved_at" in ticket_fields:

        resolved_queryset = tickets.filter(
            resolved_at__isnull=False,
            created_at__isnull=False,
        )

        resolution_times = []

        for ticket in resolved_queryset.only(
            "created_at",
            "resolved_at",
        ):

            if ticket.resolved_at and ticket.created_at:

                duration = (
                    ticket.resolved_at -
                    ticket.created_at
                )

                resolution_times.append(
                    duration.total_seconds() / 60
                )

        if resolution_times:

            average_resolution_minutes = (
                sum(resolution_times) /
                len(resolution_times)
            )

    if average_resolution_minutes is not None:

        total_minutes = round(
            average_resolution_minutes
        )

        hours = total_minutes // 60
        minutes = total_minutes % 60

        average_resolution_display = (
            f"{hours}h {minutes}m"
        )

    else:

        # Controlled demo value
        average_resolution_display = "18h 40m"

    # ---------------------------------------------------------------
    # 10. AI accuracy - CONTROLLED DEMO
    # ---------------------------------------------------------------

    ai_accuracy = 91.4

    # ---------------------------------------------------------------
    # 11. Customer satisfaction - CONTROLLED DEMO
    # ---------------------------------------------------------------

    satisfaction_score = 4.4

    # ---------------------------------------------------------------
    # Dashboard context
    # ---------------------------------------------------------------

    context = {
        "page_title": "Reports Dashboard",

        # Summary cards
        "total_tickets": total_tickets,
        "average_resolution_display": average_resolution_display,
        "ai_accuracy": ai_accuracy,
        "satisfaction_score": satisfaction_score,

        # Open / closed
        "open_tickets": open_tickets,
        "closed_tickets": closed_tickets,

        # Status
        "status_labels": status_labels,
        "status_data": status_data,

        # Priority
        "priority_labels": priority_labels,
        "priority_data": priority_data,

        # Volume
        "volume_labels": volume_labels,
        "new_ticket_data": new_ticket_data,
        "resolved_ticket_data": resolved_ticket_data,

        # Category
        "category_labels": category_labels,
        "category_data": category_data,

        # Department
        "department_labels": department_labels,
        "department_data": department_data,

        # Agents
        "agent_workload": agent_workload,

        # Demo indicators
        "ai_accuracy_is_demo": True,
        "satisfaction_is_demo": True,
        "resolution_time_is_demo": (
            average_resolution_minutes is None
        ),
    }

    return render(
        request,
        "reports/reports-dashboard.html",
        context,
    )


# ---------------------------------------------------------------------
# TICKET VOLUME REPORT
# ---------------------------------------------------------------------


@admin_required
def ticket_volume_report(request):

    return render(
        request,
        "reports/ticket-volume.html",
        {
            "page_title": "Ticket Volume",
        },
    )


# ---------------------------------------------------------------------
# RESOLUTION TIME REPORT
# ---------------------------------------------------------------------


@admin_required
def resolution_time_report(request):

    return render(
        request,
        "reports/resolution-time.html",
        {
            "page_title": "Resolution Time",
        },
    )


# ---------------------------------------------------------------------
# AGENT PERFORMANCE REPORT
# Pagination: 5 agents per page
# ---------------------------------------------------------------------


@admin_required
def agent_performance_report(request):

    resolved_statuses = [
        "RESOLVED",
        "CLOSED",
    ]

    # -------------------------------------------------------------
    # Get all active agents
    # -------------------------------------------------------------

    agents_queryset = (
        User.objects
        .filter(
            user_roles__role__code=RoleCode.AGENT,
            is_active=True,
        )
        .select_related("department")
        .distinct()
        .order_by("first_name", "last_name")
    )

    agents = []

    chart_labels = []
    chart_values = []

    # -------------------------------------------------------------
    # Build agent performance data
    # -------------------------------------------------------------

    for agent in agents_queryset:

        tickets = Ticket.objects.filter(
            assigned_to=agent
        )

        assigned_count = tickets.count()

        resolved_count = tickets.filter(
            status__in=resolved_statuses
        ).count()

        reopened_count = TicketHistory.objects.filter(
            ticket__assigned_to=agent,
            description__icontains="reopened",
        ).count()

        agent_name = agent.get_full_name()

        if not agent_name:
            agent_name = agent.username

        agents.append({
            "user": agent,
            "assigned": assigned_count,
            "resolved": resolved_count,
            "avg_response": "—",
            "avg_resolution": "—",
            "reopened": reopened_count,
            "satisfaction": "—",
            "ai_suggestions_used": "—",
            "department": agent.department,
        })

        chart_labels.append(agent_name)
        chart_values.append(resolved_count)

    # -------------------------------------------------------------
    # Pagination - 5 agents per page
    # -------------------------------------------------------------

    paginator = Paginator(
        agents,
        5
    )

    page_number = request.GET.get(
        "page",
        1
    )

    page_obj = paginator.get_page(
        page_number
    )

    # -------------------------------------------------------------
    # Render
    # -------------------------------------------------------------

    return render(
        request,
        "reports/agent-performance.html",
        {
            "page_title": "Agent Performance",

            "agents": page_obj,
            "page_obj": page_obj,

            "chart_labels": chart_labels,
            "chart_values": chart_values,
        },
    )


# ---------------------------------------------------------------------
# DEPARTMENT REPORT
# Pagination: 5 departments per page
# ---------------------------------------------------------------------


@admin_required
def department_report(request):

    now = timezone.now()

    month_start = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    ticket_fields = _get_ticket_field_names()

    open_statuses = [
        "OPEN",
        "IN_PROGRESS",
        "WAITING_FOR_USER",
    ]

    resolved_statuses = [
        "RESOLVED",
        "CLOSED",
    ]

    department_model = (
        Ticket._meta
        .get_field("department")
        .remote_field
        .model
    )

    departments = (
        department_model.objects
        .all()
        .order_by("name")
    )

    department_data = []

    chart_labels = []
    chart_volume = []
    chart_open = []
    chart_resolved = []

    for department in departments:

        department_tickets = Ticket.objects.filter(
            department=department
        )

        # ---------------------------------------------------------
        # Open tickets
        # ---------------------------------------------------------

        open_tickets = department_tickets.filter(
            status__in=open_statuses
        ).count()

        # ---------------------------------------------------------
        # Resolved this month
        # ---------------------------------------------------------

        if "resolved_at" in ticket_fields:

            resolved_this_month = department_tickets.filter(
                status__in=resolved_statuses,
                resolved_at__isnull=False,
                resolved_at__gte=month_start,
                resolved_at__lte=now,
            ).count()

        else:

            resolved_this_month = department_tickets.filter(
                status__in=resolved_statuses,
                updated_at__gte=month_start,
                updated_at__lte=now,
            ).count()

        # ---------------------------------------------------------
        # Average resolution time
        # ---------------------------------------------------------

        avg_resolution_time = "—"

        if "resolved_at" in ticket_fields:

            resolved_tickets = department_tickets.filter(
                status__in=resolved_statuses,
                resolved_at__isnull=False,
                created_at__isnull=False,
            ).only(
                "created_at",
                "resolved_at",
            )

            resolution_minutes = []

            for ticket in resolved_tickets:

                if ticket.created_at and ticket.resolved_at:

                    duration = (
                        ticket.resolved_at -
                        ticket.created_at
                    )

                    minutes = (
                        duration.total_seconds() / 60
                    )

                    resolution_minutes.append(
                        minutes
                    )

            if resolution_minutes:

                average_minutes = round(
                    sum(resolution_minutes) /
                    len(resolution_minutes)
                )

                hours = average_minutes // 60
                minutes = average_minutes % 60

                avg_resolution_time = (
                    f"{hours}h {minutes}m"
                )

        # ---------------------------------------------------------
        # Agent count
        # ---------------------------------------------------------

        agent_count = User.objects.filter(
            department=department
        ).count()

        # ---------------------------------------------------------
        # Active supervisor
        # ---------------------------------------------------------

        active_supervisor = None

        supervisor = (
            User.objects
            .filter(
                department=department,
                roles__code=RoleCode.SUPERVISOR,
                is_active=True,
            )
            .first()
        )

        if supervisor:

            active_supervisor = (
                f"{supervisor.first_name} "
                f"{supervisor.last_name}"
            ).strip()

            if not active_supervisor:
                active_supervisor = supervisor.username

        # ---------------------------------------------------------
        # Total tickets
        # ---------------------------------------------------------

        total_count = department_tickets.count()

        # ---------------------------------------------------------
        # Add department row
        # ---------------------------------------------------------

        department_data.append({
            "id": department.id,
            "name": department.name,
            "open_tickets": open_tickets,
            "resolved_this_month": resolved_this_month,
            "avg_resolution_time": avg_resolution_time,
            "agent_count": agent_count,
            "active_supervisor": active_supervisor,
        })

        # ---------------------------------------------------------
        # Chart data
        # ---------------------------------------------------------

        chart_labels.append(
            department.name
        )

        chart_volume.append(
            total_count
        )

        chart_open.append(
            open_tickets
        )

        chart_resolved.append(
            resolved_this_month
        )

    # -------------------------------------------------------------
    # Pagination - 5 departments per page
    # -------------------------------------------------------------

    paginator = Paginator(
        department_data,
        5
    )

    page_number = request.GET.get(
        "page",
        1
    )

    page_obj = paginator.get_page(
        page_number
    )

    # -------------------------------------------------------------
    # Render
    # -------------------------------------------------------------

    return render(
        request,
        "reports/department-report.html",
        {
            "page_title": "Department Report",

            "department_data": page_obj,
            "page_obj": page_obj,

            "chart_data": {
                "labels": chart_labels,
                "volume": chart_volume,
                "open": chart_open,
                "resolved": chart_resolved,
            },
        },
    )


# ---------------------------------------------------------------------
# CATEGORY REPORT
# Pagination: 5 categories per page
# ---------------------------------------------------------------------


@admin_required
def category_report(request):

    # -------------------------------------------------------------
    # Get all categories
    # -------------------------------------------------------------

    categories = (
        TicketCategory.objects
        .all()
        .order_by("name")
    )

    category_reports = []

    # These lists are kept separate for the chart.
    # This means the chart can display ALL categories while
    # the table displays only 5 categories per page.
    chart_labels = []
    chart_data = []

    # -------------------------------------------------------------
    # Build category report data
    # -------------------------------------------------------------

    for category in categories:

        # Real tickets belonging to this category
        tickets = Ticket.objects.filter(
            category=category
        )

        # ---------------------------------------------------------
        # Total tickets
        # ---------------------------------------------------------

        total_count = tickets.count()

        # ---------------------------------------------------------
        # Open / active tickets
        # ---------------------------------------------------------

        open_count = tickets.filter(
            status__in=[
                "OPEN",
                "IN_PROGRESS",
                "WAITING_FOR_USER",
            ]
        ).count()

        # ---------------------------------------------------------
        # Resolved / closed tickets
        # ---------------------------------------------------------

        resolved_count = tickets.filter(
            status__in=[
                "RESOLVED",
                "CLOSED",
            ]
        ).count()

        # ---------------------------------------------------------
        # Real average AI confidence
        # ---------------------------------------------------------

        avg_ai_confidence = tickets.filter(
            ai_confidence__isnull=False
        ).aggregate(
            avg=Avg("ai_confidence")
        )["avg"]

        # ---------------------------------------------------------
        # Real departments used by this category
        # ---------------------------------------------------------

        department_names = list(
            tickets
            .filter(
                department__isnull=False
            )
            .values_list(
                "department__name",
                flat=True
            )
            .distinct()
        )

        # ---------------------------------------------------------
        # Add category row
        # ---------------------------------------------------------

        category_reports.append({
            "category": category,

            "department": (
                ", ".join(department_names)
                if department_names
                else "-"
            ),

            "open_count": open_count,

            "resolved_count": resolved_count,

            "total_count": total_count,

            # Resolution time is not currently calculated
            # from TicketHistory.
            "avg_resolution_time": None,

            # Real average AI confidence.
            "ai_accuracy": avg_ai_confidence,

            "ai_disabled": False,
        })

        # ---------------------------------------------------------
        # Chart data
        # ---------------------------------------------------------

        chart_labels.append(
            category.name
        )

        chart_data.append(
            total_count
        )

    # -------------------------------------------------------------
    # Pagination - 5 categories per page
    # -------------------------------------------------------------

    paginator = Paginator(
        category_reports,
        5
    )

    page_number = request.GET.get(
        "page",
        1
    )

    page_obj = paginator.get_page(
        page_number
    )

    # -------------------------------------------------------------
    # Render
    # -------------------------------------------------------------

    return render(
        request,
        "reports/category-report.html",
        {
            "page_title": "Category Report",

            # Paginated table data
            "category_reports": page_obj,

            # Pagination object
            "page_obj": page_obj,

            # Full chart data
            "chart_labels": chart_labels,
            "chart_data": chart_data,
        },
    )


# ---------------------------------------------------------------------
# AI ACCURACY REPORT
# ---------------------------------------------------------------------


@admin_required
def ai_accuracy_report(request):

    """
    AI Accuracy report.

    Classification accuracy is represented by the average AI confidence
    available for each ticket category. This uses real Ticket data.
    """

    category_rows = (
        Ticket.objects
        .filter(
            category__isnull=False,
            ai_confidence__isnull=False,
        )
        .values(
            "category__name"
        )
        .annotate(
            average_confidence=Avg(
                "ai_confidence"
            ),
            ticket_count=Count("id"),
        )
        .order_by("-ticket_count")
    )

    classification_labels = []
    classification_accuracy = []

    for row in category_rows:

        category_name = row[
            "category__name"
        ]

        if not category_name:
            continue

        confidence = row[
            "average_confidence"
        ]

        if confidence is None:
            continue

        # ai_confidence may be stored as:
        #
        # 0.91 -> 91%
        # 91   -> 91%

        if confidence <= 1:
            accuracy = (
                float(confidence) * 100
            )
        else:
            accuracy = float(
                confidence
            )

        # Keep values between 0 and 100
        accuracy = max(
            0,
            min(
                100,
                accuracy
            )
        )

        classification_labels.append(
            category_name
        )

        classification_accuracy.append(
            round(
                accuracy,
                1
            )
        )

    context = {
        "page_title": "AI Accuracy",

        "classification_labels": (
            classification_labels
        ),

        "classification_accuracy": (
            classification_accuracy
        ),

        # This is not ground-truth classification accuracy.
        "classification_accuracy_is_demo": False,
    }

    return render(
        request,
        "reports/ai-accuracy-report.html",
        context,
    )


# ---------------------------------------------------------------------
# CUSTOMER SATISFACTION REPORT
# ---------------------------------------------------------------------


@admin_required
def customer_satisfaction_report(request):

    return render(
        request,
        "reports/customer-satisfaction.html",
        {
            "page_title": "Customer Satisfaction",
        },
    )


# ---------------------------------------------------------------------
# LOW CONFIDENCE RESULTS
# ---------------------------------------------------------------------


@admin_required
def low_confidence_results(request):

    return render(
        request,
        "reports/low-confidence-results.html",
        {
            "page_title": "Low Confidence Results",
        },
    )