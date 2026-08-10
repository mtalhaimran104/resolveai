"""
Data migration: create the built-in super administrator account.

After `migrate` finishes on an empty database there is somebody who can log
in to /admin/ immediately — no `createsuperuser` prompt required. That is
the whole point: a new team member can go from `git clone` to a working
login with two commands.

Credentials come from the environment so they can differ per machine:

    SUPERADMIN_USERNAME   default "superadmin"
    SUPERADMIN_EMAIL      default "superadmin@resolveai.local"
    SUPERADMIN_PASSWORD   default "ChangeMe123!"

The default password is fine for local development and must never reach a
real deployment. Set `SUPERADMIN_PASSWORD` in `.env` before running
migrations anywhere that is not your laptop.

Note on hashing: historical models returned by `apps.get_model()` only have
fields and managers — no `set_password()` method — so the password is
hashed with `make_password()` instead. Never assign a plain-text password
to `user.password`.

Created with: `manage.py makemigrations accounts --empty --name create_superadmin`
"""

import os

from django.contrib.auth.hashers import make_password
from django.db import migrations

DEFAULT_PASSWORD = "ChangeMe123!"


def create_superadmin(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Role = apps.get_model("accounts", "Role")
    UserRole = apps.get_model("accounts", "UserRole")

    username = os.getenv("SUPERADMIN_USERNAME", "superadmin").strip()
    email = os.getenv("SUPERADMIN_EMAIL", "superadmin@resolveai.local").strip().lower()
    password = os.getenv("SUPERADMIN_PASSWORD", DEFAULT_PASSWORD)

    # Idempotent: if the account already exists (someone re-ran this
    # migration, or created the user by hand) leave its password alone.
    user = User.objects.filter(username=username).first()
    if user is None:
        user = User.objects.create(
            username=username,
            email=email,
            first_name="Super",
            last_name="Admin",
            password=make_password(password),
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        if password == DEFAULT_PASSWORD:
            print(
                f"\n  Created superadmin '{username}' with the default development "
                f"password. Change it before deploying anywhere.\n"
            )

    admin_role = Role.objects.filter(code="ADMIN").first()
    if admin_role is not None:
        UserRole.objects.get_or_create(
            user=user,
            role=admin_role,
            defaults={"assigned_by": None},  # NULL = granted by the system
        )


def delete_superadmin(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    username = os.getenv("SUPERADMIN_USERNAME", "superadmin").strip()
    User.objects.filter(username=username, is_superuser=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_seed_roles_and_permissions"),
    ]

    operations = [
        migrations.RunPython(create_superadmin, delete_superadmin),
    ]
