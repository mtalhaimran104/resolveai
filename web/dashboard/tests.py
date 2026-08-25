from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, RoleCode, UserRole

User = get_user_model()


class DashboardViewTests(TestCase):
    """dashboard() requires login and picks a template per role — see
    dashboard/views.py. These replace the old Phase-1 tests, which assumed
    anonymous visitors could see the dashboard (true before auth was wired
    up, not true — and not desirable — any more)."""

    def setUp(self):
        self.requester = User.objects.create_user(
            username="requester1", email="requester1@example.com", password="pass12345!"
        )
        UserRole.objects.create(user=self.requester, role=Role.objects.get(code=RoleCode.REQUESTER))

        self.admin = User.objects.create_user(
            username="admin1", email="admin1@example.com", password="pass12345!",
            is_superuser=True,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_requester_sees_requester_dashboard(self):
        self.client.login(username="requester1", password="pass12345!")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/index-requester.html")

    def test_admin_sees_admin_dashboard_with_branding(self):
        self.client.login(username="admin1", password="pass12345!")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/index.html")
        self.assertContains(response, "ResolveAI")
