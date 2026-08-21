from django.contrib import admin

# Register your models here.

from .models import Ticket, TicketComment, TicketAttachment, TicketHistory


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("ticket_number", "subject", "requester", "priority", "status", "assigned_to", "created_at")
    list_filter = ("status", "priority", "department", "category")
    search_fields = ("ticket_number", "subject", "requester__username")


@admin.register(TicketComment)
class TicketCommentAdmin(admin.ModelAdmin):
    list_display = ("ticket", "author", "created_at")
    search_fields = ("ticket__ticket_number", "author__username", "message")


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display = ("ticket", "original_filename", "uploaded_by", "size_bytes", "created_at")
    search_fields = ("ticket__ticket_number", "original_filename", "uploaded_by__username")


@admin.register(TicketHistory)
class TicketHistoryAdmin(admin.ModelAdmin):
    list_display = ("ticket", "action", "actor", "created_at")
    list_filter = ("action",)
    search_fields = ("ticket__ticket_number", "description")