from .models import UserRole, RoleCode


def user_roles(request):
    if request.user.is_authenticated:
        codes = list(UserRole.objects.filter(user=request.user).values_list("role__code", flat=True))
    else:
        codes = []
    return {"user_role_codes": codes}


def sidebar_counts(request):
    """Live ticket counts shown as bold badges on relevant sidebar links.
    Only computed for authenticated agents/supervisors/admins to avoid an
    extra query on every page for requesters (who don't see these links)."""
    user = request.user
    if not user.is_authenticated:
        return {}
    if not (user.is_superuser or user.has_role(RoleCode.SUPERVISOR) or user.has_role(RoleCode.AGENT)):
        return {}

    from tickets.models import Ticket

    counts = {
        "sidebar_unassigned_count": Ticket.objects.filter(assigned_to__isnull=True).count(),
    }
    if user.is_superuser or user.has_role(RoleCode.SUPERVISOR):
        counts["sidebar_assigned_count"] = Ticket.objects.filter(assigned_to__isnull=False).count()
    if user.has_role(RoleCode.AGENT):
        counts["sidebar_assigned_to_me_count"] = Ticket.objects.filter(assigned_to=user).count()
    return counts