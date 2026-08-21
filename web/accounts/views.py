from django.contrib.auth import login
from django.http import JsonResponse
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth import get_user_model
from django.contrib import messages
from .forms import LoginForm, SignUpForm
from .models import Role, RoleCode, UserRole
from .decorators import admin_required
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
    next_page = reverse_lazy("accounts:login")


@transaction.atomic
def signup_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            requester_role = Role.objects.get(code=RoleCode.REQUESTER)
            UserRole.objects.create(user=user, role=requester_role, assigned_by=None)
            login(request, user)
            return redirect("dashboard")
    else:
        form = SignUpForm()

    return render(request, "auth/register.html", {"form": form})

@admin_required
def user_list(request):
    users = User.objects.all().order_by("username")
    for u in users:
        u.role_list = list(UserRole.objects.filter(user=u).values_list("role__code", flat=True))
    return render(request, "accounts/user_list.html", {"users": users, "page_title": "All Users"})


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