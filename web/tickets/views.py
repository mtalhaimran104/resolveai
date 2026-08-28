from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q

from accounts.decorators import (
    admin_required,
    supervisor_required,
    agent_required,
    agent_or_supervisor_required,
)
from accounts.models import RoleCode

from .models import (
    Ticket,
    TicketAttachment,
    TicketHistory,
)
from classification.models import TicketCategory
from .forms import (
    TicketForm,
    TicketCommentForm,
    TicketAttachmentForm,
)


User = get_user_model()

PAGE_SIZE = 5


# =====================================================================
# TICKET FILTERS
# =====================================================================

def _filter_tickets(request, tickets):
    """
    Apply advanced ticket filters.

    Supported GET parameters:

        q
        ticket_number
        requester
        assigned_agent
        department
        category
        priority
        status
        created_date
        updated_date
        ai_confidence_min
        ai_confidence_max
        sentiment
    """

    # -----------------------------------------------------------------
    # Search
    # -----------------------------------------------------------------

    search = request.GET.get("q", "").strip()
    ticket_number = request.GET.get("ticket_number", "").strip()

    if search:
        tickets = tickets.filter(
            Q(ticket_number__icontains=search)
            | Q(subject__icontains=search)
            | Q(requester__first_name__icontains=search)
            | Q(requester__last_name__icontains=search)
            | Q(requester__username__icontains=search)
        )

    if ticket_number:
        tickets = tickets.filter(
            ticket_number__icontains=ticket_number
        )

    # -----------------------------------------------------------------
    # Requester
    # -----------------------------------------------------------------

    requester = request.GET.get("requester", "").strip()

    if requester.isdigit():
        tickets = tickets.filter(
            requester_id=requester
        )

    # -----------------------------------------------------------------
    # Assigned Agent
    # -----------------------------------------------------------------

    assigned_agent = request.GET.get(
        "assigned_agent",
        "",
    ).strip()

    if assigned_agent == "unassigned":
        tickets = tickets.filter(
            assigned_to__isnull=True
        )

    elif assigned_agent.isdigit():
        tickets = tickets.filter(
            assigned_to_id=assigned_agent
        )

    # -----------------------------------------------------------------
    # Department
    # -----------------------------------------------------------------

    department = request.GET.get(
        "department",
        "",
    ).strip()

    if department.isdigit():
        tickets = tickets.filter(
            department_id=department
        )

    # -----------------------------------------------------------------
    # Category
    # -----------------------------------------------------------------

    category = request.GET.get(
        "category",
        "",
    ).strip()

    if category.isdigit():
        tickets = tickets.filter(
            category_id=category
        )

    # -----------------------------------------------------------------
    # Priority
    # -----------------------------------------------------------------

    priority = request.GET.get(
        "priority",
        "",
    ).strip()

    if priority in Ticket.Priority.values:
        tickets = tickets.filter(
            priority=priority
        )

    # -----------------------------------------------------------------
    # Status
    # -----------------------------------------------------------------

    status = request.GET.get(
        "status",
        "",
    ).strip()

    if status in Ticket.Status.values:
        tickets = tickets.filter(
            status=status
        )

    # -----------------------------------------------------------------
    # Created Date
    # -----------------------------------------------------------------

    created_date = request.GET.get(
        "created_date",
        "",
    ).strip()

    if created_date:
        tickets = tickets.filter(
            created_at__date=created_date
        )

    # -----------------------------------------------------------------
    # Updated Date
    # -----------------------------------------------------------------

    updated_date = request.GET.get(
        "updated_date",
        "",
    ).strip()

    if updated_date:
        tickets = tickets.filter(
            updated_at__date=updated_date
        )

    # -----------------------------------------------------------------
    # AI Confidence
    # -----------------------------------------------------------------

    ai_confidence_min = request.GET.get(
        "ai_confidence_min",
        "",
    ).strip()

    ai_confidence_max = request.GET.get(
        "ai_confidence_max",
        "",
    ).strip()

    if ai_confidence_min:
        try:
            tickets = tickets.filter(
                ai_confidence__gte=float(
                    ai_confidence_min
                )
            )
        except (ValueError, TypeError):
            pass

    if ai_confidence_max:
        try:
            tickets = tickets.filter(
                ai_confidence__lte=float(
                    ai_confidence_max
                )
            )
        except (ValueError, TypeError):
            pass

    # -----------------------------------------------------------------
    # Sentiment
    # -----------------------------------------------------------------

    sentiment = request.GET.get(
        "sentiment",
        "",
    ).strip()

    if sentiment:
        tickets = tickets.filter(
            sentiment__iexact=sentiment
        )

    return tickets


# =====================================================================
# PAGINATION
# =====================================================================

def _paginate(
    request,
    tickets,
    per_page=PAGE_SIZE,
):
    paginator = Paginator(
        tickets,
        per_page,
    )

    page_number = request.GET.get(
        "page",
        1,
    )

    return paginator.get_page(
        page_number
    )


# =====================================================================
# ADVANCED FILTER CONTEXT
# =====================================================================

def _ticket_list_filter_context(request):
    from organization.models import Department

    query = request.GET.copy()
    query.pop("page", None)

    # -----------------------------------------------------------------
    # Agents
    # -----------------------------------------------------------------

    agents = (
        User.objects
        .filter(
            user_roles__role__code=RoleCode.AGENT,
            is_active=True,
        )
        .distinct()
        .order_by(
            "first_name",
            "last_name",
            "username",
        )
    )

    # -----------------------------------------------------------------
    # Requesters
    # -----------------------------------------------------------------

    requesters = (
        User.objects
        .filter(
            tickets_requested__isnull=False
        )
        .distinct()
        .order_by(
            "first_name",
            "last_name",
            "username",
        )
    )

    # -----------------------------------------------------------------
    # Departments
    # -----------------------------------------------------------------

    departments = (
        Department.objects
        .filter(is_active=True)
        .order_by("name")
    )

    # -----------------------------------------------------------------
    # Categories
    # -----------------------------------------------------------------

    categories = (
        TicketCategory.objects
        .filter(is_active=True)
        .order_by("name")
    )

    # -----------------------------------------------------------------
    # Sentiments
    # -----------------------------------------------------------------

    sentiments = [
        "positive",
        "neutral",
        "negative",
    ]

    return {
        "statuses": Ticket.Status.choices,
        "priorities": Ticket.Priority.choices,

        "filter_requesters": requesters,
        "filter_agents": agents,
        "filter_departments": departments,
        "filter_categories": categories,
        "filter_sentiments": sentiments,

        "selected_ticket_number": request.GET.get(
            "ticket_number",
            "",
        ),

        "selected_requester": request.GET.get(
            "requester",
            "",
        ),

        "selected_assigned_agent": request.GET.get(
            "assigned_agent",
            "",
        ),

        "selected_status": request.GET.get(
            "status",
            "",
        ),

        "selected_priority": request.GET.get(
            "priority",
            "",
        ),

        "selected_department": request.GET.get(
            "department",
            "",
        ),

        "selected_category": request.GET.get(
            "category",
            "",
        ),

        "selected_created_date": request.GET.get(
            "created_date",
            "",
        ),

        "selected_updated_date": request.GET.get(
            "updated_date",
            "",
        ),

        "selected_ai_confidence_min": request.GET.get(
            "ai_confidence_min",
            "",
        ),

        "selected_ai_confidence_max": request.GET.get(
            "ai_confidence_max",
            "",
        ),

        "selected_sentiment": request.GET.get(
            "sentiment",
            "",
        ),

        "search_query": request.GET.get(
            "q",
            "",
        ),

        "base_query_string": query.urlencode(),
    }


# =====================================================================
# ACCESS CONTROL
# =====================================================================

def _can_access_ticket(user, ticket):
    """
    Ticket access:

    - Admin can access every ticket.
    - Requester can access their own ticket.
    - Assigned agent can access the ticket.
    - Supervisor can access every ticket.
    """

    if user.is_admin:
        return True

    if ticket.requester_id == user.id:
        return True

    if ticket.assigned_to_id == user.id:
        return True

    if user.has_role(RoleCode.SUPERVISOR):
        return True

    return False


def _is_agent_view(user):
    """
    Determines whether the user should see
    the staff/agent version of the ticket detail page.
    """

    return (
        user.is_admin
        or user.has_role(RoleCode.SUPERVISOR)
        or user.has_role(RoleCode.AGENT)
    )


def _is_supervisor_or_admin(user):
    return (
        user.is_admin
        or user.has_role(RoleCode.SUPERVISOR)
    )


# =====================================================================
# REQUESTER - MY TICKETS
# =====================================================================

@login_required
def ticket_list(request):
    tickets = (
        Ticket.objects
        .filter(
            requester=request.user
        )
        .select_related(
            "assigned_to",
            "department",
            "category",
        )
        .order_by("-created_at")
    )

    return render(
        request,
        "tickets/my-tickets.html",
        {
            "tickets": tickets,
            "page_title": "My Tickets",
        },
    )


# =====================================================================
# REQUESTER - CREATE TICKET
# =====================================================================

@login_required
def ticket_create(request):
    if request.method == "POST":
        form = TicketForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            ticket = form.save(
                commit=False
            )

            ticket.requester = request.user
            ticket.save()

            # ---------------------------------------------------------
            # History
            # ---------------------------------------------------------

            actor_label = (
                request.user.get_full_name()
                or request.user.username
            )

            TicketHistory.objects.create(
                ticket=ticket,
                actor=request.user,
                action=TicketHistory.Action.CREATED,
                description=(
                    f"Ticket created by {actor_label}."
                ),
            )

            # ---------------------------------------------------------
            # Attachments
            # ---------------------------------------------------------

            for uploaded_file in request.FILES.getlist(
                "attachments"
            ):
                TicketAttachment.objects.create(
                    ticket=ticket,
                    uploaded_by=request.user,
                    file=uploaded_file,
                    original_filename=uploaded_file.name,
                    size_bytes=uploaded_file.size,
                )

            messages.success(
                request,
                (
                    f"Ticket {ticket.ticket_number} "
                    "created successfully."
                ),
            )

            return redirect(
                "ticket_list"
            )

    else:
        form = TicketForm()

    return render(
        request,
        "tickets/create-ticket.html",
        {
            "form": form,
            "page_title": "Create Ticket",
        },
    )


# =====================================================================
# TICKET DETAIL
# =====================================================================

@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(
        Ticket,
        pk=pk,
    )

    if not _can_access_ticket(
        request.user,
        ticket,
    ):
        return HttpResponseForbidden(
            "You do not have permission to view this ticket."
        )

    comments = (
        ticket.comments
        .select_related("author")
        .all()
    )

    attachments = (
        ticket.attachments
        .select_related("uploaded_by")
        .all()
    )

    history = (
        ticket.history
        .select_related("actor")
        .all()
    )

    context = {
        "ticket": ticket,
        "comments": comments,
        "attachments": attachments,
        "history": history,
        "comment_form": TicketCommentForm(),
        "attachment_form": TicketAttachmentForm(),
        "page_title": ticket.ticket_number,
    }

    # -------------------------------------------------------------
    # Staff view
    # -------------------------------------------------------------

    if _is_agent_view(request.user):
        context["statuses"] = Ticket.Status.choices

        context["priorities"] = Ticket.Priority.choices

        context["categories"] = (
            TicketCategory.objects
            .filter(is_active=True)
            .order_by("name")
        )

        context["is_own_ticket"] = (
            ticket.assigned_to_id == request.user.id
        )

        context["public_comments"] = [
            comment
            for comment in comments
            if not comment.is_internal
        ]

        context["internal_notes"] = [
            comment
            for comment in comments
            if comment.is_internal
        ]

        return render(
            request,
            "tickets/ticket-detail-agent.html",
            context,
        )

    # -------------------------------------------------------------
    # Requester view
    # -------------------------------------------------------------

    context["comments"] = [
        comment
        for comment in comments
        if not comment.is_internal
    ]

    return render(
        request,
        "tickets/ticket-detail-requester.html",
        context,
    )


# =====================================================================
# COMMENTS
# =====================================================================

@login_required
def ticket_add_comment(request, pk):
    ticket = get_object_or_404(
        Ticket,
        pk=pk,
    )

    if not _can_access_ticket(
        request.user,
        ticket,
    ):
        return HttpResponseForbidden(
            "You do not have permission to comment on this ticket."
        )

    if request.method == "POST":
        form = TicketCommentForm(
            request.POST
        )

        if form.is_valid():
            comment = form.save(
                commit=False
            )

            comment.ticket = ticket
            comment.author = request.user

            # Requesters can never create internal notes.
            if not _is_agent_view(
                request.user
            ):
                comment.is_internal = False

            comment.save()

            actor_label = (
                request.user.get_full_name()
                or request.user.username
            )

            # ---------------------------------------------------------
            # Internal note
            # ---------------------------------------------------------

            if comment.is_internal:
                TicketHistory.objects.create(
                    ticket=ticket,
                    actor=request.user,
                    action=(
                        TicketHistory.Action.INTERNAL_NOTE
                    ),
                    description=(
                        "Internal note added by "
                        f"{actor_label}."
                    ),
                )

                messages.success(
                    request,
                    "Internal note added.",
                )

            # ---------------------------------------------------------
            # Public reply
            # ---------------------------------------------------------

            else:
                TicketHistory.objects.create(
                    ticket=ticket,
                    actor=request.user,
                    action=(
                        TicketHistory.Action.PUBLIC_REPLY
                    ),
                    description=(
                        "Reply added by "
                        f"{actor_label}."
                    ),
                )

                messages.success(
                    request,
                    "Reply added.",
                )

        else:
            messages.error(
                request,
                (
                    "Reply could not be added. "
                    "Please enter a message."
                ),
            )

    return redirect(
        "ticket_detail",
        pk=ticket.pk,
    )


# =====================================================================
# ATTACHMENTS
# =====================================================================

@login_required
def ticket_add_attachment(request, pk):
    ticket = get_object_or_404(
        Ticket,
        pk=pk,
    )

    if not _can_access_ticket(
        request.user,
        ticket,
    ):
        return HttpResponseForbidden(
            "You do not have permission to attach files to this ticket."
        )

    if request.method == "POST":
        form = TicketAttachmentForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            attachment = form.save(
                commit=False
            )

            attachment.ticket = ticket
            attachment.uploaded_by = request.user

            uploaded_file = form.cleaned_data["file"]

            attachment.original_filename = (
                uploaded_file.name
            )

            attachment.size_bytes = (
                uploaded_file.size
            )

            attachment.save()

            actor_label = (
                request.user.get_full_name()
                or request.user.username
            )

            TicketHistory.objects.create(
                ticket=ticket,
                actor=request.user,
                action=(
                    TicketHistory.Action.ATTACHMENT_ADDED
                ),
                description=(
                    f"Attachment "
                    f"'{attachment.original_filename}' "
                    f"uploaded by {actor_label}."
                ),
            )

            messages.success(
                request,
                "Attachment uploaded successfully.",
            )

        else:
            error_text = " ".join(
                str(error)
                for errors in form.errors.values()
                for error in errors
            )

            messages.error(
                request,
                error_text
                or "File could not be uploaded.",
            )

    return redirect(
        "ticket_detail",
        pk=ticket.pk,
    )


# =====================================================================
# ADMIN - ALL TICKETS
# =====================================================================

@admin_required
def admin_ticket_list(request):
    tickets = (
        Ticket.objects
        .select_related(
            "requester",
            "assigned_to",
            "department",
            "category",
        )
        .order_by("-created_at")
    )

    tickets = _filter_tickets(
        request,
        tickets,
    )

    page_obj = _paginate(
        request,
        tickets,
    )

    context = {
        "tickets": page_obj,
        "page_obj": page_obj,
        "page_title": "All Tickets",
    }

    context.update(
        _ticket_list_filter_context(request)
    )

    return render(
        request,
        "tickets/ticket-table.html",
        context,
    )


# =====================================================================
# UPDATE STATUS
# =====================================================================

@login_required
def ticket_update_status(request, pk):
    ticket = get_object_or_404(
        Ticket,
        pk=pk,
    )

    if not (
        request.user.is_admin
        or request.user.has_role(RoleCode.SUPERVISOR)
        or ticket.assigned_to_id == request.user.id
    ):
        return HttpResponseForbidden(
            "You do not have permission to update this ticket."
        )

    if request.method == "POST":
        new_status = request.POST.get(
            "status"
        )

        if (
            new_status in Ticket.Status.values
            and new_status != ticket.status
        ):
            old_status_label = (
                ticket.get_status_display()
            )

            ticket.status = new_status

            ticket.save(
                update_fields=["status"]
            )

            actor_label = (
                request.user.get_full_name()
                or request.user.username
            )

            TicketHistory.objects.create(
                ticket=ticket,
                actor=request.user,
                action=(
                    TicketHistory.Action.STATUS_CHANGED
                ),
                description=(
                    "Status changed from "
                    f"{old_status_label} to "
                    f"{ticket.get_status_display()} "
                    f"by {actor_label}."
                ),
            )

            messages.success(
                request,
                (
                    f"Ticket {ticket.ticket_number} "
                    "status updated."
                ),
            )

    return redirect(
        "ticket_detail",
        pk=ticket.pk,
    )


# =====================================================================
# UPDATE PRIORITY
# =====================================================================

@login_required
def ticket_update_priority(request, pk):
    ticket = get_object_or_404(
        Ticket,
        pk=pk,
    )

    if not (
        request.user.is_admin
        or request.user.has_role(RoleCode.SUPERVISOR)
        or ticket.assigned_to_id == request.user.id
    ):
        return HttpResponseForbidden(
            "You do not have permission to update this ticket."
        )

    if request.method == "POST":
        new_priority = request.POST.get(
            "priority"
        )

        if (
            new_priority in Ticket.Priority.values
            and new_priority != ticket.priority
        ):
            old_label = (
                ticket.get_priority_display()
            )

            ticket.priority = new_priority

            ticket.save(
                update_fields=["priority"]
            )

            actor_label = (
                request.user.get_full_name()
                or request.user.username
            )

            TicketHistory.objects.create(
                ticket=ticket,
                actor=request.user,
                action=(
                    TicketHistory.Action.PRIORITY_CHANGED
                ),
                description=(
                    "Priority changed from "
                    f"{old_label} to "
                    f"{ticket.get_priority_display()} "
                    f"by {actor_label}."
                ),
            )

            messages.success(
                request,
                (
                    f"Ticket {ticket.ticket_number} "
                    "priority updated."
                ),
            )

    return redirect(
        "ticket_detail",
        pk=ticket.pk,
    )


# =====================================================================
# UPDATE CATEGORY
# =====================================================================

@login_required
def ticket_update_category(request, pk):
    ticket = get_object_or_404(
        Ticket,
        pk=pk,
    )

    if not (
        request.user.is_admin
        or request.user.has_role(RoleCode.SUPERVISOR)
        or ticket.assigned_to_id == request.user.id
    ):
        return HttpResponseForbidden(
            "You do not have permission to update this ticket."
        )

    if request.method == "POST":
        category = get_object_or_404(
            TicketCategory.objects.filter(
                is_active=True
            ),
            pk=request.POST.get("category"),
        )

        if category.pk != ticket.category_id:
            old_label = (
                ticket.category.name
                if ticket.category
                else "None"
            )

            ticket.category = category
            ticket.department = category.department

            ticket.save(
                update_fields=[
                    "category",
                    "department",
                ]
            )

            actor_label = (
                request.user.get_full_name()
                or request.user.username
            )

            TicketHistory.objects.create(
                ticket=ticket,
                actor=request.user,
                action=(
                    TicketHistory.Action.CATEGORY_CHANGED
                ),
                description=(
                    "Category changed from "
                    f"{old_label} to "
                    f"{category.name} "
                    f"by {actor_label}."
                ),
            )

            messages.success(
                request,
                (
                    f"Ticket {ticket.ticket_number} "
                    "category updated."
                ),
            )

    return redirect(
        "ticket_detail",
        pk=ticket.pk,
    )


# =====================================================================
# RESOLVE TICKET
# =====================================================================

@login_required
def ticket_resolve(request, pk):
    ticket = get_object_or_404(
        Ticket,
        pk=pk,
    )

    if not (
        request.user.is_admin
        or request.user.has_role(RoleCode.SUPERVISOR)
        or ticket.assigned_to_id == request.user.id
    ):
        return HttpResponseForbidden(
            "You do not have permission to update this ticket."
        )

    if (
        request.method == "POST"
        and ticket.status != Ticket.Status.RESOLVED
    ):
        old_label = (
            ticket.get_status_display()
        )

        ticket.status = Ticket.Status.RESOLVED

        ticket.save(
            update_fields=["status"]
        )

        actor_label = (
            request.user.get_full_name()
            or request.user.username
        )

        TicketHistory.objects.create(
            ticket=ticket,
            actor=request.user,
            action=(
                TicketHistory.Action.STATUS_CHANGED
            ),
            description=(
                "Status changed from "
                f"{old_label} to Resolved "
                f"by {actor_label}."
            ),
        )

        messages.success(
            request,
            (
                f"Ticket {ticket.ticket_number} "
                "marked as resolved."
            ),
        )

    return redirect(
        "ticket_detail",
        pk=ticket.pk,
    )


# =====================================================================
# SUPERVISOR - TICKET MANAGEMENT
# =====================================================================

@supervisor_required
def supervisor_ticket_list(request):
    base = (
        Ticket.objects
        .select_related(
            "requester",
            "assigned_to",
            "department",
            "category",
        )
        .order_by("-created_at")
    )

    return render(
        request,
        "tickets/supervisor-ticket-list.html",
        {
            "unassigned_tickets": base.filter(
                assigned_to__isnull=True
            ),
            "assigned_tickets": base.filter(
                assigned_to__isnull=False
            ),
            "page_title": "Ticket Management",
        },
    )


# =====================================================================
# UNASSIGNED TICKETS
# =====================================================================

@agent_or_supervisor_required
def unassigned_ticket_list(request):
    tickets = (
        Ticket.objects
        .select_related(
            "requester",
            "department",
            "category",
        )
        .filter(
            assigned_to__isnull=True
        )
        .order_by("-created_at")
    )

    oldest = (
        tickets
        .order_by("created_at")
        .first()
    )

    oldest_days = (
        (
            timezone.now()
            - oldest.created_at
        ).days
        if oldest
        else None
    )

    return render(
        request,
        "queue/unassigned-tickets.html",
        {
            "tickets": tickets,
            "total_unassigned": tickets.count(),
            "oldest_unassigned_days": oldest_days,
            "oldest_unassigned_number": (
                oldest.ticket_number
                if oldest
                else None
            ),
            "critical_unassigned": tickets.filter(
                priority=Ticket.Priority.CRITICAL
            ).count(),
            "page_title": "Unassigned Tickets",
        },
    )


# =====================================================================
# ASSIGNED TICKETS
# =====================================================================

@agent_or_supervisor_required
def assigned_ticket_list(request):
    tickets = (
        Ticket.objects
        .select_related(
            "requester",
            "assigned_to",
            "department",
            "category",
        )
        .filter(
            assigned_to__isnull=False
        )
        .order_by("-created_at")
    )

    is_privileged = _is_supervisor_or_admin(
        request.user
    )

    open_statuses = (
        Ticket.Status.OPEN,
        Ticket.Status.IN_PROGRESS,
        Ticket.Status.WAITING_FOR_USER,
    )

    # -----------------------------------------------------------------
    # Supervisor / Admin
    # -----------------------------------------------------------------

    if is_privileged:
        return render(
            request,
            "queue/assigned-tickets.html",
            {
                "tickets": tickets,
                "total_assigned": tickets.count(),
                "open_among_assigned": (
                    tickets.filter(
                        status__in=open_statuses
                    ).count()
                ),
                "critical_assigned": (
                    tickets.filter(
                        priority=Ticket.Priority.CRITICAL
                    ).count()
                ),
                "page_title": "Assigned Tickets",
            },
        )

    # -----------------------------------------------------------------
    # Agent
    # -----------------------------------------------------------------

    tickets = tickets.filter(
        assigned_to=request.user
    )

    return render(
        request,
        "queue/assigned-to-me.html",
        {
            "tickets": tickets,
            "total_assigned": tickets.count(),
            "open_among_mine": (
                tickets.filter(
                    status__in=open_statuses
                ).count()
            ),
            "critical_among_mine": (
                tickets.filter(
                    priority=Ticket.Priority.CRITICAL
                ).count()
            ),
            "page_title": "Assigned to Me",
        },
    )


# =====================================================================
# ASSIGN TICKET
# =====================================================================

@agent_or_supervisor_required
def ticket_assign(request, pk):
    ticket = get_object_or_404(
        Ticket,
        pk=pk,
    )

    is_privileged = _is_supervisor_or_admin(
        request.user
    )

    # -----------------------------------------------------------------
    # POST
    # -----------------------------------------------------------------

    if request.method == "POST":

        if is_privileged:
            # Only allow an actual active Agent.
            agent = get_object_or_404(
                User.objects.filter(
                    user_roles__role__code=RoleCode.AGENT,
                    is_active=True,
                ).distinct(),
                pk=request.POST.get("agent"),
            )

        else:
            # Normal agent can assign to themselves.
            agent = request.user

        was_assigned_before = (
            ticket.assigned_to_id is not None
        )

        old_status_label = (
            ticket.get_status_display()
        )

        ticket.assigned_to = agent

        status_changed = False

        # Automatically move OPEN ticket to IN_PROGRESS.
        if ticket.status == Ticket.Status.OPEN:
            ticket.status = Ticket.Status.IN_PROGRESS
            status_changed = True

        ticket.save(
            update_fields=[
                "assigned_to",
                "status",
            ]
        )

        agent_label = (
            agent.get_full_name()
            or agent.username
        )

        actor_label = (
            request.user.get_full_name()
            or request.user.username
        )

        # -------------------------------------------------------------
        # Assignment history
        # -------------------------------------------------------------

        TicketHistory.objects.create(
            ticket=ticket,
            actor=request.user,
            action=(
                TicketHistory.Action.REASSIGNED
                if was_assigned_before
                else TicketHistory.Action.ASSIGNED
            ),
            description=(
                f"Assigned to {agent_label} "
                f"by {actor_label}."
            ),
        )

        # -------------------------------------------------------------
        # Status history
        # -------------------------------------------------------------

        if status_changed:
            TicketHistory.objects.create(
                ticket=ticket,
                actor=request.user,
                action=(
                    TicketHistory.Action.STATUS_CHANGED
                ),
                description=(
                    "Status changed from "
                    f"{old_status_label} to "
                    f"{ticket.get_status_display()} "
                    f"by {actor_label}."
                ),
            )

        messages.success(
            request,
            (
                f"Ticket {ticket.ticket_number} "
                f"assigned to {agent_label}."
            ),
        )

        return redirect(
            "supervisor_ticket_list"
            if is_privileged
            else "agent_ticket_list"
        )

    # -----------------------------------------------------------------
    # GET
    # -----------------------------------------------------------------

    agents = (
        User.objects
        .filter(
            user_roles__role__code=RoleCode.AGENT,
            is_active=True,
        )
        .distinct()
        .order_by(
            "first_name",
            "last_name",
            "username",
        )
    )

    return render(
        request,
        "tickets/ticket-assign.html",
        {
            "ticket": ticket,
            "agents": agents,
            "is_privileged": is_privileged,
            "page_title": (
                f"Assign {ticket.ticket_number}"
            ),
        },
    )


# =====================================================================
# UNASSIGN TICKET
# =====================================================================

@agent_or_supervisor_required
def ticket_unassign(request, pk):
    ticket = get_object_or_404(
        Ticket,
        pk=pk,
    )

    is_privileged = _is_supervisor_or_admin(
        request.user
    )

    # Normal agent can only unassign their own ticket.
    if (
        not is_privileged
        and ticket.assigned_to_id != request.user.id
    ):
        return HttpResponseForbidden(
            "You do not have permission to unassign this ticket."
        )

    if request.method == "POST":
        previous_agent = ticket.assigned_to

        ticket.assigned_to = None

        ticket.save(
            update_fields=[
                "assigned_to"
            ]
        )

        actor_label = (
            request.user.get_full_name()
            or request.user.username
        )

        if previous_agent:
            previous_agent_label = (
                previous_agent.get_full_name()
                or previous_agent.username
            )
        else:
            previous_agent_label = "no one"

        TicketHistory.objects.create(
            ticket=ticket,
            actor=request.user,
            action=(
                TicketHistory.Action.UNASSIGNED
            ),
            description=(
                f"Unassigned from "
                f"{previous_agent_label} "
                f"by {actor_label}."
            ),
        )

        messages.success(
            request,
            (
                f"Ticket {ticket.ticket_number} "
                "unassigned."
            ),
        )

    return redirect(
        "supervisor_ticket_list"
        if is_privileged
        else "agent_ticket_list"
    )


# =====================================================================
# AGENT - ALL TICKETS
# =====================================================================

@agent_required
def agent_ticket_list(request):
    tickets = (
        Ticket.objects
        .select_related(
            "requester",
            "assigned_to",
            "department",
            "category",
        )
        .order_by("-created_at")
    )

    tickets = _filter_tickets(
        request,
        tickets,
    )

    page_obj = _paginate(
        request,
        tickets,
    )

    context = {
        "tickets": page_obj,
        "page_obj": page_obj,
        "page_title": "All Tickets",
    }

    context.update(
        _ticket_list_filter_context(request)
    )

    return render(
        request,
        "tickets/ticket-table.html",
        context,
    )


# =====================================================================
# TICKET HISTORY
# =====================================================================

@login_required
def ticket_history(request, pk):
    ticket = get_object_or_404(
        Ticket,
        pk=pk,
    )

    # Requesters cannot see internal audit history.
    if not _is_agent_view(
        request.user
    ):
        return HttpResponseForbidden(
            "Ticket history is only available to staff."
        )

    if not _can_access_ticket(
        request.user,
        ticket,
    ):
        return HttpResponseForbidden(
            "You do not have permission to view this ticket's history."
        )

    history = (
        ticket.history
        .select_related("actor")
        .order_by("created_at")
    )

    back_url_name = "ticket_detail"

    action_icons = {
        TicketHistory.Action.CREATED:
            "bi-plus-circle text-bg-primary",

        TicketHistory.Action.ASSIGNED:
            "bi-person-check text-bg-primary",

        TicketHistory.Action.REASSIGNED:
            "bi-arrow-repeat text-bg-info",

        TicketHistory.Action.UNASSIGNED:
            "bi-person-dash text-bg-secondary",

        TicketHistory.Action.STATUS_CHANGED:
            "bi-arrow-up-square text-bg-warning",
    }

    events = [
        {
            "date": entry.created_at.date(),
            "time": entry.created_at,
            "icon": action_icons.get(
                entry.action,
                "bi-clock text-bg-secondary",
            ),
            "description": entry.description,
        }
        for entry in history
    ]

    return render(
        request,
        "tickets/ticket-history.html",
        {
            "ticket": ticket,
            "events": events,
            "back_url_name": back_url_name,
            "page_title": (
                f"History — "
                f"{ticket.ticket_number}"
            ),
        },
    )


# =====================================================================
# AGENT FAQ
# =====================================================================

@agent_required
def agent_faq_list(request):
    faqs = []

    return render(
        request,
        "tickets/agent-faqs.html",
        {
            "faqs": faqs,
            "page_title": "Suggested FAQs",
        },
    )


# =====================================================================
# DEPARTMENT QUEUE
# =====================================================================

@agent_or_supervisor_required
def department_queue_list(request):
    tickets = (
        Ticket.objects
        .select_related(
            "requester",
            "assigned_to",
            "department",
            "category",
        )
        .filter(
            department__isnull=False
        )
        .exclude(
            status__in=[
                Ticket.Status.RESOLVED,
                Ticket.Status.CLOSED,
            ]
        )
        .order_by(
            "department__name",
            "-created_at",
        )
    )

    # Supervisor/Admin see all departments.
    # Agent sees only their assigned tickets.
    if not _is_supervisor_or_admin(
        request.user
    ):
        tickets = tickets.filter(
            assigned_to=request.user
        )

    return render(
        request,
        "tickets/ticket-table.html",
        {
            "tickets": tickets,
            "page_title": "Department Queue",
        },
    )


# =====================================================================
# CRITICAL TICKETS
# =====================================================================

@agent_or_supervisor_required
def critical_ticket_list(request):
    tickets = (
        Ticket.objects
        .select_related(
            "requester",
            "assigned_to",
            "department",
            "category",
        )
        .filter(
            priority=Ticket.Priority.CRITICAL
        )
        .exclude(
            status__in=[
                Ticket.Status.RESOLVED,
                Ticket.Status.CLOSED,
            ]
        )
        .order_by("-created_at")
    )

    # Supervisor/Admin see all critical tickets.
    # Agent sees only their assigned critical tickets.
    if not _is_supervisor_or_admin(
        request.user
    ):
        tickets = tickets.filter(
            assigned_to=request.user
        )

    return render(
        request,
        "tickets/ticket-table.html",
        {
            "tickets": tickets,
            "page_title": "Critical Tickets",
        },
    )


# =====================================================================
# WAITING FOR USER
# =====================================================================

@agent_or_supervisor_required
def waiting_for_user_list(request):
    tickets = (
        Ticket.objects
        .select_related(
            "requester",
            "assigned_to",
            "department",
            "category",
        )
        .filter(
            status=Ticket.Status.WAITING_FOR_USER
        )
        .order_by("-updated_at")
    )

    # Supervisor/Admin see all.
    # Agent sees only their assigned tickets.
    if not _is_supervisor_or_admin(
        request.user
    ):
        tickets = tickets.filter(
            assigned_to=request.user
        )

    return render(
        request,
        "tickets/ticket-table.html",
        {
            "tickets": tickets,
            "page_title": "Waiting for User",
        },
    )


# =====================================================================
# RESOLVED / CLOSED
# =====================================================================

@agent_or_supervisor_required
def resolved_ticket_list(request):
    tickets = (
        Ticket.objects
        .select_related(
            "requester",
            "assigned_to",
            "department",
            "category",
        )
        .filter(
            status__in=[
                Ticket.Status.RESOLVED,
                Ticket.Status.CLOSED,
            ]
        )
        .order_by("-updated_at")
    )

    # Supervisor/Admin see all.
    # Agent sees only their assigned tickets.
    if not _is_supervisor_or_admin(
        request.user
    ):
        tickets = tickets.filter(
            assigned_to=request.user
        )

    return render(
        request,
        "tickets/ticket-table.html",
        {
            "tickets": tickets,
            "page_title": "Resolved / Closed Tickets",
        },
    )







# from django.contrib.auth import get_user_model
# from django.contrib.auth.decorators import login_required
# from django.shortcuts import render, redirect, get_object_or_404
# from django.contrib import messages
# from django.http import HttpResponseForbidden
# from django.utils import timezone
# from django.core.paginator import Paginator
# from django.db.models import Q

# from accounts.decorators import (
#     admin_required,
#     supervisor_required,
#     agent_required,
#     agent_or_supervisor_required,
# )
# from accounts.models import RoleCode
# from .models import Ticket, TicketAttachment, TicketHistory
# from classification.models import TicketCategory
# from .forms import TicketForm, TicketCommentForm, TicketAttachmentForm

# User = get_user_model()


# PAGE_SIZE = 5


# # ---------------------------------------------------------------------
# # TICKET FILTERS
# # ---------------------------------------------------------------------

# def _filter_tickets(request, tickets):
#     """
#     Complete Advanced Filters.

#     Supported GET parameters:
#         ticket_number
#         requester
#         assigned_agent
#         department
#         category
#         priority
#         status
#         created_date
#         updated_date
#         ai_confidence_min
#         ai_confidence_max
#         sentiment

#     Also keeps the old search parameter:
#         q
#     """

#     # -------------------------------------------------------------
#     # Search / Ticket #
#     # -------------------------------------------------------------

#     search = request.GET.get("q", "").strip()
#     ticket_number = request.GET.get("ticket_number", "").strip()

#     if search:
#         tickets = tickets.filter(
#             Q(ticket_number__icontains=search)
#             | Q(subject__icontains=search)
#             | Q(requester__first_name__icontains=search)
#             | Q(requester__last_name__icontains=search)
#             | Q(requester__username__icontains=search)
#         )

#     if ticket_number:
#         tickets = tickets.filter(
#             ticket_number__icontains=ticket_number
#         )

#     # -------------------------------------------------------------
#     # Requester
#     # -------------------------------------------------------------

#     requester = request.GET.get("requester", "").strip()

#     if requester.isdigit():
#         tickets = tickets.filter(requester_id=requester)

#     # -------------------------------------------------------------
#     # Assigned Agent
#     # -------------------------------------------------------------

#     assigned_agent = request.GET.get("assigned_agent", "").strip()

#     if assigned_agent == "unassigned":
#         tickets = tickets.filter(assigned_to__isnull=True)
#     elif assigned_agent.isdigit():
#         tickets = tickets.filter(assigned_to_id=assigned_agent)

#     # -------------------------------------------------------------
#     # Department
#     # -------------------------------------------------------------

#     department = request.GET.get("department", "").strip()

#     if department.isdigit():
#         tickets = tickets.filter(department_id=department)

#     # -------------------------------------------------------------
#     # Category
#     # -------------------------------------------------------------

#     category = request.GET.get("category", "").strip()

#     if category.isdigit():
#         tickets = tickets.filter(category_id=category)

#     # -------------------------------------------------------------
#     # Priority
#     # -------------------------------------------------------------

#     priority = request.GET.get("priority", "").strip()

#     if priority in Ticket.Priority.values:
#         tickets = tickets.filter(priority=priority)

#     # -------------------------------------------------------------
#     # Status
#     # -------------------------------------------------------------

#     status = request.GET.get("status", "").strip()

#     if status in Ticket.Status.values:
#         tickets = tickets.filter(status=status)

#     # -------------------------------------------------------------
#     # Created Date
#     # -------------------------------------------------------------

#     created_date = request.GET.get("created_date", "").strip()

#     if created_date:
#         tickets = tickets.filter(
#             created_at__date=created_date
#         )

#     # -------------------------------------------------------------
#     # Updated Date
#     # -------------------------------------------------------------

#     updated_date = request.GET.get("updated_date", "").strip()

#     if updated_date:
#         tickets = tickets.filter(
#             updated_at__date=updated_date
#         )

#     # -------------------------------------------------------------
#     # AI Confidence
#     # -------------------------------------------------------------

#     ai_confidence_min = request.GET.get(
#         "ai_confidence_min", ""
#     ).strip()

#     ai_confidence_max = request.GET.get(
#         "ai_confidence_max", ""
#     ).strip()

#     if ai_confidence_min:
#         try:
#             tickets = tickets.filter(
#                 ai_confidence__gte=float(ai_confidence_min)
#             )
#         except (ValueError, TypeError):
#             pass

#     if ai_confidence_max:
#         try:
#             tickets = tickets.filter(
#                 ai_confidence__lte=float(ai_confidence_max)
#             )
#         except (ValueError, TypeError):
#             pass

#     # -------------------------------------------------------------
#     # Sentiment
#     # -------------------------------------------------------------

#     sentiment = request.GET.get("sentiment", "").strip()

#     if sentiment:
#         tickets = tickets.filter(
#             sentiment__iexact=sentiment
#         )

#     return tickets


# # ---------------------------------------------------------------------
# # PAGINATION
# # ---------------------------------------------------------------------

# def _paginate(request, tickets, per_page=PAGE_SIZE):
#     paginator = Paginator(tickets, per_page)
#     page_number = request.GET.get("page", 1)

#     return paginator.get_page(page_number)


# # ---------------------------------------------------------------------
# # ADVANCED FILTER CONTEXT
# # ---------------------------------------------------------------------

# def _ticket_list_filter_context(request):
#     from organization.models import Department

#     query = request.GET.copy()
#     query.pop("page", None)

#     # Agents
#     agents = (
#         User.objects
#         .filter(
#             user_roles__role__code=RoleCode.AGENT,
#             is_active=True,
#         )
#         .distinct()
#         .order_by("first_name", "last_name", "username")
#     )

#     # Requesters
#     requesters = (
#         User.objects
#         .filter(
#             tickets_requested__isnull=False
#         )
#         .distinct()
#         .order_by("first_name", "last_name", "username")
#     )

#     # Departments
#     departments = (
#         Department.objects
#         .filter(is_active=True)
#         .order_by("name")
#     )

#     # Categories
#     categories = (
#         TicketCategory.objects
#         .filter(is_active=True)
#         .order_by("name")
#     )

#     # Sentiments
#     #
#     # These values are intentionally supplied from the model data
#     # instead of hard-coding only one AI implementation.
    
#     sentiments = [
#     "positive",
#     "neutral",
#     "negative",
# ]

#     return {
#         # Choices
#         "statuses": Ticket.Status.choices,
#         "priorities": Ticket.Priority.choices,

#         # Advanced filter options
#         "filter_requesters": requesters,
#         "filter_agents": agents,
#         "filter_departments": departments,
#         "filter_categories": categories,
#         "filter_sentiments": sentiments,

#         # Selected values
#         "selected_ticket_number": request.GET.get(
#             "ticket_number", ""
#         ),

#         "selected_requester": request.GET.get(
#             "requester", ""
#         ),

#         "selected_assigned_agent": request.GET.get(
#             "assigned_agent", ""
#         ),

#         "selected_status": request.GET.get(
#             "status", ""
#         ),

#         "selected_priority": request.GET.get(
#             "priority", ""
#         ),

#         "selected_department": request.GET.get(
#             "department", ""
#         ),

#         "selected_category": request.GET.get(
#             "category", ""
#         ),

#         "selected_created_date": request.GET.get(
#             "created_date", ""
#         ),

#         "selected_updated_date": request.GET.get(
#             "updated_date", ""
#         ),

#         "selected_ai_confidence_min": request.GET.get(
#             "ai_confidence_min", ""
#         ),

#         "selected_ai_confidence_max": request.GET.get(
#             "ai_confidence_max", ""
#         ),

#         "selected_sentiment": request.GET.get(
#             "sentiment", ""
#         ),

#         "search_query": request.GET.get(
#             "q", ""
#         ),

#         # Preserve all filters while changing pagination.
#         "base_query_string": query.urlencode(),
#     }


# # ---------------------------------------------------------------------
# # ACCESS CONTROL
# # ---------------------------------------------------------------------

# def _can_access_ticket(user, ticket):
#     """
#     Who may view/comment/attach on this ticket:

#     - Admin
#     - Requester who created it
#     - Agent assigned to it
#     - Supervisor
#     """

#     if user.is_admin:
#         return True

#     if ticket.requester_id == user.id:
#         return True

#     if ticket.assigned_to_id == user.id:
#         return True

#     if user.has_role(RoleCode.SUPERVISOR):
#         return True

#     return False


# def _is_agent_view(user):
#     return (
#         user.is_admin
#         or user.has_role(RoleCode.SUPERVISOR)
#         or user.has_role(RoleCode.AGENT)
#     )


# def _is_supervisor_or_admin(user):
#     return (
#         user.is_admin
#         or user.has_role(RoleCode.SUPERVISOR)
#     )


# # ---------------------------------------------------------------------
# # REQUESTER
# # ---------------------------------------------------------------------

# @login_required
# def ticket_list(request):
#     tickets = (
#         Ticket.objects
#         .filter(requester=request.user)
#         .select_related(
#             "assigned_to",
#             "department",
#             "category",
#         )
#         .order_by("-created_at")
#     )

#     return render(
#         request,
#         "tickets/my-tickets.html",
#         {
#             "tickets": tickets,
#             "page_title": "My Tickets",
#         },
#     )


# @login_required
# def ticket_create(request):
#     if request.method == "POST":
#         form = TicketForm(request.POST)

#         if form.is_valid():
#             ticket = form.save(commit=False)
#             ticket.requester = request.user
#             ticket.save()

#             TicketHistory.objects.create(
#                 ticket=ticket,
#                 actor=request.user,
#                 action=TicketHistory.Action.CREATED,
#                 description=(
#                     f"Ticket created by "
#                     f"{request.user.get_full_name() or request.user.username}."
#                 ),
#             )

#             for f in request.FILES.getlist("attachments"):
#                 TicketAttachment.objects.create(
#                     ticket=ticket,
#                     uploaded_by=request.user,
#                     file=f,
#                     original_filename=f.name,
#                     size_bytes=f.size,
#                 )

#             messages.success(
#                 request,
#                 f"Ticket {ticket.ticket_number} created successfully.",
#             )

#             return redirect("ticket_list")

#     else:
#         form = TicketForm()

#     return render(
#         request,
#         "tickets/create-ticket.html",
#         {
#             "form": form,
#             "page_title": "Create Ticket",
#         },
#     )


# # ---------------------------------------------------------------------
# # TICKET DETAIL
# # ---------------------------------------------------------------------

# @login_required
# def ticket_detail(request, pk):
#     ticket = get_object_or_404(Ticket, pk=pk)

#     if not _can_access_ticket(request.user, ticket):
#         return HttpResponseForbidden(
#             "You do not have permission to view this ticket."
#         )

#     comments = (
#         ticket.comments
#         .select_related("author")
#         .all()
#     )

#     context = {
#         "ticket": ticket,
#         "comments": comments,
#         "attachments": (
#             ticket.attachments
#             .select_related("uploaded_by")
#             .all()
#         ),
#         "history": (
#             ticket.history
#             .select_related("actor")
#             .all()
#         ),
#         "comment_form": TicketCommentForm(),
#         "attachment_form": TicketAttachmentForm(),
#         "page_title": ticket.ticket_number,
#     }

#     if _is_agent_view(request.user):
#         context["statuses"] = Ticket.Status.choices
#         context["priorities"] = Ticket.Priority.choices
#         context["categories"] = (
#             TicketCategory.objects
#             .filter(is_active=True)
#         )
#         context["is_own_ticket"] = (
#             ticket.assigned_to_id == request.user.id
#         )
#         context["public_comments"] = [
#             c for c in comments
#             if not c.is_internal
#         ]
#         context["internal_notes"] = [
#             c for c in comments
#             if c.is_internal
#         ]

#         return render(
#             request,
#             "tickets/ticket-detail-agent.html",
#             context,
#         )

#     context["comments"] = [
#         c for c in comments
#         if not c.is_internal
#     ]

#     return render(
#         request,
#         "tickets/ticket-detail-requester.html",
#         context,
#     )


# # ---------------------------------------------------------------------
# # COMMENTS
# # ---------------------------------------------------------------------

# @login_required
# def ticket_add_comment(request, pk):
#     ticket = get_object_or_404(Ticket, pk=pk)

#     if not _can_access_ticket(request.user, ticket):
#         return HttpResponseForbidden(
#             "You do not have permission to comment on this ticket."
#         )

#     if request.method == "POST":
#         form = TicketCommentForm(request.POST)

#         if form.is_valid():
#             comment = form.save(commit=False)
#             comment.ticket = ticket
#             comment.author = request.user

#             # Requesters can NEVER create internal notes.
#             if not _is_agent_view(request.user):
#                 comment.is_internal = False

#             comment.save()

#             actor_label = (
#                 request.user.get_full_name()
#                 or request.user.username
#             )

#             if comment.is_internal:
#                 TicketHistory.objects.create(
#                     ticket=ticket,
#                     actor=request.user,
#                     action=TicketHistory.Action.INTERNAL_NOTE,
#                     description=(
#                         f"Internal note added by {actor_label}."
#                     ),
#                 )

#                 messages.success(
#                     request,
#                     "Internal note added.",
#                 )

#             else:
#                 TicketHistory.objects.create(
#                     ticket=ticket,
#                     actor=request.user,
#                     action=TicketHistory.Action.PUBLIC_REPLY,
#                     description=(
#                         f"Reply added by {actor_label}."
#                     ),
#                 )

#                 messages.success(
#                     request,
#                     "Reply added.",
#                 )

#         else:
#             messages.error(
#                 request,
#                 "Reply could not be added. Please enter a message.",
#             )

#     if _is_agent_view(request.user):
#         return redirect(
#             "ticket_detail_requester",
#             pk=ticket.pk,
#         )

#     return redirect(
#         "ticket_detail_requester",
#         pk=ticket.pk,
#     )

# # ---------------------------------------------------------------------
# # ATTACHMENTS
# # ---------------------------------------------------------------------

# # ---------------------------------------------------------------------
# # ATTACHMENTS
# # ---------------------------------------------------------------------

# @login_required
# def ticket_add_attachment(request, pk):
#     ticket = get_object_or_404(Ticket, pk=pk)

#     if not _can_access_ticket(request.user, ticket):
#         return HttpResponseForbidden(
#             "You do not have permission to attach files to this ticket."
#         )

#     if request.method == "POST":
#         form = TicketAttachmentForm(
#             request.POST,
#             request.FILES,
#         )

#         if form.is_valid():
#             attachment = form.save(commit=False)

#             attachment.ticket = ticket
#             attachment.uploaded_by = request.user

#             uploaded_file = form.cleaned_data["file"]

#             attachment.original_filename = uploaded_file.name
#             attachment.size_bytes = uploaded_file.size

#             attachment.save()

#             actor_label = (
#                 request.user.get_full_name()
#                 or request.user.username
#             )

#             TicketHistory.objects.create(
#                 ticket=ticket,
#                 actor=request.user,
#                 action=TicketHistory.Action.ATTACHMENT_ADDED,
#                 description=(
#                     f"Attachment '{attachment.original_filename}' "
#                     f"uploaded by {actor_label}."
#                 ),
#             )

#             messages.success(
#                 request,
#                 "Attachment uploaded successfully.",
#             )

#         else:
#             error_text = " ".join(
#                 str(error)
#                 for errors in form.errors.values()
#                 for error in errors
#             ) or "File could not be uploaded."

#             messages.error(
#                 request,
#                 error_text,
#             )

#     return redirect(
#         "ticket_detail_requester",
#         pk=ticket.pk,
#     )



# # ---------------------------------------------------------------------
# # ADMIN
# # ---------------------------------------------------------------------

# @admin_required
# def admin_ticket_list(request):
#     tickets = (
#         Ticket.objects
#         .select_related(
#             "requester",
#             "assigned_to",
#             "department",
#             "category",
#         )
#         .order_by("-created_at")
#     )

#     tickets = _filter_tickets(
#         request,
#         tickets,
#     )

#     page_obj = _paginate(
#         request,
#         tickets,
#     )

#     context = {
#         "tickets": page_obj,
#         "page_obj": page_obj,
#         "page_title": "All Tickets",
#     }

#     context.update(
#         _ticket_list_filter_context(request)
#     )

#     return render(
#         request,
#         "tickets/ticket-table.html",
#         context,
#     )


# # ---------------------------------------------------------------------
# # UPDATE STATUS
# # ---------------------------------------------------------------------

# @login_required
# def ticket_update_status(request, pk):
#     ticket = get_object_or_404(Ticket, pk=pk)

#     if not (
#         request.user.is_admin
#         or request.user.has_role(RoleCode.SUPERVISOR)
#         or ticket.assigned_to_id == request.user.id
#     ):
#         return HttpResponseForbidden(
#             "You do not have permission to update this ticket."
#         )

#     if request.method == "POST":
#         new_status = request.POST.get("status")

#         if (
#             new_status in Ticket.Status.values
#             and new_status != ticket.status
#         ):
#             old_status_label = ticket.get_status_display()

#             ticket.status = new_status
#             ticket.save(update_fields=["status"])

#             TicketHistory.objects.create(
#                 ticket=ticket,
#                 actor=request.user,
#                 action=TicketHistory.Action.STATUS_CHANGED,
#                 description=(
#                     f"Status changed from "
#                     f"{old_status_label} to "
#                     f"{ticket.get_status_display()} "
#                     f"by "
#                     f"{request.user.get_full_name() or request.user.username}."
#                 ),
#             )

#             messages.success(
#                 request,
#                 f"Ticket {ticket.ticket_number} status updated.",
#             )

#     if _is_agent_view(request.user):
#      return redirect(
#         "ticket_detail_requester",
#         pk=ticket.pk,
#     )

#     return redirect(
#     "ticket_detail_requester",
#     pk=ticket.pk,
# )


# # # ---------------------------------------------------------------------
# # # UPDATE PRIORITY
# # # ---------------------------------------------------------------------

# @login_required
# def ticket_update_priority(request, pk):
#     ticket = get_object_or_404(Ticket, pk=pk)

#     if not (
#         request.user.is_admin
#         or request.user.has_role(RoleCode.SUPERVISOR)
#         or ticket.assigned_to_id == request.user.id
#     ):
#         return HttpResponseForbidden(
#             "You do not have permission to update this ticket."
#         )

#     if request.method == "POST":
#         new_priority = request.POST.get("priority")

#         if (
#             new_priority in Ticket.Priority.values
#             and new_priority != ticket.priority
#         ):
#             old_label = ticket.get_priority_display()

#             ticket.priority = new_priority
#             ticket.save(update_fields=["priority"])

#             TicketHistory.objects.create(
#                 ticket=ticket,
#                 actor=request.user,
#                action=TicketHistory.Action.PRIORITY_CHANGED,
#                 description=(
#                     f"Priority changed from "
#                     f"{old_label} to "
#                     f"{ticket.get_priority_display()} "
#                     f"by "
#                     f"{request.user.get_full_name() or request.user.username}."
#                 ),
#             )

#             messages.success(
#                 request,
#                 f"Ticket {ticket.ticket_number} priority updated.",
#             )

#     if _is_agent_view(request.user):
#      return redirect(
#         "ticket_detail_requester",
#         pk=ticket.pk,
#     )

#     return redirect(
#     "ticket_detail_requester",
#     pk=ticket.pk,
# )

# # ---------------------------------------------------------------------
# # UPDATE CATEGORY
# # ---------------------------------------------------------------------

# @login_required
# def ticket_update_category(request, pk):
#     ticket = get_object_or_404(Ticket, pk=pk)

#     if not (
#         request.user.is_admin
#         or request.user.has_role(RoleCode.SUPERVISOR)
#         or ticket.assigned_to_id == request.user.id
#     ):
#         return HttpResponseForbidden(
#             "You do not have permission to update this ticket."
#         )

#     if request.method == "POST":
#         category = get_object_or_404(
#             TicketCategory,
#             pk=request.POST.get("category"),
#         )

#         if category.pk != ticket.category_id:
#             old_label = (
#                 ticket.category.name
#                 if ticket.category
#                 else "None"
#             )

#             ticket.category = category
#             ticket.department = category.department

#             ticket.save(
#                 update_fields=[
#                     "category",
#                     "department",
#                 ]
#             )

#             TicketHistory.objects.create(
#                 ticket=ticket,
#                 actor=request.user,
#                action=TicketHistory.Action.CATEGORY_CHANGED,
#                 description=(
#                     f"Category changed from "
#                     f"{old_label} to {category.name} "
#                     f"by "
#                     f"{request.user.get_full_name() or request.user.username}."
#                 ),
#             )

#             messages.success(
#                 request,
#                 f"Ticket {ticket.ticket_number} category updated.",
#             )

#     if _is_agent_view(request.user):
#       return redirect(
#         "ticket_detail_requester",
#         pk=ticket.pk,
#     )

#     return redirect(
#     "ticket_detail_requester",
#     pk=ticket.pk,
# )


# # ---------------------------------------------------------------------
# # RESOLVE
# # ---------------------------------------------------------------------

# @login_required
# def ticket_resolve(request, pk):
#     ticket = get_object_or_404(Ticket, pk=pk)

#     if not (
#         request.user.is_admin
#         or request.user.has_role(RoleCode.SUPERVISOR)
#         or ticket.assigned_to_id == request.user.id
#     ):
#         return HttpResponseForbidden(
#             "You do not have permission to update this ticket."
#         )

#     if (
#         request.method == "POST"
#         and ticket.status != Ticket.Status.RESOLVED
#     ):
#         old_label = ticket.get_status_display()

#         ticket.status = Ticket.Status.RESOLVED
#         ticket.save(update_fields=["status"])

#         TicketHistory.objects.create(
#             ticket=ticket,
#             actor=request.user,
#             action=TicketHistory.Action.STATUS_CHANGED,
#             description=(
#                 f"Status changed from "
#                 f"{old_label} to Resolved "
#                 f"by "
#                 f"{request.user.get_full_name() or request.user.username}."
#             ),
#         )

#         messages.success(
#             request,
#             f"Ticket {ticket.ticket_number} marked as resolved.",
#         )

#     if _is_agent_view(request.user):
#      return redirect(
#         "ticket_detail_requester",
#         pk=ticket.pk,
#     )

#     return redirect(
#     "ticket_detail_requester",
#     pk=ticket.pk,
# )

# # ---------------------------------------------------------------------
# # SUPERVISOR
# # ---------------------------------------------------------------------

# @supervisor_required
# def supervisor_ticket_list(request):
#     base = (
#         Ticket.objects
#         .select_related(
#             "requester",
#             "assigned_to",
#             "department",
#             "category",
#         )
#         .order_by("-created_at")
#     )

#     return render(
#         request,
#         "tickets/supervisor-ticket-list.html",
#         {
#             "unassigned_tickets": base.filter(
#                 assigned_to__isnull=True
#             ),
#             "assigned_tickets": base.filter(
#                 assigned_to__isnull=False
#             ),
#             "page_title": "Ticket Management",
#         },
#     )


# # ---------------------------------------------------------------------
# # UNASSIGNED
# # ---------------------------------------------------------------------

# @agent_or_supervisor_required
# def unassigned_ticket_list(request):
#     tickets = (
#         Ticket.objects
#         .select_related(
#             "requester",
#             "department",
#             "category",
#         )
#         .filter(assigned_to__isnull=True)
#         .order_by("-created_at")
#     )

#     oldest = tickets.order_by("created_at").first()

#     oldest_days = (
#         (timezone.now() - oldest.created_at).days
#         if oldest
#         else None
#     )

#     return render(
#         request,
#         "queue/unassigned-tickets.html",
#         {
#             "tickets": tickets,
#             "total_unassigned": tickets.count(),
#             "oldest_unassigned_days": oldest_days,
#             "oldest_unassigned_number": (
#                 oldest.ticket_number
#                 if oldest
#                 else None
#             ),
#             "critical_unassigned": tickets.filter(
#                 priority=Ticket.Priority.CRITICAL
#             ).count(),
#             "page_title": "Unassigned Tickets",
#         },
#     )


# # ---------------------------------------------------------------------
# # ASSIGNED
# # ---------------------------------------------------------------------

# @agent_or_supervisor_required
# def assigned_ticket_list(request):
#     tickets = (
#         Ticket.objects
#         .select_related(
#             "requester",
#             "assigned_to",
#             "department",
#             "category",
#         )
#         .filter(assigned_to__isnull=False)
#         .order_by("-created_at")
#     )

#     is_privileged = _is_supervisor_or_admin(
#         request.user
#     )

#     open_statuses = (
#         Ticket.Status.OPEN,
#         Ticket.Status.IN_PROGRESS,
#         Ticket.Status.WAITING_FOR_USER,
#     )

#     if is_privileged:
#         return render(
#             request,
#             "queue/assigned-tickets.html",
#             {
#                 "tickets": tickets,
#                 "total_assigned": tickets.count(),
#                 "open_among_assigned": tickets.filter(
#                     status__in=open_statuses
#                 ).count(),
#                 "critical_assigned": tickets.filter(
#                     priority=Ticket.Priority.CRITICAL
#                 ).count(),
#                 "page_title": "Assigned Tickets",
#             },
#         )

#     tickets = tickets.filter(
#         assigned_to=request.user
#     )

#     return render(
#         request,
#         "queue/assigned-to-me.html",
#         {
#             "tickets": tickets,
#             "total_assigned": tickets.count(),
#             "open_among_mine": tickets.filter(
#                 status__in=open_statuses
#             ).count(),
#             "critical_among_mine": tickets.filter(
#                 priority=Ticket.Priority.CRITICAL
#             ).count(),
#             "page_title": "Assigned to Me",
#         },
#     )


# # ---------------------------------------------------------------------
# # ASSIGN
# # ---------------------------------------------------------------------

# @agent_or_supervisor_required
# def ticket_assign(request, pk):
#     ticket = get_object_or_404(Ticket, pk=pk)

#     is_privileged = _is_supervisor_or_admin(
#         request.user
#     )

#     if request.method == "POST":

#         if is_privileged:
#             agent = get_object_or_404(
#                 User,
#                 pk=request.POST.get("agent"),
#             )
#         else:
#             agent = request.user

#         was_assigned_before = (
#             ticket.assigned_to_id is not None
#         )

#         old_status_label = ticket.get_status_display()

#         ticket.assigned_to = agent

#         status_changed = False

#         if ticket.status == Ticket.Status.OPEN:
#             ticket.status = Ticket.Status.IN_PROGRESS
#             status_changed = True

#         ticket.save(
#             update_fields=[
#                 "assigned_to",
#                 "status",
#             ]
#         )

#         agent_label = (
#             agent.get_full_name()
#             or agent.username
#         )

#         actor_label = (
#             request.user.get_full_name()
#             or request.user.username
#         )

#         TicketHistory.objects.create(
#             ticket=ticket,
#             actor=request.user,
#             action=(
#                 TicketHistory.Action.REASSIGNED
#                 if was_assigned_before
#                 else TicketHistory.Action.ASSIGNED
#             ),
#             description=(
#                 f"Assigned to {agent_label} "
#                 f"by {actor_label}."
#             ),
#         )

#         if status_changed:
#             TicketHistory.objects.create(
#                 ticket=ticket,
#                 actor=request.user,
#                 action=TicketHistory.Action.STATUS_CHANGED,
#                 description=(
#                     f"Status changed from "
#                     f"{old_status_label} to "
#                     f"{ticket.get_status_display()} "
#                     f"by {actor_label}."
#                 ),
#             )

#         messages.success(
#             request,
#             f"Ticket {ticket.ticket_number} assigned to {agent_label}.",
#         )

#         return redirect(
#             "supervisor_ticket_list"
#             if is_privileged
#             else "agent_ticket_list"
#         )

#     agents = (
#         User.objects
#         .filter(
#             user_roles__role__code=RoleCode.AGENT,
#             is_active=True,
#         )
#         .distinct()
#     )

#     return render(
#         request,
#         "tickets/ticket-assign.html",
#         {
#             "ticket": ticket,
#             "agents": agents,
#             "is_privileged": is_privileged,
#             "page_title": f"Assign {ticket.ticket_number}",
#         },
#     )


# # ---------------------------------------------------------------------
# # UNASSIGN
# # ---------------------------------------------------------------------

# @agent_or_supervisor_required
# def ticket_unassign(request, pk):
#     ticket = get_object_or_404(Ticket, pk=pk)

#     is_privileged = _is_supervisor_or_admin(
#         request.user
#     )

#     if (
#         not is_privileged
#         and ticket.assigned_to_id != request.user.id
#     ):
#         return HttpResponseForbidden(
#             "You do not have permission to unassign this ticket."
#         )

#     if request.method == "POST":
#         previous_agent = ticket.assigned_to

#         ticket.assigned_to = None
#         ticket.save(
#             update_fields=["assigned_to"]
#         )

#         actor_label = (
#             request.user.get_full_name()
#             or request.user.username
#         )

#         prev_label = (
#             (
#                 previous_agent.get_full_name()
#                 or previous_agent.username
#             )
#             if previous_agent
#             else "no one"
#         )

#         TicketHistory.objects.create(
#             ticket=ticket,
#             actor=request.user,
#             action=TicketHistory.Action.UNASSIGNED,
#             description=(
#                 f"Unassigned from {prev_label} "
#                 f"by {actor_label}."
#             ),
#         )

#         messages.success(
#             request,
#             f"Ticket {ticket.ticket_number} unassigned.",
#         )

#     return redirect(
#         "supervisor_ticket_list"
#         if is_privileged
#         else "agent_ticket_list"
#     )


# # ---------------------------------------------------------------------
# # AGENT TICKET LIST
# # ---------------------------------------------------------------------

# @agent_required
# def agent_ticket_list(request):
#     tickets = (
#         Ticket.objects
#         .select_related(
#             "requester",
#             "assigned_to",
#             "department",
#             "category",
#         )
#         .order_by("-created_at")
#     )

#     tickets = _filter_tickets(
#         request,
#         tickets,
#     )

#     page_obj = _paginate(
#         request,
#         tickets,
#     )

#     context = {
#         "tickets": page_obj,
#         "page_obj": page_obj,
#         "page_title": "All Tickets",
#     }

#     context.update(
#         _ticket_list_filter_context(request)
#     )

#     return render(
#         request,
#         "tickets/ticket-table.html",
#         context,
#     )


# # ---------------------------------------------------------------------
# # HISTORY
# # ---------------------------------------------------------------------

# @login_required
# def ticket_history(request, pk):
#     ticket = get_object_or_404(Ticket, pk=pk)

#      # Requesters must not see the internal audit history.
#     if not _is_agent_view(request.user):
#         return HttpResponseForbidden(
#             "Ticket history is only available to staff."
#         )

#     if not _can_access_ticket(request.user, ticket):
#         return HttpResponseForbidden(
#             "You do not have permission to view this ticket's history."
#         )

#     history = (
#         ticket.history
#         .select_related("actor")
#         .order_by("created_at")
#     )

#     back_url_name = "ticket_detail_requester"

#     action_icons = {
#         TicketHistory.Action.CREATED:
#             "bi-plus-circle text-bg-primary",

#         TicketHistory.Action.ASSIGNED:
#             "bi-person-check text-bg-primary",

#         TicketHistory.Action.REASSIGNED:
#             "bi-arrow-repeat text-bg-info",

#         TicketHistory.Action.UNASSIGNED:
#             "bi-person-dash text-bg-secondary",

#         TicketHistory.Action.STATUS_CHANGED:
#             "bi-arrow-up-square text-bg-warning",
#     }

#     events = [
#         {
#             "date": entry.created_at.date(),
#             "time": entry.created_at,
#             "icon": action_icons.get(
#                 entry.action,
#                 "bi-clock text-bg-secondary",
#             ),
#             "description": entry.description,
#         }
#         for entry in history
#     ]

#     return render(
#         request,
#         "tickets/ticket-history.html",
#         {
#             "ticket": ticket,
#             "events": events,
#             "back_url_name": back_url_name,
#             "page_title": (
#                 f"History — {ticket.ticket_number}"
#             ),
#         },
#     )


# # ---------------------------------------------------------------------
# # AGENT FAQ
# # ---------------------------------------------------------------------

# @agent_required
# def agent_faq_list(request):
#     faqs = []

#     return render(
#         request,
#         "tickets/agent-faqs.html",
#         {
#             "faqs": faqs,
#             "page_title": "Suggested FAQs",
#         },
#     )


# # ---------------------------------------------------------------------
# # DEPARTMENT QUEUE
# # ---------------------------------------------------------------------

# @agent_or_supervisor_required
# def department_queue_list(request):
#     tickets = (
#         Ticket.objects
#         .select_related(
#             "requester",
#             "assigned_to",
#             "department",
#             "category",
#         )
#         .filter(department__isnull=False)
#         .exclude(
#             status__in=[
#                 Ticket.Status.RESOLVED,
#                 Ticket.Status.CLOSED,
#             ]
#         )
#         .order_by(
#             "department__name",
#             "-created_at",
#         )
#     )

#     if not _is_supervisor_or_admin(request.user):
#         tickets = tickets.filter(
#             assigned_to=request.user
#         )

#     return render(
#         request,
#         "tickets/ticket-table.html",
#         {
#             "tickets": tickets,
#             "page_title": "Department Queue",
#         },
#     )


# # ---------------------------------------------------------------------
# # CRITICAL TICKETS
# # ---------------------------------------------------------------------

# @agent_or_supervisor_required
# def critical_ticket_list(request):
#     tickets = (
#         Ticket.objects
#         .select_related(
#             "requester",
#             "assigned_to",
#             "department",
#             "category",
#         )
#         .filter(
#             priority=Ticket.Priority.CRITICAL
#         )
#         .exclude(
#             status__in=[
#                 Ticket.Status.RESOLVED,
#                 Ticket.Status.CLOSED,
#             ]
#         )
#         .order_by("-created_at")
#     )

#     if not _is_supervisor_or_admin(request.user):
#         tickets = tickets.filter(
#             assigned_to=request.user
#         )

#     return render(
#         request,
#         "tickets/ticket-table.html",
#         {
#             "tickets": tickets,
#             "page_title": "Critical Tickets",
#         },
#     )


# # ---------------------------------------------------------------------
# # WAITING FOR USER
# # ---------------------------------------------------------------------

# @agent_or_supervisor_required
# def waiting_for_user_list(request):
#     tickets = (
#         Ticket.objects
#         .select_related(
#             "requester",
#             "assigned_to",
#             "department",
#             "category",
#         )
#         .filter(
#             status=Ticket.Status.WAITING_FOR_USER
#         )
#         .order_by("-updated_at")
#     )

#     if not _is_supervisor_or_admin(request.user):
#         tickets = tickets.filter(
#             assigned_to=request.user
#         )

#     return render(
#         request,
#         "tickets/ticket-table.html",
#         {
#             "tickets": tickets,
#             "page_title": "Waiting for User",
#         },
#     )


# # ---------------------------------------------------------------------
# # RESOLVED / CLOSED
# # ---------------------------------------------------------------------

# @agent_or_supervisor_required
# def resolved_ticket_list(request):
#     tickets = (
#         Ticket.objects
#         .select_related(
#             "requester",
#             "assigned_to",
#             "department",
#             "category",
#         )
#         .filter(
#             status__in=[
#                 Ticket.Status.RESOLVED,
#                 Ticket.Status.CLOSED,
#             ]
#         )
#         .order_by("-updated_at")
#     )

#     if not _is_supervisor_or_admin(request.user):
#         tickets = tickets.filter(
#             assigned_to=request.user
#         )

#     return render(
#         request,
#         "tickets/ticket-table.html",
#         {
#             "tickets": tickets,
#             "page_title": "Resolved / Closed Tickets",
#         },
#     )