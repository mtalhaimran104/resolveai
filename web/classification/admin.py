from django.contrib import admin

# Register your models here.

from .models import TicketCategory


@admin.register(TicketCategory)
class TicketCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "department", "is_active")
    list_filter = ("department", "is_active")
    search_fields = ("name", "code")