from django.db import models

from tickets.models import Ticket


class AIAnalysis(models.Model):
    """
    Stores the AI analysis generated for a ticket.

    The AI service performs the analysis.
    Django stores the returned result here.
    """

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="ai_analyses",
    )

    sentiment = models.CharField(
        max_length=20,
        blank=True,
        default="",
    )

    summary = models.TextField(
        blank=True,
        default="",
    )

    faq_answer = models.TextField(
        blank=True,
        default="",
    )

    faq_similarity_score = models.FloatField(
        null=True,
        blank=True,
    )

    faq_confidence_level = models.CharField(
        max_length=20,
        blank=True,
        default="",
    )

    model_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    model_version = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    status = models.CharField(
        max_length=20,
        default="COMPLETED",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "ai_analyses"
        ordering = ["-created_at"]

    def __str__(self):
        return f"AI Analysis - {self.ticket.ticket_number}"