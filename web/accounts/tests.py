"""
Tests for the identity and RBAC models.

Django's test runner builds a throwaway database (`test_resolve_ai`) by
running every migration, so these tests also prove that the seed and
superadmin migrations work — not just the model code.

    docker compose exec web python manage.py test accounts
"""

import os

from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import Permission, Role, RoleCode, UserRole

User = get_user_model()


class SeedDataTests(TestCase):
    """What migration 0002 put in the database."""

    def test_four_system_roles_exist(self):
        codes = set(Role.objects.values_list("code", flat=True))
        self.assertEqual(codes, {"REQUESTER", "AGENT", "SUPERVISOR", "ADMIN"})
        self.assertTrue(all(role.is_system_role for role in Role.objects.all()))

    def test_permissions_are_seeded(self):
        self.assertTrue(Permission.objects.filter(code="ticket.assign").exists())
        self.assertTrue(Permission.objects.count() >= 20)

    def test_admin_role_has_every_permission(self):
        admin = Role.objects.get(code=RoleCode.ADMIN)
        self.assertEqual(admin.role_permissions.count(), Permission.objects.count())

    def test_requester_cannot_assign_tickets(self):
        requester = Role.objects.get(code=RoleCode.REQUESTER)
        granted = set(requester.role_permissions.values_list("permission__code", flat=True))
        self.assertIn("ticket.create", granted)
        self.assertNotIn("ticket.assign", granted)


class SuperadminMigrationTests(TestCase):
    """What migration 0003 put in the database."""

    def setUp(self):
        self.username = os.getenv("SUPERADMIN_USERNAME", "superadmin").strip()

    def test_superadmin_exists_and_is_privileged(self):
        user = User.objects.get(username=self.username)
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_superadmin_holds_the_admin_role(self):
        user = User.objects.get(username=self.username)
        self.assertTrue(user.has_role(RoleCode.ADMIN))

    def test_superadmin_can_log_in(self):
        password = os.getenv("SUPERADMIN_PASSWORD", "ChangeMe123!")
        self.assertIsNotNone(authenticate(username=self.username, password=password))

    def test_password_is_hashed_not_stored_in_plain_text(self):
        user = User.objects.get(username=self.username)
        self.assertNotIn("ChangeMe123!", user.password)
        self.assertTrue(user.password.startswith("pbkdf2_"))


class UserManagerTests(TestCase):
    def test_create_user_hashes_the_password(self):
        user = User.objects.create_user("ayesha", "Ayesha@Example.com", "s3cret-pass")
        self.assertNotEqual(user.password, "s3cret-pass")
        self.assertTrue(user.check_password("s3cret-pass"))

    def test_email_is_normalised_to_lowercase(self):
        user = User.objects.create_user("talha", "Talha@Example.COM", "s3cret-pass")
        self.assertEqual(user.email, "talha@example.com")

    def test_username_and_email_are_required(self):
        with self.assertRaises(ValueError):
            User.objects.create_user("", "nobody@example.com", "s3cret-pass")
        with self.assertRaises(ValueError):
            User.objects.create_user("nobody", "", "s3cret-pass")

    def test_create_superuser_sets_the_privilege_flags(self):
        user = User.objects.create_superuser("root", "root@example.com", "s3cret-pass")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)


class RolePermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("maryam", "maryam@example.com", "s3cret-pass")
        self.agent_role = Role.objects.get(code=RoleCode.AGENT)

    def grant_agent_role(self):
        return UserRole.objects.create(user=self.user, role=self.agent_role)

    def test_user_without_roles_has_no_permissions(self):
        self.assertFalse(self.user.has_permission("ticket.create"))
        self.assertEqual(self.user.role_codes, set())

    def test_role_grants_its_permissions(self):
        self.grant_agent_role()
        self.assertTrue(self.user.has_role(RoleCode.AGENT))
        self.assertTrue(self.user.has_permission("ticket.comment_internal"))

    def test_permission_outside_the_role_is_denied(self):
        self.grant_agent_role()
        self.assertFalse(self.user.has_permission("ticket.assign"))

    def test_inactive_user_is_denied_everything(self):
        self.grant_agent_role()
        self.user.is_active = False
        self.user.save()
        self.assertFalse(self.user.has_permission("ticket.comment_internal"))

    def test_superuser_bypasses_permission_checks(self):
        self.user.is_superuser = True
        self.user.save()
        self.assertTrue(self.user.has_permission("anything.at.all"))

    def test_the_same_role_cannot_be_granted_twice(self):
        self.grant_agent_role()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.grant_agent_role()

    def test_permissions_are_cached_after_the_first_read(self):
        self.grant_agent_role()
        with self.assertNumQueries(1):
            self.user.has_permission("ticket.update")
            self.user.has_permission("ticket.comment")
            self.user.has_permission("ticket.close")

    def test_refresh_permission_cache_picks_up_a_new_role(self):
        self.assertFalse(self.user.has_permission("ticket.update"))
        self.grant_agent_role()
        self.assertFalse(self.user.has_permission("ticket.update"))  # still cached
        self.user.refresh_permission_cache()
        self.assertTrue(self.user.has_permission("ticket.update"))

    def test_a_user_can_hold_several_roles(self):
        self.grant_agent_role()
        UserRole.objects.create(user=self.user, role=Role.objects.get(code=RoleCode.SUPERVISOR))
        self.assertEqual(self.user.role_codes, {"AGENT", "SUPERVISOR"})
        # Permissions are the union of both roles.
        self.assertTrue(self.user.has_permission("ticket.assign"))
