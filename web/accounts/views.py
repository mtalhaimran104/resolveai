from django.contrib.auth import login
from django.http import JsonResponse
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth import get_user_model
from django.contrib import messages
from .forms import LoginForm, SignUpForm
from .models import Role, RoleCode, UserRole, Permission, RolePermission
from .decorators import admin_required
from core.pagination import paginate_queryset
from django.db.models import Count

User = get_user_model()
def check_username(request):
    username = request.GET.get("username", "").strip()
    exists = User.objects.filter(username=username).exists()
    return JsonResponse({"available": not exists})
class ResolveAILoginView(LoginView):
    template_name = "auth/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class ResolveAILogoutView(LogoutView):
    next_page = reverse_lazy("login")


@transaction.atomic
def signup_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            # SignUpForm.save() already grants the REQUESTER role — do not
            # assign it again here, or the second UserRole.objects.create()
            # call raises IntegrityError against the uniq_user_role
            # constraint.
            user = form.save()
            login(request, user)
            return redirect("dashboard")
    else:
        form = SignUpForm()

    return render(request, "auth/register.html", {"form": form})

@admin_required
def user_list(request):
    users = User.objects.all().order_by("username")
    page_obj = paginate_queryset(users, request)
    for u in page_obj:
        u.role_list = list(UserRole.objects.filter(user=u).values_list("role__code", flat=True))
    return render(request, "accounts/user_list.html", {
        "users": page_obj,
        "page_obj": page_obj,
        "page_title": "All Users",
    })


@admin_required
def toggle_user_active(request, pk):
    if request.method == "POST":
        target = get_object_or_404(User, pk=pk)
        if target != request.user:
            target.is_active = not target.is_active
            target.save(update_fields=["is_active"])
            messages.success(request, f"{target.username} is now {'active' if target.is_active else 'inactive'}.")
        else:
            messages.error(request, "You cannot deactivate your own account.")
    return redirect("user_list")


# ---------------------------------------------------------------------
# ROLES & PERMISSIONS
# ---------------------------------------------------------------------

@admin_required
def role_list(request):
    roles = (
        Role.objects
        .annotate(
            user_count=Count(
                "user_roles__user",
                distinct=True,
            ),
            permission_count=Count(
                "role_permissions__permission",
                distinct=True,
            ),
        )
        .order_by("name")
    )

    page_obj = paginate_queryset(roles, request)

    return render(
        request,
        "roles/role-list.html",
        {
            "roles": page_obj,
            "page_obj": page_obj,
            "page_title": "Roles",
        },
    )

@admin_required
def role_create(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        code = request.POST.get("code", "").strip().upper()
        description = request.POST.get("description", "").strip()
        if name and code:
            role = Role.objects.create(name=name, code=code, description=description)
            messages.success(request, f"Role {role.name} created.")
            return redirect("role_list")
        messages.error(request, "Name and code are required.")
    return render(request, "roles/role-create.html", {
        "page_title": "New Role",
    })


@admin_required
def role_edit(request, pk):
    role = get_object_or_404(Role, pk=pk)
    if request.method == "POST":
        role.name = request.POST.get("name", role.name).strip()
        role.description = request.POST.get("description", role.description).strip()
        role.save(update_fields=["name", "description"])
        messages.success(request, f"Role {role.name} updated.")
        return redirect("role_list")
    return render(request, "roles/role-edit.html", {
        "role": role,
        "page_title": f"Edit {role.name}",
    })


@admin_required
def permissions_list(request):
    permissions = Permission.objects.all().order_by("module", "code")
    page_obj = paginate_queryset(permissions, request)
    return render(request, "roles/permissions.html", {
        "permissions": page_obj,
        "page_obj": page_obj,
        "page_title": "Permissions",
    })


@admin_required
def permission_matrix(request):
    roles = list(Role.objects.all())
    permissions = Permission.objects.all().order_by("module", "code")
    granted = set(
        RolePermission.objects.values_list("role_id", "permission_id")
    )

    if request.method == "POST":
        for role in roles:
            for permission in permissions:
                key = f"perm_{role.id}_{permission.id}"
                should_have = request.POST.get(key) == "on"
                has_it = (role.id, permission.id) in granted
                if should_have and not has_it:
                    RolePermission.objects.create(role=role, permission=permission)
                elif not should_have and has_it:
                    RolePermission.objects.filter(role=role, permission=permission).delete()
        messages.success(request, "Permission matrix updated.")
        return redirect("permission_matrix")

    matrix = []
    for permission in permissions:
        row = {"permission": permission, "cells": []}
        for role in roles:
            row["cells"].append({
                "role": role,
                "granted": (role.id, permission.id) in granted,
            })
        matrix.append(row)

    return render(request, "roles/permission-matrix.html", {
        "roles": roles,
        "matrix": matrix,
        "page_title": "Permission Matrix",
    })