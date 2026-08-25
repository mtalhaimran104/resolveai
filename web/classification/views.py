from django.shortcuts import render

# Create your views here.
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import admin_required
from core.pagination import paginate_queryset
from organization.models import Department
from .models import TicketCategory


@admin_required
def category_list(request):
    categories = TicketCategory.objects.select_related("department").all().order_by("name")
    page_obj = paginate_queryset(categories, request)
    return render(request, "categories/category-list.html", {
        "categories": page_obj,
        "page_obj": page_obj,
        "current": "category-list",
    })


@admin_required
def category_detail(request, pk):
    category = get_object_or_404(TicketCategory, pk=pk)
    return render(request, "categories/category-detail.html", {
        "category": category,
        "current": "category-detail",
    })


def _department_from_code(code):
    return Department.objects.filter(code__iexact=code).first()


@admin_required
def category_create(request):
    if request.method == "POST":
        name = request.POST.get("catName", "").strip()
        code = request.POST.get("catCode", "").strip().upper()
        department = _department_from_code(request.POST.get("catDepartment", ""))
        description = request.POST.get("catDescription", "").strip()
        is_active = request.POST.get("catActive") == "on"

        if not name:
            messages.error(request, "Category name is required.")
        elif not code:
            messages.error(request, "Category code is required.")
        elif TicketCategory.objects.filter(code=code).exists():
            messages.error(request, "A category with this code already exists.")
        else:
            category = TicketCategory.objects.create(
                name=name,
                code=code,
                department=department,
                description=description,
                is_active=is_active,
            )
            messages.success(request, f"Category '{category.name}' created successfully.")
            return redirect("category_detail", pk=category.pk)

    return render(request, "categories/category-create.html", {"current": "category-create"})


@admin_required
def category_edit(request, pk):
    category = get_object_or_404(TicketCategory, pk=pk)

    if request.method == "POST":
        name = request.POST.get("catName", "").strip()
        code = request.POST.get("catCode", "").strip().upper()
        department = _department_from_code(request.POST.get("catDepartment", ""))
        description = request.POST.get("catDescription", "").strip()
        is_active = request.POST.get("catActive") == "on"

        if not name:
            messages.error(request, "Category name is required.")
        elif not code:
            messages.error(request, "Category code is required.")
        elif TicketCategory.objects.filter(code=code).exclude(pk=category.pk).exists():
            messages.error(request, "A category with this code already exists.")
        else:
            category.name = name
            category.code = code
            category.department = department
            category.description = description
            category.is_active = is_active
            category.save()
            messages.success(request, f"Category '{category.name}' updated successfully.")
            return redirect("category_detail", pk=category.pk)

    return render(request, "categories/category-edit.html", {
        "category": category,
        "current": "category-edit",
    })


@admin_required
def category_toggle_status(request, pk):
    category = get_object_or_404(TicketCategory, pk=pk)

    if request.method == "POST":
        category.is_active = not category.is_active
        category.save(update_fields=["is_active"])

        messages.success(
            request,
            f"Category '{category.name}' is now "
            f"{'active' if category.is_active else 'inactive'}.",
        )

    return redirect("category-detail", pk=category.pk)