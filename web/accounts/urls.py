from django.contrib.auth import views as auth_views
from django.urls import path

from . import views



urlpatterns = [
    # This app is the single source of truth for authentication URLs.
    # (dashboard/urls.py used to duplicate these names with no namespacing,
    # which silently shadowed these views — see dashboard/urls.py.)
    path("register/", views.signup_view, name="register"),
    path("login/", views.ResolveAILoginView.as_view(), name="login"),
    path("logout/", views.ResolveAILogoutView.as_view(), name="logout"),
    path("users/", views.user_list, name="user_list"),
    path("users/<int:pk>/toggle/", views.toggle_user_active, name="toggle_user_active"),

    path("roles/", views.role_list, name="role_list"),
    path("roles/create/", views.role_create, name="role_create"),
    path("roles/<int:pk>/edit/", views.role_edit, name="role_edit"),
    path("permissions/", views.permissions_list, name="permissions_list"),
    path("permissions/matrix/", views.permission_matrix, name="permission_matrix"),

    path(
        "forgot-password/",
        auth_views.PasswordResetView.as_view(
            template_name="auth/forgot-password.html",
            email_template_name="auth/password-reset-email.txt",
            subject_template_name="auth/password-reset-subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "forgot-password/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="auth/password-reset-done.html"),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="auth/reset-password.html",
            success_url="/accounts/reset/done/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(template_name="auth/password-reset-complete.html"),
        name="password_reset_complete",
    ),
    path("check-username/", views.check_username, name="check_username"),
    path("users/", views.user_list, name="user_list"),
    path("users/create/", views.user_create, name="user_create"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
]