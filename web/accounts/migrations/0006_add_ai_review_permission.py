from django.db import migrations
def add_ai_review_permission(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Role = apps.get_model("accounts", "Role")
    RolePermission = apps.get_model("accounts", "RolePermission")
    permission, _ = Permission.objects.update_or_create(
        code="ai.review_analysis",
        defaults={
            "module": "ai",
            "description": "Accept, correct, or reject an AI analysis",
        },
    )
    for role_code in ["AGENT", "SUPERVISOR", "ADMIN"]:
        role = Role.objects.get(code=role_code)
        RolePermission.objects.get_or_create(
            role=role,
            permission=permission,
        )
def remove_ai_review_permission(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(
        code="ai.review_analysis"
    ).delete()
class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_user_department"),
    ]
    operations = [
        migrations.RunPython(
            add_ai_review_permission,
            remove_ai_review_permission,
        ),
    ]
