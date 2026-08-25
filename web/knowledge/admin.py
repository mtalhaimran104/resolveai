from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import KnowledgeArticle, KnowledgeArticleVersion


@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "status",
        "is_public",
        "author",
        "created_at",
    )
    list_filter = (
        "status",
        "is_public",
    )
    search_fields = (
        "title",
        "content",
        "excerpt",
    )
    prepopulated_fields = {
        "slug": ("title",),
    }


@admin.register(KnowledgeArticleVersion)
class KnowledgeArticleVersionAdmin(admin.ModelAdmin):
    list_display = (
        "article",
        "version_number",
        "created_by",
        "created_at",
    )
    search_fields = ("article__title",)