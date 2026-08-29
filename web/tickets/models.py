from django.db import models
from django.conf import settings
from django.utils import timezone

from core.models import TimeStampedModel
from organization.models import Department
from classification.models import TicketCategory


class Ticket(TimeStampedModel):
    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        WAITING_FOR_USER = "WAITING_FOR_USER", "Waiting for User"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    class Sentiment(models.TextChoices):
        POSITIVE = "POSITIVE", "Positive"
        NEUTRAL = "NEUTRAL", "Neutral"
        NEGATIVE = "NEGATIVE", "Negative"

    ticket_number = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
    )

    subject = models.CharField(max_length=255)

    description = models.TextField()

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets_requested",
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="tickets_assigned",
        null=True,
        blank=True,
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        related_name="tickets",
        null=True,
        blank=True,
    )

    category = models.ForeignKey(
        TicketCategory,
        on_delete=models.SET_NULL,
        related_name="tickets",
        null=True,
        blank=True,
    )

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )

    ai_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="AI classification confidence percentage (0-100).",
    )

    sentiment = models.CharField(
        max_length=20,
        choices=Sentiment.choices,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "tickets"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ticket_number} - {self.subject}"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            year = timezone.now().year

            last = (
                Ticket.objects
                .filter(ticket_number__startswith=f"RA-{year}-")
                .order_by("-ticket_number")
                .first()
            )

            last_seq = (
                int(last.ticket_number.split("-")[-1])
                if last
                else 0
            )

            self.ticket_number = f"RA-{year}-{last_seq + 1:06d}"

        super().save(*args, **kwargs)


def ticket_attachment_upload_path(instance, filename):
    return f"ticket_attachments/{instance.ticket_id}/{filename}"


class TicketComment(TimeStampedModel):
    """Conversation messages and internal notes."""

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="comments",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ticket_comments",
    )

    message = models.TextField()

    is_internal = models.BooleanField(
        default=False,
        blank=True,
        help_text=(
            "Internal notes are visible to agents, supervisors and "
            "admins only. Requesters must never see them."
        ),
    )

    class Meta:
        db_table = "ticket_comments"
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author} on {self.ticket.ticket_number}"


class TicketAttachment(TimeStampedModel):
    """Files attached to a ticket."""

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="attachments",
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ticket_attachments",
    )

    file = models.FileField(
        upload_to=ticket_attachment_upload_path,
    )

    original_filename = models.CharField(
        max_length=255,
    )

    size_bytes = models.PositiveIntegerField(
        default=0,
    )

    class Meta:
        db_table = "ticket_attachments"
        ordering = ["-created_at"]

    def __str__(self):
        return self.original_filename


class TicketHistory(TimeStampedModel):
    """Audit trail for ticket lifecycle events."""

    class Action(models.TextChoices):
        CREATED = "CREATED", "Created"
        ASSIGNED = "ASSIGNED", "Assigned"
        REASSIGNED = "REASSIGNED", "Reassigned"
        UNASSIGNED = "UNASSIGNED", "Unassigned"
        STATUS_CHANGED = "STATUS_CHANGED", "Status changed"
        PRIORITY_CHANGED = "PRIORITY_CHANGED", "Priority changed"
        CATEGORY_CHANGED = "CATEGORY_CHANGED", "Category changed"

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="history",
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="ticket_history_actions",
        null=True,
        blank=True,
    )

    action = models.CharField(
        max_length=30,
        choices=Action.choices,
    )

    description = models.CharField(
        max_length=255,
    )

    class Meta:
        db_table = "ticket_history"
        ordering = ["created_at"]
        verbose_name_plural = "Ticket history"

    def __str__(self):
        return (
            f"{self.get_action_display()} "
            f"on {self.ticket.ticket_number}"
        )


