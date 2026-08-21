from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Role, RoleCode, UserRole

User = get_user_model()


class Command(BaseCommand):
    help = "Grant a role (AGENT, SUPERVISOR, ADMIN, REQUESTER) to a user by username."

    def add_arguments(self, parser):
        parser.add_argument("username", type=str, help="Username of the user")
        parser.add_argument(
            "role",
            type=str,
            choices=[c.value for c in RoleCode],
            help="Role code to grant",
        )

    def handle(self, *args, **options):
        username = options["username"]
        role_code = options["role"]

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'No user found with username "{username}"')

        try:
            role = Role.objects.get(code=role_code)
        except Role.DoesNotExist:
            raise CommandError(
                f'Role "{role_code}" not found. Did migrations run? '
                f"(python manage.py migrate accounts)"
            )

        user_role, created = UserRole.objects.get_or_create(user=user, role=role)
        user.refresh_permission_cache()

        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Granted "{role_code}" to user "{username}".')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'User "{username}" already has role "{role_code}".')
            )