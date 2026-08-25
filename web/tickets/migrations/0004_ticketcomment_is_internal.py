# Generated manually — adds TicketComment.is_internal (public reply vs
# internal note, used by the agent ticket-detail screen).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0003_tickethistory'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticketcomment',
            name='is_internal',
            field=models.BooleanField(
                blank=True,
                default=False,
                help_text='Internal notes are visible to agents/supervisors/admins only, never the requester.',
            ),
        ),
    ]
