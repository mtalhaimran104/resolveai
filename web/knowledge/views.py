from django.shortcuts import render
from .models import KnowledgeArticle, KnowledgeArticleVersion
# Create your views here.
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify

from accounts.decorators import supervisor_or_admin_required
from .models import KnowledgeArticle


@supervisor_or_admin_required
def article_list(request):
    articles = KnowledgeArticle.objects.select_related(
        "author"
    ).all()

    return render(
        request,
        "knowledge/articles.html",
        {
            "articles": articles,
            "current": "knowledge_article_list",
        },
    )


@supervisor_or_admin_required
def article_create(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        content = request.POST.get("content", "").strip()
        excerpt = request.POST.get("excerpt", "").strip()
        status = request.POST.get(
            "status",
            KnowledgeArticle.Status.DRAFT,
        )

        if not title:
            messages.error(request, "Article title is required.")
        elif not content:
            messages.error(request, "Article content is required.")
        else:
            slug = slugify(title)

            original_slug = slug
            counter = 2

            while KnowledgeArticle.objects.filter(slug=slug).exists():
                slug = f"{original_slug}-{counter}"
                counter += 1

            article = KnowledgeArticle.objects.create(
                title=title,
                slug=slug,
                content=content,
                excerpt=excerpt,
                status=status,
                is_public=(
                    status == KnowledgeArticle.Status.PUBLISHED
                ),
                author=request.user,
                published_at=(
                    timezone.now()
                    if status == KnowledgeArticle.Status.PUBLISHED
                    else None
                ),
            )

            KnowledgeArticleVersion.objects.create(
                article=article,
                version_number=1,
                title=article.title,
                content=article.content,
                created_by=request.user,
            )

            messages.success(
                request,
                f"Article '{article.title}' created successfully.",
            )

            return redirect(
                "knowledge_article_detail",
                pk=article.pk,
            )

    return render(
        request,
        "knowledge/article-create.html",
        {
            "current": "knowledge_article_create",
        },
    )


@supervisor_or_admin_required
def article_detail(request, pk):
    article = get_object_or_404(
        KnowledgeArticle.objects.select_related("author"),
        pk=pk,
    )

    return render(
        request,
        "knowledge/article-detail.html",
        {
            "article": article,
            "current": "knowledge_article_detail",
        },
    )


@supervisor_or_admin_required
def article_edit(request, pk):
    article = get_object_or_404(KnowledgeArticle, pk=pk)

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        content = request.POST.get("content", "").strip()
        excerpt = request.POST.get("excerpt", "").strip()
        status = request.POST.get(
            "status",
            KnowledgeArticle.Status.DRAFT,
        )

        if not title:
            messages.error(request, "Article title is required.")
        elif not content:
            messages.error(request, "Article content is required.")
        else:
            article.title = title
            article.content = content
            article.excerpt = excerpt
            article.status = status

            if status == KnowledgeArticle.Status.PUBLISHED:
                article.is_public = True
                article.published_at = (
                    article.published_at or timezone.now()
                )
            else:
                article.is_public = False
                article.published_at = None

            article.save()

            latest_version = article.versions.order_by(
                "-version_number"
            ).first()

            next_version = (
                latest_version.version_number + 1
                if latest_version
                else 1
            )

            KnowledgeArticleVersion.objects.create(
                article=article,
                version_number=next_version,
                title=article.title,
                content=article.content,
                created_by=request.user,
            )

            messages.success(
                request,
                f"Article '{article.title}' updated successfully.",
            )

            return redirect(
                "knowledge_article_detail",
                pk=article.pk,
            )

    return render(
        request,
        "knowledge/article-edit.html",
        {
            "article": article,
            "current": "knowledge_article_edit",
        },
    )


@supervisor_or_admin_required
def article_delete(request, pk):
    article = get_object_or_404(KnowledgeArticle, pk=pk)

    if request.method == "POST":
        title = article.title
        article.delete()

        messages.success(
            request,
            f"Article '{title}' deleted successfully.",
        )

    return redirect("knowledge_article_list")


@supervisor_or_admin_required
def article_publish(request, pk):
    article = get_object_or_404(KnowledgeArticle, pk=pk)

    if request.method == "POST":
        article.status = KnowledgeArticle.Status.PUBLISHED
        article.is_public = True
        article.published_at = timezone.now()
        article.save(
            update_fields=[
                "status",
                "is_public",
                "published_at",
                "updated_at",
            ]
        )

        messages.success(
            request,
            f"Article '{article.title}' published successfully.",
        )

    return redirect(
        "knowledge_article_detail",
        pk=article.pk,
    )


@login_required
def public_knowledge_base(request):
    articles = KnowledgeArticle.objects.filter(
        status=KnowledgeArticle.Status.PUBLISHED,
        is_public=True,
    ).select_related("author")

    return render(
        request,
        "knowledge/public-knowledge-base.html",
        {
            "articles": articles,
            "current": "public_knowledge_base",
        },
    )


@login_required
def public_article_detail(request, slug):
    article = get_object_or_404(
        KnowledgeArticle,
        slug=slug,
        status=KnowledgeArticle.Status.PUBLISHED,
        is_public=True,
    )

    return render(
        request,
        "knowledge/public-article-detail.html",
        {
            "article": article,
            "current": "public_knowledge_base",
        },
    )