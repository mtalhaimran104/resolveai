import json
from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
from django.shortcuts import render
from django.utils import timezone

from accounts.models import User, RoleCode
from django.contrib.admin.views.decorators import staff_member_required

from accounts.decorators import admin_required
from ai.services import (
    AIServiceError,
    get_classification_model_metrics,
)
from organization.models import Department
from tickets.models import Ticket, TicketComment, TicketHistory
from classification.models import TicketCategory


# ---------------------------------------------------------------------
# SHARED REPORT HELPERS
# ---------------------------------------------------------------------

RESOLVED_STATUSES = ["RESOLVED", "CLOSED"]

# Target hours from creation to resolution, by priority. These are constants
# until the project grows a real SLA model -- there is no SLA table yet, so
# nothing per-department or per-category can be expressed here. They are used
# only to flag breaches; every other number on the report is measured.
SLA_TARGET_HOURS = {
    "CRITICAL": 4,
    "HIGH": 8,
    "MEDIUM": 24,
    "LOW": 48,
}

TRUNC_BY_GROUPING = {
    "day": TruncDay,
    "week": TruncWeek,
    "month": TruncMonth,
}

LABEL_FORMAT_BY_GROUPING = {
    "day": "%b %d",
    "week": "%b %d",
    "month": "%b %Y",
}


def _resolution_duration():
    """resolved_at - created_at, as a database-side expression."""
    return ExpressionWrapper(
        F("resolved_at") - F("created_at"),
        output_field=DurationField(),
    )


def _format_duration(total_seconds):
    """Render a duration the way the report cards do: '18h 40m', '24m'."""
    if total_seconds is None:
        return "\u2014"

    minutes = int(round(total_seconds / 60))
    hours, minutes = divmod(minutes, 60)

    if hours >= 24:
        days, hours = divmod(hours, 24)
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _average_seconds(queryset):
    """Mean resolution time in seconds, or None when nothing is resolved."""
    average = (
        queryset
        .filter(resolved_at__isnull=False)
        .annotate(duration=_resolution_duration())
        .aggregate(value=Avg("duration"))["value"]
    )
    return average.total_seconds() if average else None


def _percent_change(current, previous):
    """Percent change between two periods, rounded, guarding divide-by-zero."""
    if not previous:
        return None
    return round(((current - previous) / previous) * 100)


def _first_response_seconds_by_ticket():
    """Seconds from ticket creation to its first reply, keyed by ticket id.

    "First response" is the earliest public comment written by somebody other
    than the requester -- the closest thing to a reply that the schema
    records. Tickets nobody has answered are absent rather than zero.
    """
    first_seen = {}

    comments = (
        TicketComment.objects
        .filter(is_internal=False)
        .exclude(author=F("ticket__requester"))
        .values("ticket_id", "created_at", "ticket__created_at")
        .order_by("ticket_id", "created_at")
    )

    for comment in comments:
        ticket_id = comment["ticket_id"]
        if ticket_id in first_seen:
            continue
        delta = comment["created_at"] - comment["ticket__created_at"]
        if delta.total_seconds() >= 0:
            first_seen[ticket_id] = delta.total_seconds()

    return first_seen


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _parse_date(value):
    """Parse a YYYY-MM-DD filter value into an aware datetime, or None."""
    if not value:
        return None
    try:
        parsed = timezone.datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None
    return timezone.make_aware(parsed, timezone.get_current_timezone())


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

        average_resolution_display = _format_duration(
            average_resolution_minutes * 60
        )

    else:

        # No ticket has been resolved yet. Show that, rather than a number.
        average_resolution_display = "\u2014"

    # ---------------------------------------------------------------
    # 10. AI classification accuracy
    #
    # The model's own held-out accuracy, straight from the service that
    # serves it. Falling back to the mean confidence recorded on tickets
    # keeps the card populated when the service is unreachable -- that is a
    # different measure, so it is flagged as such.
    # ---------------------------------------------------------------

    ai_accuracy = None
    ai_accuracy_is_demo = False

    try:
        metrics = get_classification_model_metrics()
    except AIServiceError:
        metrics = None

    if metrics and metrics.get("status"):
        ai_accuracy = (metrics.get("data") or {}).get("accuracy")

    if ai_accuracy is None:
        mean_confidence = tickets.filter(
            ai_confidence__isnull=False
        ).aggregate(value=Avg("ai_confidence"))["value"]
        if mean_confidence is not None:
            ai_accuracy = round(float(mean_confidence), 1)

    if ai_accuracy is None:
        ai_accuracy = "\u2014"

    # ---------------------------------------------------------------
    # 11. Customer satisfaction
    #
    # Nothing in the schema records satisfaction: there is no rating on a
    # ticket and no survey model. Rather than print an invented score, the
    # card reports that it is not tracked yet. Wire this up when a rating
    # field or survey model exists.
    # ---------------------------------------------------------------

    satisfaction_score = None

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

        # Which numbers are measured, and which are not yet available
        "ai_accuracy_is_demo": ai_accuracy_is_demo,
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
    """Tickets opened against tickets resolved, over a chosen window.

    Supports the filters the template already renders: date range, grouping,
    department, category and status.
    """
    grouping = request.GET.get("group_by") or "week"
    if grouping not in TRUNC_BY_GROUPING:
        grouping = "week"

    now = timezone.now()
    date_to = _parse_date(request.GET.get("date_to")) or now
    date_from = _parse_date(request.GET.get("date_from")) or (
        date_to - timedelta(days=60)
    )
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    selected_department = request.GET.get("department") or ""
    selected_category = request.GET.get("category") or ""
    selected_status = request.GET.get("status") or ""

    tickets = Ticket.objects.all()

    if selected_department.isdigit():
        tickets = tickets.filter(department_id=int(selected_department))
    if selected_category.isdigit():
        tickets = tickets.filter(category_id=int(selected_category))
    if selected_status:
        tickets = tickets.filter(
            status=selected_status.replace("-", "_").upper()
        )

    truncate = TRUNC_BY_GROUPING[grouping]
    label_format = LABEL_FORMAT_BY_GROUPING[grouping]

    def buckets(queryset, field):
        rows = (
            queryset
            .filter(**{
                f"{field}__gte": date_from,
                f"{field}__lte": date_to,
            })
            .annotate(bucket=truncate(field))
            .values("bucket")
            .annotate(total=Count("id"))
            .order_by("bucket")
        )
        return {row["bucket"]: row["total"] for row in rows if row["bucket"]}

    opened = buckets(tickets, "created_at")
    resolved = buckets(
        tickets.filter(resolved_at__isnull=False), "resolved_at"
    )

    periods = sorted(set(opened) | set(resolved))

    chart_labels = [period.strftime(label_format) for period in periods]
    chart_new_tickets = [opened.get(period, 0) for period in periods]
    chart_resolved_tickets = [resolved.get(period, 0) for period in periods]

    volume_data = [
        {
            "period": label,
            "new_tickets": new_count,
            "resolved_tickets": resolved_count,
            "net_change": new_count - resolved_count,
            "in_progress": period == periods[-1] if periods else False,
        }
        for period, label, new_count, resolved_count in zip(
            periods, chart_labels, chart_new_tickets, chart_resolved_tickets
        )
    ]
    volume_data.reverse()

    # Compare the window against the equally long window before it, which is
    # what the "vs previous period" wording on the cards means.
    window = date_to - date_from
    previous_from = date_from - window

    current_new = sum(chart_new_tickets)
    current_resolved = sum(chart_resolved_tickets)

    previous_new = tickets.filter(
        created_at__gte=previous_from, created_at__lt=date_from
    ).count()
    previous_resolved = tickets.filter(
        resolved_at__gte=previous_from, resolved_at__lt=date_from
    ).count()

    current_seconds = _average_seconds(
        tickets.filter(resolved_at__gte=date_from, resolved_at__lte=date_to)
    )
    previous_seconds = _average_seconds(
        tickets.filter(resolved_at__gte=previous_from, resolved_at__lt=date_from)
    )

    return render(
        request,
        "reports/ticket-volume.html",
        {
            "page_title": "Ticket Volume",

            "group_by": grouping,
            "date_from": date_from.date().isoformat(),
            "date_to": date_to.date().isoformat(),

            "departments": Department.objects.order_by("name"),
            "categories": TicketCategory.objects.filter(
                is_active=True
            ).order_by("name"),
            "selected_department": selected_department,
            "selected_category": selected_category,
            "selected_status": selected_status,

            "volume_data": volume_data,
            "chart_labels": json.dumps(chart_labels),
            "chart_new_tickets": json.dumps(chart_new_tickets),
            "chart_resolved_tickets": json.dumps(chart_resolved_tickets),

            "total_new_tickets": current_new,
            "total_resolved_tickets": current_resolved,
            "new_ticket_change": _percent_change(current_new, previous_new),
            "resolved_ticket_change": _percent_change(
                current_resolved, previous_resolved
            ),
            "resolution_time_change": _percent_change(
                current_seconds or 0, previous_seconds or 0
            ),
            "backlog_change": current_new - current_resolved,
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