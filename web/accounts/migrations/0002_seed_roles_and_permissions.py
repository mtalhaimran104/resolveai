"""
Data migration: the four ResolveAI roles, the permission catalogue and the
mapping between them.

Why a migration and not a fixture or a manual SQL script? Because every
developer, the CI job and the production database all run `migrate`
already. Seeding here means a brand-new database is *usable* the moment
migrations finish — nobody has to remember an extra step.

Two rules every data migration in this project follows:

1. Use `apps.get_model(...)`, never `from accounts.models import Role`.
   `apps.get_model` returns the *historical* version of the model, i.e. the
   fields as they existed at this point in migration history. Importing the
   real model breaks this migration the day someone adds a field to Role.

2. Be idempotent and reversible. `update_or_create` lets the migration be
   re-applied safely, and `reverse_code` lets `migrate accounts 0001` undo
   it during development.

Created with: `manage.py makemigrations accounts --empty --name seed_roles_and_permissions`
"""

from django.db import migrations

# ---------------------------------------------------------------------------
# The permission catalogue: (code, name, module, description)
#
# Codes are `module.action`. Add new ones in a *new* migration — editing this
# list after it has run on someone's database changes nothing there.
# ---------------------------------------------------------------------------
PERMISSIONS = [
    # Tickets
    ("ticket.view_own", "View own tickets", "ticket", "See tickets the user submitted"),
    ("ticket.view_assigned", "View assigned tickets", "ticket", "See tickets assigned to the user"),
    ("ticket.view_department", "View department tickets", "ticket", "See the department queue"),
    ("ticket.view_all", "View all tickets", "ticket", "See every ticket in the system"),
    ("ticket.create", "Create ticket", "ticket", "Submit a new support ticket"),
    ("ticket.update", "Update ticket", "ticket", "Edit ticket fields"),
    ("ticket.assign", "Assign ticket", "ticket", "Assign a ticket to an agent"),
    ("ticket.change_status", "Change ticket status", "ticket", "Move a ticket through its states"),
    ("ticket.close", "Close ticket", "ticket", "Close a resolved ticket"),
    ("ticket.reopen", "Reopen ticket", "ticket", "Reopen a resolved or closed ticket"),
    ("ticket.comment", "Reply to ticket", "ticket", "Post a message visible to the requester"),
    ("ticket.comment_internal", "Add internal note", "ticket", "Post a note hidden from the requester"),
    # Users and RBAC
    ("user.view", "View users", "user", "Browse the user directory"),
    ("user.create", "Create user", "user", "Add a new user account"),
    ("user.update", "Update user", "user", "Edit user details"),
    ("user.deactivate", "Deactivate user", "user", "Disable access without deleting history"),
    ("role.view", "View roles", "role", "Browse roles and their permissions"),
    ("role.assign", "Assign role", "role", "Grant or revoke a user's roles"),
    ("role.manage", "Manage roles", "role", "Create roles and edit their permissions"),
    # Organization
    ("department.manage", "Manage departments", "organization", "Create and edit departments"),
    ("category.manage", "Manage categories", "organization", "Create and edit ticket categories"),
    # Knowledge base
    ("knowledge.view", "View knowledge base", "knowledge", "Read published articles"),
    ("knowledge.manage", "Manage knowledge base", "knowledge", "Write and publish articles"),
    # AI
    ("ai.view_analysis", "View AI analysis", "ai", "See AI classification and summaries"),
    ("ai.use_suggestion", "Use AI suggestion", "ai", "Insert an AI-suggested reply"),
    # Reporting
    ("report.view", "View reports", "report", "Open dashboards and reports"),
]

# ---------------------------------------------------------------------------
# The four roles from section 5.2 of the schema document, and what each one
# is allowed to do. ADMIN gets every permission (see `_permissions_for`).
# ---------------------------------------------------------------------------
ROLES = [
    {
        "code": "REQUESTER",
        "name": "Requester",
        "description": "Creates and tracks their own tickets.",
        "permissions": [
            "ticket.view_own",
            "ticket.create",
            "ticket.comment",
            "knowledge.view",
        ],
    },
    {
        "code": "AGENT",
        "name": "Agent",
        "description": "Handles assigned tickets and communicates with requesters.",
        "permissions": [
            "ticket.view_own",
            "ticket.view_assigned",
            "ticket.create",
            "ticket.update",
            "ticket.change_status",
            "ticket.close",
            "ticket.comment",
            "ticket.comment_internal",
            "knowledge.view",
            "ai.view_analysis",
            "ai.use_suggestion",
        ],
    },
    {
        "code": "SUPERVISOR",
        "name": "Supervisor",
        "description": "Manages queues, priorities, assignments and escalations.",
        "permissions": [
            "ticket.view_own",
            "ticket.view_assigned",
            "ticket.view_department",
            "ticket.view_all",
            "ticket.create",
            "ticket.update",
            "ticket.assign",
            "ticket.change_status",
            "ticket.close",
            "ticket.reopen",
            "ticket.comment",
            "ticket.comment_internal",
            "knowledge.view",
            "knowledge.manage",
            "ai.view_analysis",
            "ai.use_suggestion",
            "user.view",
            "role.view",
            "report.view",
        ],
    },
    {
        "code": "ADMIN",
        "name": "Admin",
        "description": "Manages users, roles, departments, categories, knowledge base and settings.",
        "permissions": "__all__",
    },
]


def _permissions_for(role):
    if role["permissions"] == "__all__":
        return [code for code, _name, _module, _description in PERMISSIONS]
    return role["permissions"]


def seed_rbac(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Role = apps.get_model("accounts", "Role")
    RolePermission = apps.get_model("accounts", "RolePermission")

    permissions = {}
    for code, name, module, description in PERMISSIONS:
        permissions[code], _created = Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "module": module, "description": description},
        )

    for role_spec in ROLES:
        role, _created = Role.objects.update_or_create(
            code=role_spec["code"],
            defaults={
                "name": role_spec["name"],
                "description": role_spec["description"],
                "is_system_role": True,
            },
        )
        for code in _permissions_for(role_spec):
            RolePermission.objects.get_or_create(role=role, permission=permissions[code])


def unseed_rbac(apps, schema_editor):
    """Undo `seed_rbac` so `migrate accounts 0001` works during development.

    Roles are only removed when nothing references them — deleting a role
    that a real user still holds would fail on the PROTECT foreign key, and
    silently dropping people's roles would be worse.
    """
    Permission = apps.get_model("accounts", "Permission")
    Role = apps.get_model("accounts", "Role")
    UserRole = apps.get_model("accounts", "UserRole")

    role_codes = [role["code"] for role in ROLES]
    in_use = set(
        UserRole.objects.filter(role__code__in=role_codes).values_list("role__code", flat=True)
    )
    Role.objects.filter(code__in=role_codes).exclude(code__in=in_use).delete()
    Permission.objects.filter(code__in=[code for code, *_rest in PERMISSIONS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_rbac, unseed_rbac),
    ]
