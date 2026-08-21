"""
Fires on Django's built-in `user_logged_in` signal, which every successful
login goes through — Django's own `LoginView`, `authenticate()` + `login()`
called manually (as in ResolveAI's signup flow), and Django Admin's login
page all raise it. That means this one signal handler covers every entry
point in the project without needing to duplicate the "mark verified" logic
inside each view.
"""
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def mark_user_verified(sender, request, user, **kwargs):
    if not user.is_verified:
        user.is_verified = True
        user.save(update_fields=["is_verified", "updated_at"])