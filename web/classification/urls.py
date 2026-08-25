from django.urls import path

from . import views

urlpatterns = [
    path("categories/", views.category_list, name="category_list"),
    path("categories/create/", views.category_create, name="category_create"),
    path("categories/<int:pk>/", views.category_detail, name="category_detail"),
    path("categories/<int:pk>/edit/", views.category_edit, name="category_edit"),
    path(
    "categories/<int:pk>/toggle-status/",
    views.category_toggle_status,
    name="category_toggle_status",
),
]
