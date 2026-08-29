from django.db import models
from tickets.models import TicketCategory
# Create your models here.
from django.conf import settings
from django.db import models

from core.models import TimeStampedModel






class KnowledgeArticle(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        ARCHIVED = "ARCHIVED", "Archived"

    title = models.CharField(max_length=255)

    slug = models.SlugField(
        max_length=255,
        unique=True,
    )

    content = models.TextField()

    excerpt = models.TextField(
        blank=True,
    )

    category = models.ForeignKey(
        
        TicketCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="knowledge_articles",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    is_public = models.BooleanField(
        default=False,
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="knowledge_articles",
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "knowledge_articles"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class KnowledgeArticleVersion(models.Model):
    article = models.ForeignKey(
        KnowledgeArticle,
        on_delete=models.CASCADE,
        related_name="versions",
    )

    version_number = models.PositiveIntegerField()

    title = models.CharField(
        max_length=255,
    )

    content = models.TextField()

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="knowledge_article_versions",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "knowledge_article_versions"
        ordering = ["-version_number"]

        constraints = [
            models.UniqueConstraint(
                fields=["article", "version_number"],
                name="uniq_article_version",
            ),
        ]

    def __str__(self):
        return f"{self.article.title} v{self.version_number}"

# class KnowledgeArticle(TimeStampedModel):
#     class Status(models.TextChoices):
#         DRAFT = "DRAFT", "Draft"
#         PUBLISHED = "PUBLISHED", "Published"
#         ARCHIVED = "ARCHIVED", "Archived"

#     title = models.CharField(max_length=255)
#     slug = models.SlugField(max_length=255, unique=True)
#     content = models.TextField()
#     excerpt = models.TextField(blank=True)

#     status = models.CharField(
#         max_length=20,
#         choices=Status.choices,
#         default=Status.DRAFT,
#     )

#     is_public = models.BooleanField(default=False)

#     author = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.PROTECT,
#         related_name="knowledge_articles",
#     )

#     published_at = models.DateTimeField(null=True, blank=True)

#     class Meta:
#         db_table = "knowledge_articles"
#         ordering = ["-created_at"]

#     def __str__(self):
#         return self.title


# class KnowledgeArticleVersion(models.Model):
#     article = models.ForeignKey(
#         KnowledgeArticle,
#         on_delete=models.CASCADE,
#         related_name="versions",
#     )

#     version_number = models.PositiveIntegerField()
#     title = models.CharField(max_length=255)
#     content = models.TextField()

#     created_by = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.PROTECT,
#         related_name="knowledge_article_versions",
#     )

#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         db_table = "knowledge_article_versions"
#         ordering = ["-version_number"]

#         constraints = [
#             models.UniqueConstraint(
#                 fields=["article", "version_number"],
#                 name="uniq_article_version",
#             ),
#         ]

#     def __str__(self):
#         return f"{self.article.title} v{self.version_number}"