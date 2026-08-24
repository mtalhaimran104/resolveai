from django.conf import settings
from django.db import models
from core.models import TimeStampedModel
from tickets.models import Ticket
class AIAnalysis(TimeStampedModel):
    """Stores an AI analysis result for a ticket."""
    class AnalysisType(models.TextChoices):
        CLASSIFICATION = "CLASSIFICATION", "Classification"
        PRIORITY = "PRIORITY", "Priority"
        SENTIMENT = "SENTIMENT", "Sentiment"
        SUMMARY = "SUMMARY", "Summary"
    class Status(models.TextChoices):
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        LOW_CONFIDENCE = "LOW_CONFIDENCE", "Low confidence"
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="ai_analyses",
    )
    analysis_type = models.CharField(
        max_length=30,
        choices=AnalysisType.choices,
    )
    model_name = models.CharField(max_length=100)
    model_version = models.CharField(max_length=100)
    input_hash = models.CharField(max_length=128)
    result_json = models.JSONField()
    confidence_score = models.FloatField(null=True, blank=True)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.SUCCESS,
    )
    error_message = models.TextField(blank=True)
    class Meta:
        db_table = "ai_analyses"
        ordering = ["-created_at"]
        verbose_name_plural = "AI analyses"
        indexes = [
            models.Index(
                fields=["ticket", "analysis_type", "created_at"],
                name="ai_analysis_lookup_idx",
            ),
        ]
    def __str__(self):
        return f"{self.get_analysis_type_display()} for {self.ticket.ticket_number}"
class AISuggestion(TimeStampedModel):
    """Stores an AI-generated suggestion related to a ticket."""
    class SuggestionType(models.TextChoices):
        REPLY = "REPLY", "Reply"
        FAQ = "FAQ", "FAQ"
        ACTION = "ACTION", "Action"
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="ai_suggestions",
    )
    created_by_analysis = models.ForeignKey(
        AIAnalysis,
        on_delete=models.SET_NULL,
        related_name="suggestions",
        null=True,
        blank=True,
    )
    suggestion_type = models.CharField(
        max_length=20,
        choices=SuggestionType.choices,
    )
    suggested_text = models.TextField()
    source_json = models.JSONField(null=True, blank=True)
    confidence_score = models.FloatField(null=True, blank=True)
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="ai_suggestions_used",
        null=True,
        blank=True,
    )
    used_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        db_table = "ai_suggestions"
        ordering = ["-created_at"]
        verbose_name_plural = "AI suggestions"
    def __str__(self):
        return f"{self.get_suggestion_type_display()} suggestion for {self.ticket.ticket_number}"
class AIFeedback(TimeStampedModel):
    """Stores human feedback and corrections for AI outputs."""
    class FeedbackType(models.TextChoices):
        ACCEPTED = "ACCEPTED", "Accepted"
        CORRECTED = "CORRECTED", "Corrected"
        REJECTED = "REJECTED", "Rejected"
    class RetrainingStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        USED = "USED", "Used"
        EXCLUDED = "EXCLUDED", "Excluded"
    analysis = models.ForeignKey(
        AIAnalysis,
        on_delete=models.CASCADE,
        related_name="feedback",
    )
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="ai_feedback",
    )
    feedback_type = models.CharField(
        max_length=20,
        choices=FeedbackType.choices,
    )
    original_prediction = models.JSONField()
    corrected_prediction = models.JSONField(
        null=True,
        blank=True,
    )
    feedback_comment = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="ai_feedback_reviews",
        null=True,
        blank=True,
    )
    is_retraining_eligible = models.BooleanField(default=False)
    retraining_status = models.CharField(
        max_length=20,
        choices=RetrainingStatus.choices,
        default=RetrainingStatus.PENDING,
    )
    class Meta:
        db_table = "ai_feedback"
        ordering = ["-created_at"]
        verbose_name_plural = "AI feedback"
    def __str__(self):
        return f"{self.get_feedback_type_display()} feedback for {self.ticket.ticket_number}"


