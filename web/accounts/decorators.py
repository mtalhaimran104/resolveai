from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def _deny(request, message="You do not have permission to access this page."):
    messages.error(request, message)
    return redirect("dashboard")


def role_required(*role_codes):
    """Allow access if the user holds ANY of the given role codes.

    Superusers always pass. Usage:
        @role_required(RoleCode.AGENT, RoleCode.SUPERVISOR)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")
            if request.user.is_admin:
                return view_func(request, *args, **kwargs)
            if any(request.user.has_role(code) for code in role_codes):
                return view_func(request, *args, **kwargs)
            return _deny(request)
        return wrapper
    return decorator


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if not request.user.is_admin:
            return _deny(request)
        return view_func(request, *args, **kwargs)
    return wrapper


def supervisor_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if not (request.user.is_admin or request.user.has_role("SUPERVISOR")):
            return _deny(request)
        return view_func(request, *args, **kwargs)
    return wrapper


def agent_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if not (request.user.is_admin or request.user.has_role("AGENT")):
            return _deny(request)
        return view_func(request, *args, **kwargs)
    return wrapper


def supervisor_or_admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if not (request.user.is_admin or request.user.has_role("SUPERVISOR")):
            return _deny(request)
        return view_func(request, *args, **kwargs)
    return wrapper
def agent_or_supervisor_required(view_func):
    """Allow agents and supervisors (and superusers). Used for the shared
    ticket queue screens (unassigned / assigned / assign-to-agent) so agents
    can self-assign and unassign tickets, while supervisors keep full access.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if not (
            request.user.is_admin
            or request.user.has_role("SUPERVISOR")
            or request.user.has_role("AGENT")
        ):
            return _deny(request)
        return view_func(request, *args, **kwargs)
    return wrapper