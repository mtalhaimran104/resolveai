from .models import UserRole


def user_roles(request):
    if request.user.is_authenticated:
        codes = list(UserRole.objects.filter(user=request.user).values_list("role__code", flat=True))
    else:
        codes = []
    return {"user_role_codes": codes}