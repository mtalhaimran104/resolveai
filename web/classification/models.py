from django.db import models

# Create your models here.


from core.models import TimeStampedModel
from organization.models import Department


class TicketCategory(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        related_name="ticket_categories",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "ticket_categories"
        ordering = ["name"]
        verbose_name_plural = "Ticket categories"

    def __str__(self):
        return self.name