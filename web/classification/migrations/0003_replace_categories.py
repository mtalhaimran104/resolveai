from django.db import migrations


CATEGORIES = [
    ("PORTAL_TECHNICAL_ISSUE", "Portal Technical Issue", "IT_SUPPORT"),
    ("DEGREE", "Degree", "EXAMINATION"),
    ("FEE_CHALLAN", "Fee & Challan", "FINANCE"),
    ("INFRASTRUCTURE_MAINTENANCE", "Infrastructure / Maintenance", "GENERAL"),
    ("EMPLOYEE_SERVICES", "Employee Services", "GENERAL"),
    ("OTHER", "Other", "GENERAL"),
    ("ADMISSION", "Admission", "ADMISSIONS"),
    ("CERTIFICATE_VERIFICATION", "Certificate / Verification", "ADMISSIONS"),
    ("SCHOLARSHIP", "Scholarship", "FINANCE"),
    ("TRANSCRIPT", "Transcript", "EXAMINATION"),
    ("THESIS", "Thesis", "EXAMINATION"),
    ("NAME_CORRECTION", "Name Correction", "ADMISSIONS"),
    ("ACCOUNT_LOGIN", "Account & Login", "IT_SUPPORT"),
    ("PROFILE_UPDATE", "Profile Update", "IT_SUPPORT"),
    ("COMPLAINT", "Complaint", "GENERAL"),
    ("RESULT", "Result", "EXAMINATION"),
    ("EXAMINATION", "Examination", "EXAMINATION"),
    ("COURSE_REGISTRATION", "Course Registration", "ADMISSIONS"),
    ("CLEARANCE", "Clearance", "GENERAL"),
]


def replace_categories(apps, schema_editor):
    TicketCategory = apps.get_model("classification", "TicketCategory")
    Department = apps.get_model("organization", "Department")

    # Remove all existing categories.
    TicketCategory.objects.all().delete()

    # Create the replacement categories.
    for code, name, department_code in CATEGORIES:
        department = Department.objects.filter(code=department_code).first()

        TicketCategory.objects.create(
            code=code,
            name=name,
            department=department,
            is_active=True,
        )


def reverse_categories(apps, schema_editor):
    TicketCategory = apps.get_model("classification", "TicketCategory")

    new_codes = [code for code, _, _ in CATEGORIES]
    TicketCategory.objects.filter(code__in=new_codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("classification", "0002_seed_departments"),
        ("organization", "0002_seed_departments"),
    ]

    operations = [
        migrations.RunPython(
            replace_categories,
            reverse_categories,
        ),
    ]