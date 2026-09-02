from django.db import migrations, models


def backfill_resolved_at(apps, schema_editor):
    """Give already-resolved tickets a resolution timestamp.

    Nothing recorded when a ticket was resolved before Ticket.resolved_at
    existed, so updated_at is the closest available approximation: for a
    resolved or closed ticket it is almost always the moment it was resolved.
    Only rows currently in a resolved state are touched, and only those that
    do not already carry a timestamp.
    """
    Ticket = apps.get_model("tickets", "Ticket")
    Ticket.objects.filter(
        status__in=["RESOLVED", "CLOSED"],
        resolved_at__isnull=True,
    ).update(resolved_at=models.F("updated_at"))


def clear_resolved_at(apps, schema_editor):
    """Reverse the backfill without touching rows set since."""
    Ticket = apps.get_model("tickets", "Ticket")
    Ticket.objects.filter(status__in=["RESOLVED", "CLOSED"]).update(
        resolved_at=None
    )


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0012_ticket_resolved_at_alter_tickethistory_action"),
    ]

    operations = [
        migrations.RunPython(backfill_resolved_at, clear_resolved_at),
    ]
