from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from accounts.decorators import supervisor_or_admin_required
# from accounts.decorators import admin_required
from core.pagination import paginate_queryset
from .models import Department


@supervisor_or_admin_required
def department_list(request):
    departments = Department.objects.all().order_by("name")
    page_obj = paginate_queryset(departments, request)

    return render(
        request,
        "departments/department-list.html",
        {
            "departments": page_obj,
            "page_obj": page_obj,
        },
    )


@supervisor_or_admin_required
def department_detail(request, pk):
    department = get_object_or_404(Department, pk=pk)

    return render(
        request,
        "departments/department-detail.html",
        {
            "department": department,
        },
    )


@supervisor_or_admin_required
def department_create(request):
    if request.method == "POST":
        name = request.POST.get("deptName", "").strip()
        code = request.POST.get("deptCode", "").strip().upper()
        description = request.POST.get("deptDescription", "").strip()
        is_active = request.POST.get("deptActive") == "on"

        if not name:
            messages.error(request, "Department name is required.")
        elif not code:
            messages.error(request, "Department code is required.")
        elif not description:
            messages.error(request, "Department description is required.")
        elif Department.objects.filter(code=code).exists():
            messages.error(
                request,
                "A department with this code already exists.",
            )
        else:
            department = Department.objects.create(
                name=name,
                code=code,
                description=description,
                is_active=is_active,
            )

            messages.success(
                request,
                f"Department '{department.name}' created successfully.",
            )

            return redirect(
                "department_detail",
                pk=department.pk,
            )

    return render(
        request,
        "departments/department-create.html",
        {
        },
    )


@supervisor_or_admin_required
def department_edit(request, pk):
    department = get_object_or_404(Department, pk=pk)

    if request.method == "POST":
        name = request.POST.get("deptName", "").strip()
        code = request.POST.get("deptCode", "").strip().upper()
        description = request.POST.get("deptDescription", "").strip()
        is_active = request.POST.get("deptActive") == "on"

        if not name:
            messages.error(request, "Department name is required.")
        elif not code:
            messages.error(request, "Department code is required.")
        elif not description:
            messages.error(request, "Department description is required.")
        elif (
            Department.objects
            .filter(code=code)
            .exclude(pk=department.pk)
            .exists()
        ):
            messages.error(
                request,
                "A department with this code already exists.",
            )
        else:
            department.name = name
            department.code = code
            department.description = description
            department.is_active = is_active
            department.save()

            messages.success(
                request,
                f"Department '{department.name}' updated successfully.",
            )

            return redirect(
                "department_detail",
                pk=department.pk,
            )

    return render(
        request,
        "departments/department-edit.html",
        {
            "department": department,
        },
    )


@supervisor_or_admin_required
def department_toggle_status(request, pk):
    department = get_object_or_404(Department, pk=pk)

    if request.method == "POST":
        department.is_active = not department.is_active
        department.save(update_fields=["is_active"])

        messages.success(
            request,
            f"Department '{department.name}' is now "
            f"{'active' if department.is_active else 'inactive'}.",
        )

    return redirect("department_detail", pk=department.pk)