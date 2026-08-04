from django.test import TestCase
from django.urls import reverse


class DashboardViewTests(TestCase):
    def test_dashboard_page_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_dashboard_uses_expected_template(self):
        response = self.client.get(reverse("dashboard"))
        self.assertTemplateUsed(response, "dashboard/index.html")

    def test_dashboard_contains_resolveai_branding(self):
        response = self.client.get("/")
        self.assertContains(response, "ResolveAI")
