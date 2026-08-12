from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect

from accounts.forms import SignUpForm, LoginForm

from django.http import JsonResponse
from django.contrib.auth import get_user_model

User = get_user_model()

def check_username(request):
    username = request.GET.get("username", "").strip()
    exists = User.objects.filter(username=username).exists()
    return JsonResponse({"available": not exists})
@login_required
def dashboard(request):
    context = {
        "page_title": "Dashboard",
        "summary_cards": SUMMARY_CARDS,
        "recent_tickets": RECENT_TICKETS,
        "status_summary": STATUS_SUMMARY,
    }
    return render(request, "dashboard/index.html", context)


def login_page(request):
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect("dashboard")
    else:
        form = LoginForm()
    return render(request, "auth/login.html", {"form": form})


def register_page(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("dashboard")
    else:
        form = SignUpForm()
    return render(request, "auth/register.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("login")


# Phase 1 has no ticket models yet, so the dashboard is built from static
# mock data. This will be replaced with real database queries once the
# ticket-management app is introduced in a later phase.

SUMMARY_CARDS = [
    {"label": "Open Tickets", "value": 24, "icon": "bi-envelope-open-fill", "color": "primary"},
    {"label": "In Progress", "value": 11, "icon": "bi-arrow-repeat", "color": "info"},
    {"label": "Waiting for User", "value": 7, "icon": "bi-hourglass-split", "color": "warning"},
    {"label": "Resolved Today", "value": 9, "icon": "bi-check-circle-fill", "color": "success"},
]

RECENT_TICKETS = [
    {
        "number": "RA-2026-000101",
        "subject": "Unable to access student portal",
        "requester": "Ayesha Khan",
        "priority": "High",
        "status": "In Progress",
        "status_class": "in-progress",
        "assigned_to": "Faiza Tehreem",
        "updated": "10 minutes ago",
    },
    {
        "number": "RA-2026-000098",
        "subject": "Fee challan not generated for Fall semester",
        "requester": "Talha Ahmed",
        "priority": "Medium",
        "status": "Open",
        "status_class": "open",
        "assigned_to": "Unassigned",
        "updated": "32 minutes ago",
    },
    {
        "number": "RA-2026-000095",
        "subject": "Wi-Fi not working in hostel block C",
        "requester": "Maryam Waseem",
        "priority": "Critical",
        "status": "Waiting for User",
        "status_class": "waiting",
        "assigned_to": "Hamza Tariq",
        "updated": "1 hour ago",
    },
    {
        "number": "RA-2026-000091",
        "subject": "Request to update transcript address",
        "requester": "Bilal Sultan",
        "priority": "Low",
        "status": "Resolved",
        "status_class": "resolved",
        "assigned_to": "Faiza Tehreem",
        "updated": "3 hours ago",
    },
    {
        "number": "RA-2026-000087",
        "subject": "LMS course content missing for CS-301",
        "requester": "Sana Iqbal",
        "priority": "Medium",
        "status": "Closed",
        "status_class": "closed",
        "assigned_to": "Zainab Malik",
        "updated": "Yesterday",
    },
]

STATUS_SUMMARY = [
    {"label": "Open", "count": 24, "percent": 34, "color": "primary"},
    {"label": "In Progress", "count": 11, "percent": 16, "color": "info"},
    {"label": "Waiting for User", "count": 7, "percent": 10, "color": "warning"},
    {"label": "Resolved", "count": 18, "percent": 25, "color": "success"},
    {"label": "Closed", "count": 11, "percent": 15, "color": "secondary"},
]