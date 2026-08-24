"""
Identity and RBAC models — section 5 of the Database Schema Design document.

Five tables live here:

    users              a person who can log in
    roles              REQUESTER / AGENT / SUPERVISOR / ADMIN
    permissions        a single thing someone is allowed to do
    user_roles         which roles a user has        (users  <-> roles)
    role_permissions   what a role is allowed to do  (roles  <-> permissions)

Why not Django's built-in `auth.Group` / `auth.Permission`? Because the
schema document specifies our own `roles` and `permissions` tables with a
`code` column that the application reasons about (`"ticket.assign"`), and
because ResolveAI's permissions describe *business* actions, not the
model-level add/change/delete permissions Django generates automatically.
Keeping one RBAC system instead of two avoids "which permission table is
the real one?" confusion.

Read `docs/phase-2-models-and-migrations.md` before adding models of your
own — it explains the conventions used in this file.
"""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel


class RoleCode(models.TextChoices):
    """The four roles ResolveAI ships with.

    `TextChoices` gives us a readable constant (`RoleCode.AGENT`), the value
    stored in MySQL (`"AGENT"`) and a human label, all in one place. Use
    `RoleCode.ADMIN` in code instead of typing the string `"ADMIN"` — a typo
    in a constant is an error, a typo in a string is a silent bug.
    """

    REQUESTER = "REQUESTER", "Requester"
    AGENT = "AGENT", "Agent"
    SUPERVISOR = "SUPERVISOR", "Supervisor"
    ADMIN = "ADMIN", "Admin"


class Role(TimeStampedModel):
    """A named bundle of permissions, e.g. AGENT."""

    name = models.CharField(max_length=100, unique=True, help_text="Display name, e.g. 'Agent'")
    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Machine-readable code the application checks, e.g. 'AGENT'",
    )
    description = models.CharField(max_length=255, blank=True)
    is_system_role = models.BooleanField(
        default=False,
        help_text="System roles are seeded by a migration and must not be deleted",
    )

    class Meta:
        db_table = "roles"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Permission(models.Model):
    """One thing a user is allowed to do, identified by `code`.

    This model has no timestamps: permissions are seeded by migrations and
    never edited at runtime, so there is nothing useful to timestamp. That
    is why it extends `models.Model` and not `TimeStampedModel`.
    """

    name = models.CharField(max_length=150, help_text="Display name, e.g. 'View all tickets'")
    code = models.CharField(
        max_length=100,
        unique=True,
        help_text="Checked in code, e.g. 'ticket.view_all'",
    )
    module = models.CharField(
        max_length=50,
        help_text="Feature area this permission belongs to, e.g. 'ticket'",
    )
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "permissions"
        ordering = ["module", "code"]

    def __str__(self):
        return self.code


class UserManager(BaseUserManager):
    """Creates users with a properly hashed password.

    Django never lets you write `User(password="secret")` — passwords must
    go through `set_password()`, which hashes them. This manager is what
    `manage.py createsuperuser` and the Phase 3 signup view will call.
    """

    use_in_migrations = False

    def _create_user(self, username, email, password, **extra_fields):
        if not username:
            raise ValueError("A username is required")
        if not email:
            raise ValueError("An email address is required")

        user = self.model(
            username=username,
            email=self.normalize_email(email).lower(),
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields["is_staff"] is not True:
            raise ValueError("A superuser must have is_staff=True")
        if extra_fields["is_superuser"] is not True:
            raise ValueError("A superuser must have is_superuser=True")

        return self._create_user(username, email, password, **extra_fields)


class User(AbstractBaseUser, TimeStampedModel):
    """A person who can log in to ResolveAI.

    `AbstractBaseUser` contributes the `password` and `last_login` columns
    plus password hashing and `check_password()`. Everything else on the
    `users` table is declared below.

    We deliberately do *not* inherit `PermissionsMixin`. It would wire every
    user to Django's own `auth_group` / `auth_permission` tables, giving the
    project two competing permission systems. Authorisation in ResolveAI
    goes through `has_permission()` at the bottom of this class.
    """

    username = models.CharField(max_length=150, unique=True, help_text="Unique login identifier")
    email = models.EmailField(max_length=254, unique=True, help_text="Stored lowercase")
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    department = models.ForeignKey("organization.Department",
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="users",
    help_text="Department this user belongs to",
)

    is_active = models.BooleanField(
        default=True,
        help_text="Unchecked instead of deleting a user, so their history survives",
    )
    is_staff = models.BooleanField(
        default=False,
        help_text="Allows access to Django Admin at /admin/",
    )
    is_verified = models.BooleanField(
         default=False,
         help_text="Set automatically the first time this user logs in successfully. "
         "Not the same as is_active — a user can be active but never verified.",
    )
    is_superuser = models.BooleanField(
        default=False,
        help_text="Bypasses every permission check",
    )

    # `through=` points the many-to-many at our own `user_roles` table so it
    # can carry the extra `assigned_by` / `assigned_at` columns. `UserRole`
    # has two foreign keys to `User` (the holder and the admin who granted
    # the role), so `through_fields` tells Django which one is the holder.
    roles = models.ManyToManyField(
        Role,
        through="UserRole",
        through_fields=("user", "role"),
        related_name="users",
    )

    objects = UserManager()

    USERNAME_FIELD = "username"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["email"]  # prompted for by `createsuperuser`

    class Meta:
        db_table = "users"
        ordering = ["username"]

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        # Normalising here (not only in the manager) means every write path
        # — admin, forms, shell — stores the same casing, so the unique
        # constraint on `email` actually prevents duplicate accounts.
        self.email = self.email.lower().strip()
        return super().save(*args, **kwargs)

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username

    def get_short_name(self):
        return self.first_name or self.username

    # ------------------------------------------------------------------
    # Authorisation
    # ------------------------------------------------------------------
    @property
    def role_codes(self):
        """Set of role codes this user holds, e.g. `{"AGENT"}`."""
        if not hasattr(self, "_role_code_cache"):
            self._role_code_cache = set(self.roles.values_list("code", flat=True))
        return self._role_code_cache

    def has_role(self, code):
        """`user.has_role(RoleCode.SUPERVISOR)`"""
        return str(code) in self.role_codes
    @property
    def has_role_agent(self):
        return self.has_role(RoleCode.AGENT)

    @property
    def has_role_supervisor(self):
        return self.has_role(RoleCode.SUPERVISOR)

    @property
    def has_role_admin(self):
        return self.has_role(RoleCode.ADMIN)

    @property
    def has_role_requester(self):
        return self.has_role(RoleCode.REQUESTER)

    @property
    def is_admin(self):
        """True for the seeded superuser AND for anyone granted the ADMIN
        role through the RBAC tables. Use this (not `is_superuser` alone)
        anywhere "is this person an admin" is being decided, so granting
        the ADMIN role through the UI actually has an effect."""
        return self.is_superuser or self.has_role_admin

    @property
    def permission_codes(self):
        """Every permission code granted by any of this user's roles.

        Cached on the instance after the first read — rendering a ticket list
        calls `has_permission()` once per row, and that must not be one query
        per row. Django's own `ModelBackend` caches permissions the same way.
        Call `refresh_permission_cache()` after changing a user's roles inside
        a single request.
        """
        if not hasattr(self, "_permission_code_cache"):
            self._permission_code_cache = set(
                Permission.objects.filter(role_permissions__role__user_roles__user=self)
                .values_list("code", flat=True)
                .distinct()
            )
        return self._permission_code_cache

    def refresh_permission_cache(self):
        """Drop the cached roles/permissions so the next read hits the database."""
        for attribute in ("_role_code_cache", "_permission_code_cache"):
            if hasattr(self, attribute):
                delattr(self, attribute)

    def has_permission(self, code):
        """The permission check to use everywhere in ResolveAI.

            if not request.user.has_permission("ticket.assign"):
                raise PermissionDenied

        Inactive users are refused, superusers are always allowed.
        """
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        return str(code) in self.permission_codes

    # Django Admin calls these two. Ours answer from `is_superuser` only,
    # because ResolveAI's own permissions (`ticket.assign`) are a different
    # vocabulary from Django's model permissions (`tickets.add_ticket`).
    def has_perm(self, perm, obj=None):
        return self.is_active and self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_active and self.is_superuser


class UserRole(models.Model):
    """Which roles a user has — the `user_roles` mapping table.

    A plain `ManyToManyField` would have been enough for user + role, but
    the schema requires recording *who* granted the role and *when*, so the
    join table is an explicit model.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="user_roles")
    assigned_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="role_assignments_made",
        help_text="Admin who granted the role; NULL when granted by the system",
    )
    assigned_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "user_roles"
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="uniq_user_role"),
        ]

    def __str__(self):
        return f"{self.user} -> {self.role}"


class RolePermission(models.Model):
    """What a role is allowed to do — the `role_permissions` mapping table."""

    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, related_name="role_permissions"
    )

    class Meta:
        db_table = "role_permissions"
        constraints = [
            models.UniqueConstraint(fields=["role", "permission"], name="uniq_role_permission"),
        ]

    def __str__(self):
        return f"{self.role} -> {self.permission}"
