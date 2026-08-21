"""
Django Admin registrations for the identity models.

This is the quickest way to *see* that your models and migrations did what
you expected: start the project, log in at /admin/ and browse the tables.

Passwords are shown read-only (as a hash) on purpose — a password must be
set through `set_password()`, never typed into a plain form field. Create
users with `manage.py createsuperuser`, the seed migration, or the signup
view that arrives in Phase 3.
"""

from django.contrib import admin

from .models import Permission, Role, RolePermission, User, UserRole


class UserRoleInline(admin.TabularInline):
    """Lets you edit a user's roles from the user page itself."""

    model = UserRole
    fk_name = "user"
    extra = 0
    autocomplete_fields = ["role"]


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 0
    autocomplete_fields = ["permission"]


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "full_name", "role_list", "is_active", "is_verified", "is_staff", "last_login")
    list_filter = ("is_active", "is_staff", "is_superuser", "roles")
    search_fields = ("username", "email", "first_name", "last_name")
    readonly_fields = ("password", "last_login", "created_at", "updated_at")
    inlines = [UserRoleInline]
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        ("Access", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Timestamps", {"fields": ("last_login", "created_at", "updated_at")}),
    )

    @admin.display(description="Name")
    def full_name(self, obj):
        return obj.get_full_name()

    @admin.display(description="Roles")
    def role_list(self, obj):
        return ", ".join(sorted(obj.role_codes)) or "—"


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_system_role", "permission_count")
    list_filter = ("is_system_role",)
    search_fields = ("name", "code")
    inlines = [RolePermissionInline]

    @admin.display(description="Permissions")
    def permission_count(self, obj):
        return obj.role_permissions.count()


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "module")
    list_filter = ("module",)
    search_fields = ("code", "name")


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "assigned_by", "assigned_at")
    list_filter = ("role",)
    search_fields = ("user__username", "role__code")
    autocomplete_fields = ["user", "role", "assigned_by"]
