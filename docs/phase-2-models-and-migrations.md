# Phase 2 — Models, Migrations and the Superadmin

This document has two jobs:

1. Explain the models and migrations that were just added — the identity and
   RBAC tables that signup and login (Phase 3) will be built on.
2. Be the **pattern you copy** when you build the remaining modules
   (departments, categories, tickets, messages, AI results, knowledge base,
   attachments, audit logs, notifications).

Read it once end to end before writing your first model. Section 10 is a
worked example you can follow step by step.

The source of truth for *what* to build is
`docs/ResolveAI_Database_Schema_Design.pdf`. This document is about *how* we
build it in Django.

---

## 1. What Phase 2 Adds

Five tables, all from section 5 of the schema document:

| Table              | Model            | Purpose                                   |
| ------------------ | ---------------- | ----------------------------------------- |
| `users`            | `User`           | Somebody who can log in                   |
| `roles`            | `Role`           | REQUESTER / AGENT / SUPERVISOR / ADMIN    |
| `permissions`      | `Permission`     | One action somebody may perform           |
| `user_roles`       | `UserRole`       | Which roles a user holds                  |
| `role_permissions` | `RolePermission` | What a role is allowed to do              |

Plus three migrations:

| Migration                          | Kind      | What it does                                    |
| ---------------------------------- | --------- | ----------------------------------------------- |
| `0001_initial`                     | schema    | Creates the five tables                         |
| `0002_seed_roles_and_permissions`  | data      | Inserts the 4 roles, 26 permissions and mapping |
| `0003_create_superadmin`           | data      | Creates the `superadmin` login                  |

Tickets, departments and everything else are **not** here. That is
deliberate — you are going to build them using this pattern.

---

## 2. Where Things Live

```text
web/
├── core/           # shared building blocks, no tables of its own
│   └── models.py   #   TimeStampedModel (abstract)
├── accounts/       # identity and RBAC  ← Phase 2
│   ├── models.py
│   ├── admin.py
│   ├── tests.py
│   └── migrations/
│       ├── 0001_initial.py
│       ├── 0002_seed_roles_and_permissions.py
│       └── 0003_create_superadmin.py
└── dashboard/      # the dashboard page (Phase 1)
```

**One Django app per domain.** The schema document groups tables into
modules; each module becomes one app:

| Module          | App to create   | Models                                           |
| --------------- | --------------- | ------------------------------------------------ |
| Identity / RBAC | `accounts` ✅    | User, Role, Permission, UserRole, RolePermission |
| Organization    | `organization`  | Department                                       |
| Classification  | `classification`| TicketCategory                                   |
| Ticketing       | `tickets`       | Ticket, TicketMessage, TicketStatusHistory, TicketAssignment |
| AI              | `ai`            | AIAnalysis, AISuggestion                         |
| Knowledge base  | `knowledge`     | KnowledgeArticle, KnowledgeArticleVersion        |
| Attachments     | `attachments`   | TicketAttachment                                 |
| Audit           | `audit`         | AuditLog                                         |
| Notifications   | `notifications` | Notification                                     |

Do **not** put everything in one giant `models.py`. When you cannot explain
in one sentence why a model lives in an app, it is in the wrong app.

---

## 3. The Five Tables

### `users`

| Column                    | Where it comes from                              |
| ------------------------- | ------------------------------------------------ |
| `id`                      | Django's automatic `BigAutoField` primary key     |
| `password`, `last_login`  | inherited from `AbstractBaseUser`                 |
| `created_at`, `updated_at`| inherited from `core.TimeStampedModel`            |
| `username`, `email`       | declared on `User`; both `unique=True`            |
| `first_name`, `last_name` | declared on `User`                                |
| `is_active`               | disable an account without deleting its history   |
| `is_staff`                | may open Django Admin at `/admin/`                |
| `is_superuser`            | bypasses every permission check                   |

Emails are lower-cased in `User.save()`, so `Ali@x.com` and `ali@x.com`
cannot both register — a unique constraint on a case-sensitive column would
not have stopped that on its own.

### `roles` / `permissions`

A **role** is a named bundle (`AGENT`). A **permission** is one action
(`ticket.assign`). Both have a `code` column, and *code is what the
application checks* — never the display name, which somebody will rename.

Permission codes are `module.action`: `ticket.view_all`, `user.deactivate`,
`knowledge.manage`.

### `user_roles` / `role_permissions`

Join tables. `user_roles` is a model rather than a bare `ManyToManyField`
because the schema requires extra columns on the link itself —
`assigned_by` and `assigned_at` (who granted this role, and when).

> Rule of thumb: a plain `ManyToManyField` is enough until the relationship
> itself needs data. The moment it does, write the join model and point the
> `ManyToManyField` at it with `through=`.

---

## 4. Why a Custom User Model

We replaced `django.contrib.auth.User` with `accounts.User` and told Django
about it in `config/settings.py`:

```python
AUTH_USER_MODEL = "accounts.User"
```

The schema document says to do this "from the beginning", and it is right:
swapping the user model later, once tickets and messages already have
foreign keys to it, is genuinely painful. Doing it now costs nothing.

Two consequences you must remember:

**a) `AUTH_USER_MODEL` can only be set on an empty database.** Django writes
the user table during the very first `migrate`. If Phase 1 already created
`auth_user` on your machine, reset the database once:

```bash
docker compose down -v      # -v deletes the MySQL volume — all data is lost
docker compose up -d --build
docker compose exec web python manage.py migrate
```

**b) Never import `accounts.User` directly in another app.** Use the
indirection Django provides, so the project keeps working if the user model
ever moves:

```python
from django.conf import settings

class Ticket(models.Model):
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
```

```python
from django.contrib.auth import get_user_model   # in views, tests, services
User = get_user_model()
```

### 4.1 "Why not just use Django's `Group` and `Permission`?"

The right question to ask, and worth answering properly — Django *does* ship
an RBAC system, and reinventing framework features is normally a mistake.

We use Django's built-ins everywhere they fit:

| Feature                                                     | Who provides it |
| ----------------------------------------------------------- | --------------- |
| Password hashing, `check_password()`, password validators     | Django          |
| `authenticate()`, `login()`, `logout()`, sessions             | Django          |
| `LoginView`, `LogoutView`, password change and reset flows    | Django          |
| `AuthenticationForm`, `BaseUserCreationForm`, `SetPasswordForm` | Django        |
| `@login_required`, `LoginRequiredMixin`                       | Django          |
| `is_active` / `is_staff` / `is_superuser`, Django Admin       | Django          |
| **Roles and business permissions**                            | **ResolveAI**   |

Do not hand-write anything in the top six rows in Phase 3. Only the last row
is ours, for three concrete reasons:

1. **`Group` has two fields.** `name` and `permissions` — that is the entire
   model. The schema requires `roles.code`, `roles.description`,
   `roles.is_system_role` and timestamps.
2. **`Permission` requires a `content_type`** — a non-nullable foreign key to
   a *model*. Django's permissions describe rows in a table
   (`tickets.add_ticket`). Several ResolveAI permissions describe no table at
   all: `report.view`, `ai.use_suggestion`, `knowledge.manage`. Forcing them
   into Django's table means inventing a fake model to hang them off. Django's
   `Permission` also has no `module` or `description` column.
3. **`auth_user_groups` has no audit columns.** It stores `user_id` and
   `group_id` and nothing else. Section 5.4 of the schema requires
   `assigned_by` and `assigned_at` — who granted this role, and when.

Going the Django route would therefore mean a fake content type, three lost
columns, a side table for the audit fields, and an ERD that no longer matches
the approved design document. The custom tables are the smaller change.

For the same reason we skipped `PermissionsMixin`: it would link every user to
Django's `auth_group` / `auth_permission` tables next to our own, leaving two
RBAC systems and no obvious answer to "which one is real?". ResolveAI has
exactly one: ours.

The price we pay is that `@permission_required` and the `{{ perms }}` template
variable do not know about our permissions — so we use
`user.has_permission("ticket.assign")` instead (section 9).

You will still see `auth_group`, `auth_permission` and `auth_group_permissions`
in `SHOW TABLES`. Those are created by `django.contrib.auth` itself (Django
Admin depends on the app) and nothing in ResolveAI writes to them. Ignore
them; `roles` and `permissions` are the tables that matter.

---

## 5. Model Conventions to Copy

Every model you write for this project follows these. They are all visible
in `accounts/models.py`.

### 5.1 Explicit table names

```python
class Meta:
    db_table = "tickets"
```

Without this, Django would name the table `tickets_ticket`. The schema
document specifies `tickets`, so we say so explicitly. Table names are
plural and `snake_case`.

### 5.2 Inherit `TimeStampedModel` when the table has timestamps

```python
from core.models import TimeStampedModel

class Department(TimeStampedModel):
    ...
```

It is an abstract model: it adds `created_at` / `updated_at` columns to your
table and creates no table of its own. Tables that the schema shows with
only `created_at` (history and log tables) declare that single field
themselves instead.

### 5.3 `TextChoices` instead of MySQL `ENUM`

```python
class Status(models.TextChoices):
    OPEN = "OPEN", "Open"
    IN_PROGRESS = "IN_PROGRESS", "In progress"

status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN)
```

Adding a value is then an ordinary code change, not an `ALTER TABLE`. Use
`Status.OPEN` in code — a mistyped constant raises `AttributeError`, a
mistyped string silently matches nothing.

### 5.4 Choose `on_delete` deliberately

This is the question the schema document's "deletion policy" section
answers. There is no safe default; pick per foreign key.

| `on_delete`  | Meaning                                      | Use it for                                               |
| ------------ | -------------------------------------------- | -------------------------------------------------------- |
| `PROTECT`    | refuse to delete the parent                  | `Ticket.requester` — never lose a ticket with its author |
| `CASCADE`    | delete the children too                      | `TicketMessage.ticket` — a message without its ticket is meaningless |
| `SET_NULL`   | keep the child, null the link (needs `null=True`) | `Ticket.assigned_to` — the ticket outlives the agent's account |

ResolveAI deactivates rather than deletes (`is_active = False`), so in
practice `PROTECT` and `SET_NULL` dominate.

### 5.5 Always name your reverse accessors

```python
requester = models.ForeignKey(
    settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="submitted_tickets"
)
assigned_to = models.ForeignKey(
    settings.AUTH_USER_MODEL, null=True, blank=True,
    on_delete=models.SET_NULL, related_name="assigned_tickets",
)
```

Now `user.submitted_tickets.all()` reads like English. Two foreign keys to
the same model *require* distinct `related_name`s — without them Django
raises a clash error.

### 5.6 Constraints and indexes belong in `Meta`

```python
class Meta:
    db_table = "user_roles"
    constraints = [
        models.UniqueConstraint(fields=["user", "role"], name="uniq_user_role"),
    ]
    indexes = [
        models.Index(fields=["ticket", "created_at"], name="idx_msg_ticket_created"),
    ]
```

Add the indexes listed in section 13.2 of the schema document when you
create the table they belong to — they exist because of the queries the
dashboard and queue pages will run. Constraint and index names are global
in MySQL, so keep them descriptive.

### 5.7 `__str__`, `help_text`, `ordering`

`__str__` is what Django Admin, the shell and error messages show — always
define it. `help_text` shows up in Admin and in forms, and doubles as
documentation for the next reader. `ordering` gives lists a stable order.

### 5.8 Business rules live outside the model

Models describe *data*. A rule like "assigning a ticket closes the previous
assignment, updates the ticket, writes a status-history row and an audit
log, all in one transaction" is a **service function**, not a model method:

```python
# tickets/services.py
from django.db import transaction

@transaction.atomic
def assign_ticket(ticket, agent, assigned_by):
    ...
```

Small helpers that only read the object's own data (`user.has_permission()`,
`ticket.is_open`) are fine on the model.

---

## 6. The Migration Workflow

A migration is a Python file describing a change to the database. Django
generates most of them for you and records which ones have run in the
`django_migrations` table.

```bash
# 1. Edit models.py
# 2. Generate the migration file (does not touch the database)
docker compose exec web python manage.py makemigrations accounts

# 3. Look at the SQL it will run — do this before every migrate
docker compose exec web python manage.py sqlmigrate accounts 0001

# 4. Apply it
docker compose exec web python manage.py migrate

# What has and has not been applied
docker compose exec web python manage.py showmigrations
```

Rules:

- **Commit migration files to git.** They are code. A teammate pulling your
  branch runs `migrate` and gets the same schema.
- **Never edit a migration that has been applied or pushed.** Change the
  model and run `makemigrations` again; Django writes a follow-up migration.
  Editing history means your database and everyone else's silently diverge.
- **One logical change per migration**, with a name that says what it does:
  `makemigrations tickets --name add_ticket_priority_index`.
- **Read what `makemigrations` generated** before committing it. If it wants
  to delete a column you did not mean to touch, that is your warning.
- If Django asks *"you are trying to add a non-nullable field without a
  default"*, give the field `null=True` or `default=...` — do not pick the
  "one-off default" option unless you understand what it writes.

### Undoing a migration in development

```bash
docker compose exec web python manage.py migrate accounts 0001   # roll back to 0001
docker compose exec web python manage.py migrate accounts zero   # undo the whole app
```

This works only if your migrations are reversible — which is why the data
migrations below all provide a reverse function.

---

## 7. The Data Migration Pattern

`0002_seed_roles_and_permissions.py` is the file to copy whenever you need
rows to exist in a fresh database. The schema document lists what still
needs seeding: departments, ticket categories, demo users, at least 10
knowledge articles and at least 20 demo tickets.

Create the empty file first, then fill it in:

```bash
docker compose exec web python manage.py makemigrations organization --empty --name seed_departments
```

```python
from django.db import migrations

DEPARTMENTS = [
    ("IT_SUPPORT", "IT Support"),
    ("FINANCE", "Finance"),
]

def seed_departments(apps, schema_editor):
    Department = apps.get_model("organization", "Department")   # rule 1
    for code, name in DEPARTMENTS:
        Department.objects.update_or_create(                     # rule 2
            code=code, defaults={"name": name, "is_active": True},
        )

def unseed_departments(apps, schema_editor):
    Department = apps.get_model("organization", "Department")
    Department.objects.filter(code__in=[c for c, _ in DEPARTMENTS]).delete()

class Migration(migrations.Migration):
    dependencies = [("organization", "0001_initial")]
    operations = [migrations.RunPython(seed_departments, unseed_departments)]
```

**Rule 1 — `apps.get_model()`, never a direct import.** `apps.get_model`
hands you the *historical* model: the fields exactly as they existed at this
point in migration history. If you write `from organization.models import
Department`, the migration uses today's model, and it will crash for the
next person the moment somebody adds a required field — because their
database at migration 0002 does not have that column yet.

**Rule 2 — idempotent and reversible.** `update_or_create` / `get_or_create`
mean re-running is harmless. The second argument to `RunPython` is the
reverse function, so rolling back works. Use
`migrations.RunPython.noop` only when an undo genuinely makes no sense.

**Do not seed inside `0001_initial`.** Keep schema changes and data changes
in separate files; they fail for different reasons and roll back
differently.

---

## 8. The Superadmin Migration

`0003_create_superadmin.py` creates the built-in admin account, so a fresh
clone reaches a working login with nothing but `migrate`.

Credentials come from the environment (`.env`), with development defaults:

| Variable              | Default                      |
| --------------------- | ---------------------------- |
| `SUPERADMIN_USERNAME` | `superadmin`                 |
| `SUPERADMIN_EMAIL`    | `superadmin@resolveai.local` |
| `SUPERADMIN_PASSWORD` | `ChangeMe123!`               |

Log in at <http://localhost:8000/admin/> with `superadmin` / `ChangeMe123!`.

Two details worth understanding, because they will bite you in your own
migrations:

**Passwords must be hashed.** Historical models have fields and managers but
**no custom methods** — `user.set_password()` does not exist inside a
migration. Use `make_password()`:

```python
from django.contrib.auth.hashers import make_password

User.objects.create(username=..., password=make_password(password), ...)
```

Assigning a plain string to `password` would store it in clear text and
nobody would be able to log in.

**It is idempotent.** If the user already exists the migration leaves the
password alone and only makes sure the ADMIN role is attached. Re-running it
never resets somebody's password.

To change the superadmin password afterwards:

```bash
docker compose exec web python manage.py changepassword superadmin
```

`manage.py createsuperuser` still works too — it goes through
`UserManager.create_superuser()`. Note that it creates a user with
`is_superuser=True` but **no** ADMIN role row; grant the role in Django
Admin if the account needs to appear in RBAC queries.

---

## 9. Using Roles and Permissions in Code

Never check `if user.username == "admin"` and never check the role name
where you mean the permission. Check the permission:

```python
if not request.user.has_permission("ticket.assign"):
    raise PermissionDenied
```

Available on `User`:

| Call                                | Returns                                       |
| ----------------------------------- | --------------------------------------------- |
| `user.has_permission("ticket.assign")` | `True` / `False` — the check you want almost always |
| `user.has_role(RoleCode.SUPERVISOR)` | `True` / `False` — only for genuinely role-shaped logic |
| `user.permission_codes`              | set of every code the user's roles grant       |
| `user.role_codes`                    | set of the user's role codes                   |
| `user.refresh_permission_cache()`    | forget the cached sets after changing roles    |

Inactive users are refused everything; superusers are allowed everything.

Both sets are cached on the user object the first time you read them, so a
ticket list that calls `has_permission()` once per row costs one query, not
one per row. The cache lives as long as the object does — which for
`request.user` is one request. If you grant or revoke a role and then check a
permission *in the same request*, call `refresh_permission_cache()` in
between.

In a template:

```django
{% if request.user.is_superuser %} ... {% endif %}
```

For permissions in templates, put the flag in the view's context
(`{"can_assign": request.user.has_permission("ticket.assign")}`) rather than
calling a method with arguments from the template language.

> Hiding a sidebar link is not security. Every protected view, API endpoint
> and service function must check the permission itself.

---

## 10. Worked Example — Build the `organization` App

Do this one yourself; it is the smallest module in the schema (section 6.1)
and it touches every step.

**1. Create the app**

```bash
docker compose exec web python manage.py startapp organization
```

**2. Register it** in `config/settings.py`, next to the other ResolveAI apps:

```python
INSTALLED_APPS = [
    ...
    "core",
    "accounts",
    "organization",     # ← new
    "dashboard",
]
```

**3. Write the model** in `organization/models.py`:

```python
from django.db import models

from core.models import TimeStampedModel


class Department(TimeStampedModel):
    """A team that owns a ticket queue, e.g. IT Support."""

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, unique=True, help_text="e.g. FINANCE")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "departments"
        ordering = ["name"]

    def __str__(self):
        return self.name
```

Check it against the conventions in section 5: explicit `db_table` ✅,
timestamps inherited ✅, `unique=True` on `code` as the schema requires ✅,
`is_active` instead of deletion ✅, `__str__` ✅.

**4. Generate and inspect the migration**

```bash
docker compose exec web python manage.py makemigrations organization
docker compose exec web python manage.py sqlmigrate organization 0001
```

**5. Add the seed data migration** — the `--empty` recipe from section 7,
with the five departments from the schema document (IT_SUPPORT, FINANCE,
ADMISSIONS, EXAMINATION, GENERAL).

**6. Apply**

```bash
docker compose exec web python manage.py migrate
```

**7. Register in Admin** (`organization/admin.py`) so you can see the rows:

```python
from django.contrib import admin

from .models import Department


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
```

**8. Write tests** (`organization/tests.py`) — copy the shape of
`accounts/tests.py`: the seeded rows exist, `code` is unique, `__str__`
returns the name.

**9. Run everything and commit**

```bash
docker compose exec web python manage.py test
git add organization web/config/settings.py
git commit -m "Add organization app with Department model and seed data"
```

Then repeat for `classification` (TicketCategory, which has a nullable
`department` foreign key — `on_delete=models.SET_NULL`), and you are ready
for the ticket core.

---

## 11. Verifying Your Work

```bash
# Every model is valid and nothing is missing a migration
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run

# Run the tests (builds a fresh test database, so this also tests migrations)
docker compose exec web python manage.py test

# Poke at real data
docker compose exec web python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> u = User.objects.get(username="superadmin")
>>> u.role_codes
{'ADMIN'}
>>> sorted(u.permission_codes)[:3]
['ai.use_suggestion', 'ai.view_analysis', 'category.manage']

# Look at the actual MySQL tables
docker compose exec db mysql -uresolve_ai_user -presolve_ai_password resolve_ai -e "SHOW TABLES; DESCRIBE users;"
```

`makemigrations --check --dry-run` failing means somebody changed a model
without generating the migration. Run it before you push.

---

## 12. Common Mistakes

| Symptom                                                                    | Cause and fix                                                                                   |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `InconsistentMigrationHistory` / `auth.User` errors after pulling Phase 2   | Your database predates `AUTH_USER_MODEL`. `docker compose down -v`, then `up` and `migrate`.       |
| `Reverse accessor clashes`                                                  | Two foreign keys to the same model without distinct `related_name`s.                               |
| Migration works locally, crashes for a teammate                             | You imported the real model instead of using `apps.get_model()` in a data migration.               |
| Password stored but login fails                                             | You assigned a plain string to `password`. Use `set_password()` or `make_password()`.              |
| `Model class ... doesn't declare an explicit app_label`                     | The app is missing from `INSTALLED_APPS`.                                                          |
| `makemigrations` produces nothing                                           | The app is not in `INSTALLED_APPS`, or you edited a file Django is not importing.                  |
| `Table 'x' already exists`                                                  | The table was created outside Django. Never write DDL by hand — migrations own the schema.         |
| Duplicate accounts differing only in email case                             | You bypassed `User.save()` (e.g. `bulk_create` / raw SQL), which is where lower-casing happens.    |
| `IntegrityError: uniq_user_role`                                            | Working as intended — a user cannot hold the same role twice. Use `get_or_create`.                 |

---

## 13. Definition of Done for Every Module

Before you open a merge request for a new app, check all of these:

- [ ] One app per schema module, listed in `INSTALLED_APPS`
- [ ] `db_table` matches the schema document exactly
- [ ] Every column from the schema table exists, with the right type and nullability
- [ ] Unique constraints from section 13.1 of the schema are in place
- [ ] Indexes from section 13.2 are in place
- [ ] `on_delete` chosen deliberately for every foreign key, matching the deletion policy
- [ ] `related_name` on every foreign key
- [ ] `__str__` on every model
- [ ] User references use `settings.AUTH_USER_MODEL`, never a direct import
- [ ] Migrations generated by `makemigrations`, reviewed, and committed
- [ ] Seed data (if any) in a separate, idempotent, reversible data migration
- [ ] Models registered in `admin.py`
- [ ] Tests covering the model rules, and they pass
- [ ] `manage.py check` and `makemigrations --check --dry-run` are clean
- [ ] You can explain every table and relationship you added out loud

---

## 14. What Comes Next

Phase 3 builds signup and login screens on top of these models: a
registration form that creates a `User` and grants the REQUESTER role, a
login view, logout, and role-aware navigation. The models are ready for it —
nothing in this phase needs to change.

Build those screens on Django's own auth machinery (`LoginView`,
`LogoutView`, `AuthenticationForm`, `BaseUserCreationForm`, the
`PasswordReset*` views) with ResolveAI templates, as explained in section
4.1. The only ResolveAI-specific part is granting the REQUESTER role after
signup:

```python
UserRole.objects.create(user=new_user, role=Role.objects.get(code=RoleCode.REQUESTER))
```
