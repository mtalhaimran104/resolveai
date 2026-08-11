from django.urls import path
from django.contrib.auth import views as auth_views


from . import views

urlpatterns = [
    path('', views.home_page, name='home'),
    path("", views.dashboard, name="dashboard"),
    path("dashboard/", views.dashboard, name="dashboard-page"),
    path("login/", views.login_page, name="login"),
    path("signup/", views.signup_page, name="register"),
    path("logout/", views.logout_view, name="logout"),
     path('forgot-password/',
         auth_views.PasswordResetView.as_view(
             template_name='auth/forgot-password.html',
             email_template_name='auth/password-reset-email.html',
             subject_template_name='auth/password-reset-subject.txt',
             success_url='/forgot-password/sent/'
         ),
         name='password_reset'),

    path('forgot-password/sent/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='auth/password-reset-sent.html'
         ),
         name='password_reset_done'),

    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='auth/reset-password.html',
             success_url='/reset/done/'
         ),
         name='password_reset_confirm'),

    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='auth/password-reset-complete.html'
         ),
         name='password_reset_complete'),
]