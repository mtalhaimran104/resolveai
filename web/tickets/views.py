from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponseForbidden

from accounts.decorators import admin_required, supervisor_required, agent_required
from accounts.models import RoleCode
from .models import Ticket, TicketAttachment, TicketHistory
from .forms import TicketForm, TicketCommentForm, TicketAttachmentForm

User = get_user_model()


def _can_access_ticket(user, ticket):
    """Who may view/comment/attach on this ticket:
    the requester who filed it, the agent it's assigned to,
    any supervisor, or an admin (superuser)."""
    if user.is_superuser:
        return True
    if ticket.requester_id == user.id:
        return True
    if ticket.assigned_to_id == user.id:
        return True
    if user.has_role(RoleCode.SUPERVISOR):
        return True
    return False


# ---------------------------------------------------------------------
# REQUESTER
# ---------------------------------------------------------------------

@login_required
def ticket_list(request):
    tickets = Ticket.objects.filter(requester=request.user).select_related(
        "assigned_to", "department", "category"
    ).order_by("-created_at")
    return render(request, "tickets/my-tickets.html", {
        "tickets": tickets,
        "page_title": "My Tickets",
    })


@login_required
def ticket_create(request):
    if request.method == "POST":
        form = TicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.requester = request.user
            ticket.save()

            TicketHistory.objects.create(
                ticket=ticket,
                actor=request.user,
                action=TicketHistory.Action.CREATED,
                description=f"Ticket created by {request.user.get_full_name() or request.user.username}.",
            )

            for f in request.FILES.getlist("attachments"):
                TicketAttachment.objects.create(
                    ticket=ticket,
                    uploaded_by=request.user,
                    file=f,
                    original_filename=f.name,
                    size_bytes=f.size,
                )

            messages.success(request, f"Ticket {ticket.ticket_number} created successfully.")
            return redirect("my_tickets")
    else:
        form = TicketForm()
    return render(request, "tickets/create-ticket.html", {
        "form": form,
        "page_title": "Create Ticket",
    })


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if not _can_access_ticket(request.user, ticket):
        return HttpResponseForbidden("You do not have permission to view this ticket.")

    return render(request, "tickets/ticket-detail-requester.html", {
        "ticket": ticket,
        "comments": ticket.comments.select_related("author").all(),
        "attachments": ticket.attachments.select_related("uploaded_by").all(),
        "history": ticket.history.select_related("actor").all(),
        "comment_form": TicketCommentForm(),
        "attachment_form": TicketAttachmentForm(),
        "page_title": ticket.ticket_number,
    })


@login_required
def ticket_add_comment(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if not _can_access_ticket(request.user, ticket):
        return HttpResponseForbidden("You do not have permission to comment on this ticket.")

    if request.method == "POST":
        form = TicketCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.ticket = ticket
            comment.author = request.user
            comment.save()
            messages.success(request, "Reply added.")
        else:
            messages.error(request, "Reply could not be added. Please enter a message.")
    return redirect("ticket_detail_requester", pk=ticket.pk)


@login_required
def ticket_add_attachment(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if not _can_access_ticket(request.user, ticket):
        return HttpResponseForbidden("You do not have permission to attach files to this ticket.")

    if request.method == "POST":
        form = TicketAttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            attachment = form.save(commit=False)
            attachment.ticket = ticket
            attachment.uploaded_by = request.user
            attachment.original_filename = form.cleaned_data["file"].name
            attachment.size_bytes = form.cleaned_data["file"].size
            attachment.save()
            messages.success(request, "Attachment uploaded.")
        else:
            error_text = " ".join(
                str(e) for errs in form.errors.values() for e in errs
            ) or "File could not be uploaded."
            messages.error(request, error_text)
    return redirect("ticket_detail_requester", pk=ticket.pk)


# ---------------------------------------------------------------------
# ADMIN
# ---------------------------------------------------------------------

@admin_required
def admin_ticket_list(request):
    tickets = Ticket.objects.select_related(
        "requester", "assigned_to", "department", "category"
    ).all()
    return render(request, "tickets/ticket-table.html", {
        "tickets": tickets,
        "page_title": "All Tickets",
    })


@admin_required
def ticket_update_status(request, pk):
    if request.method == "POST":
        ticket = get_object_or_404(Ticket, pk=pk)
        new_status = request.POST.get("status")
        if new_status in Ticket.Status.values and new_status != ticket.status:
            old_status_label = ticket.get_status_display()
            ticket.status = new_status
            ticket.save(update_fields=["status"])
            TicketHistory.objects.create(
                ticket=ticket,
                actor=request.user,
                action=TicketHistory.Action.STATUS_CHANGED,
                description=f"Status changed from {old_status_label} to {ticket.get_status_display()} by {request.user.get_full_name() or request.user.username}.",
            )
            messages.success(request, f"Ticket {ticket.ticket_number} status updated.")
    return redirect("admin_ticket_list")


# ---------------------------------------------------------------------
# SUPERVISOR
# ---------------------------------------------------------------------

@supervisor_required
def supervisor_ticket_list(request):
    base = Ticket.objects.select_related(
        "requester", "assigned_to", "department", "category"
    ).order_by("-created_at")
    return render(request, "tickets/supervisor-ticket-list.html", {
        "unassigned_tickets": base.filter(assigned_to__isnull=True),
        "assigned_tickets": base.filter(assigned_to__isnull=False),
        "page_title": "Ticket Management",
    })


@supervisor_required
def unassigned_ticket_list(request):
    tickets = Ticket.objects.select_related("requester", "department", "category") \
        .filter(assigned_to__isnull=True).order_by("-created_at")
    return render(request, "tickets/ticket-table.html", {
        "tickets": tickets,
        "page_title": "Unassigned Tickets",
    })


@supervisor_required
def assigned_ticket_list(request):
    tickets = Ticket.objects.select_related("requester", "assigned_to", "department", "category") \
        .filter(assigned_to__isnull=False).order_by("-created_at")
    return render(request, "tickets/ticket-table.html", {
        "tickets": tickets,
        "page_title": "Assigned Tickets",
    })


@supervisor_required
def ticket_assign(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if request.method == "POST":
        agent = get_object_or_404(User, pk=request.POST.get("agent"))
        was_assigned_before = ticket.assigned_to_id is not None
        old_status_label = ticket.get_status_display()

        ticket.assigned_to = agent
        status_changed = False
        if ticket.status == Ticket.Status.OPEN:
            ticket.status = Ticket.Status.IN_PROGRESS
            status_changed = True
        ticket.save(update_fields=["assigned_to", "status"])

        agent_label = agent.get_full_name() or agent.username
        actor_label = request.user.get_full_name() or request.user.username
        TicketHistory.objects.create(
            ticket=ticket,
            actor=request.user,
            action=TicketHistory.Action.REASSIGNED if was_assigned_before else TicketHistory.Action.ASSIGNED,
            description=f"Assigned to {agent_label} by {actor_label}.",
        )
        if status_changed:
            TicketHistory.objects.create(
                ticket=ticket,
                actor=request.user,
                action=TicketHistory.Action.STATUS_CHANGED,
                description=f"Status changed from {old_status_label} to {ticket.get_status_display()} by {actor_label}.",
            )

        messages.success(request, f"Ticket {ticket.ticket_number} assigned to {agent_label}.")
        return redirect("supervisor_ticket_list")

    agents = User.objects.filter(user_roles__role__code=RoleCode.AGENT, is_active=True).distinct()
    return render(request, "tickets/ticket-assign.html", {
        "ticket": ticket,
        "agents": agents,
        "page_title": f"Assign {ticket.ticket_number}",
    })


# ---------------------------------------------------------------------
# AGENT
# ---------------------------------------------------------------------

@agent_required
def agent_ticket_list(request):
    tickets = Ticket.objects.select_related("requester", "department", "category") \
        .filter(assigned_to=request.user).order_by("-created_at")
    return render(request, "tickets/ticket-table.html", {
        "tickets": tickets,
        "page_title": "My Assigned Tickets",
    })


@agent_required
def agent_faq_list(request):
    faqs = []  # placeholder — no AI integration yet
    return render(request, "tickets/agent-faqs.html", {
        "faqs": faqs,
        "page_title": "Suggested FAQs",
    })