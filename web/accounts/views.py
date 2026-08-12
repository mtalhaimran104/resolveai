from django.contrib.auth import login
from django.http import JsonResponse
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.contrib.auth import get_user_model
from .forms import LoginForm, SignUpForm
from .models import Role, RoleCode, UserRole
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