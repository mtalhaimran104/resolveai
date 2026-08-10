from django.db import models

# Create your models here.
from core.models import TimeStampedModel


class Department(TimeStampedModel):
    """A team that owns a ticket queue, e.g. IT Support."""

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, unique=True, help_text="e.g. FINANCE")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "departments"
        ordering = ["name"]

    def __str__(self):
        return self.name