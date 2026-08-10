from django.test import TestCase

# Create your tests here.
from django.db import IntegrityError


from .models import Department


class DepartmentModelTests(TestCase):
    def test_seeded_departments_exist(self):
        self.assertTrue(Department.objects.filter(code="IT_SUPPORT").exists())
        self.assertEqual(Department.objects.count(), 5)

    def test_code_is_unique(self):
        Department.objects.create(name="Test Dept", code="TEST_DEPT")
        with self.assertRaises(IntegrityError):
            Department.objects.create(name="Duplicate", code="TEST_DEPT")

    def test_str_returns_name(self):
        dept = Department.objects.get(code="FINANCE")
        self.assertEqual(str(dept), "Finance")