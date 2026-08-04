from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("dashboard/", views.dashboard, name="dashboard-page"),
    path("login/", views.login_page, name="login"),
    path("signup/", views.signup_page, name="signup"),
    path("logout/", views.logout_view, name="logout"),
]
