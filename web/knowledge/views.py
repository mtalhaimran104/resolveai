from django.shortcuts import render
from .models import KnowledgeArticle, KnowledgeArticleVersion

from .forms import KnowledgeArticleForm
# Create your views here.
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from accounts.decorators import agent_or_supervisor_required

from tickets.models import TicketCategory


@agent_or_supervisor_required
def article_list(request):
    articles = KnowledgeArticle.objects.select_related(
        "author"
    ).all()

    return render(
        request,
        "knowledge-base/article-list.html",
        {
            "articles": articles,
            "current": "knowledge_article_list",
        },
    )
@agent_or_supervisor_required
def article_create(request):
    categories = TicketCategory.objects.filter(
        is_active=True
    ).order_by("name")

    if request.method == "POST":
        form = KnowledgeArticleForm(request.POST)

        if form.is_valid():
            article = form.save(commit=False)

            article.author = request.user

            # Generate slug if the user left it blank
            if not article.slug:
                slug = slugify(article.title)

                original_slug = slug
                counter = 2

                while KnowledgeArticle.objects.filter(
                    slug=slug
                ).exists():
                    slug = f"{original_slug}-{counter}"
                    counter += 1

                article.slug = slug

            # Set publish information
            if article.status == KnowledgeArticle.Status.PUBLISHED:
                article.is_public = True
                article.published_at = (
                    article.published_at or timezone.now()
                )
            else:
                article.published_at = None

            article.save()

            # Save tags if your model uses a normal field
            form.save_m2m()

            # Create first version
            KnowledgeArticleVersion.objects.create(
                article=article,
                version_number=1,
                title=article.title,
                content=article.body,
                created_by=request.user,
            )

            if article.status == KnowledgeArticle.Status.PUBLISHED:
                messages.success(
                    request,
                    f"Article '{article.title}' published successfully.",
                )
            else:
                messages.success(
                    request,
                    f"Article '{article.title}' saved as draft successfully.",
                )

            return redirect(
                "knowledge_article_list"
            )

    else:
        form = KnowledgeArticleForm()

    return render(
        request,
        "knowledge-base/article-create.html",
        {
            "form": form,
            "categories": categories,
            "current": "knowledge_article_create",
        },
    )
# @agent_or_supervisor_required
# def article_create(request):
#     if request.method == "POST":
#         title = request.POST.get("title", "").strip()
#         content = request.POST.get("content", "").strip()
#         excerpt = request.POST.get("excerpt", "").strip()
#         status = request.POST.get(
#             "status",
#             KnowledgeArticle.Status.DRAFT,
#         )

#         errors = []

#         if not title:
#             errors.append("Article title is required.")

#         if not content:
#             errors.append("Article content is required.")

#         if errors:
#             return render(
#                 request,
#                 "knowledge-base/article-create.html",
#                 {
#                     "current": "knowledge_article_create",

#                     # Keep everything the user entered
#                     "title": title,
#                     "content": content,
#                     "excerpt": excerpt,
#                     "status": status,

#                     # Send errors to template
#                     "errors": errors,
#                 },
#             )

#         slug = slugify(title)

#         original_slug = slug
#         counter = 2

#         while KnowledgeArticle.objects.filter(slug=slug).exists():
#             slug = f"{original_slug}-{counter}"
#             counter += 1

#         article = KnowledgeArticle.objects.create(
#             title=title,
#             slug=slug,
#             content=content,
#             excerpt=excerpt,
#             status=status,
#             is_public=(
#                 status == KnowledgeArticle.Status.PUBLISHED
#             ),
#             author=request.user,
#             published_at=(
#                 timezone.now()
#                 if status == KnowledgeArticle.Status.PUBLISHED
#                 else None
#             ),
#         )

#         KnowledgeArticleVersion.objects.create(
#             article=article,
#             version_number=1,
#             title=article.title,
#             content=article.content,
#             created_by=request.user,
#         )

#         messages.success(
#             request,
#             f"Article '{article.title}' created successfully.",
#         )

#         return redirect(
#             "knowledge_article_detail",
#             pk=article.pk,
#         )

#     return render(
#         request,
#         "knowledge-base/article-create.html",
#         {
#             "current": "knowledge_article_create",
#         },
#     )

# @agent_or_supervisor_required
# def article_create(request):
#     categories = TicketCategory.objects.filter(
#         is_active=True
#     ).order_by("name")

#     if request.method == "POST":
#         title = request.POST.get("title", "").strip()
#         content = request.POST.get("content", "").strip()
#         excerpt = request.POST.get("excerpt", "").strip()

#         category_id = request.POST.get("category", "").strip()

#         action = request.POST.get("action", "draft")

#         if action == "publish":
#             status = KnowledgeArticle.Status.PUBLISHED
#         else:
#             status = KnowledgeArticle.Status.DRAFT

#         errors = []

#         if not title:
#             errors.append("Article title is required.")

#         if not content:
#             errors.append("Article content is required.")

#         if not category_id:
#             errors.append("Please choose a category.")

#         category = None

#         if category_id:
#             category = TicketCategory.objects.filter(
#                 pk=category_id,
#                 is_active=True,
#             ).first()

#             if not category:
#                 errors.append("Selected category is invalid.")

#         # If there are errors, return the same page
#         # with all entered data still populated.
#         if errors:
#             return render(
#                 request,
#                 "knowledge-base/article-create.html",
#                 {
#                     "current": "knowledge_article_create",
#                     "title": title,
#                     "content": content,
#                     "excerpt": excerpt,
#                     "status": status,
#                     "selected_category": category_id,
#                     "categories": categories,
#                     "errors": errors,
#                 },
#             )

#         # Generate unique slug
#         slug = slugify(title)

#         original_slug = slug
#         counter = 2

#         while KnowledgeArticle.objects.filter(slug=slug).exists():
#             slug = f"{original_slug}-{counter}"
#             counter += 1

#         article = KnowledgeArticle.objects.create(
#             title=title,
#             slug=slug,
#             content=content,
#             excerpt=excerpt,
#             category=category,
#             status=status,
#             is_public=(
#                 status == KnowledgeArticle.Status.PUBLISHED
#             ),
#             author=request.user,
#             published_at=(
#                 timezone.now()
#                 if status == KnowledgeArticle.Status.PUBLISHED
#                 else None
#             ),
#         )

#         KnowledgeArticleVersion.objects.create(
#             article=article,
#             version_number=1,
#             title=article.title,
#             content=article.content,
#             created_by=request.user,
#         )

#         # SUCCESS MESSAGE
#         if status == KnowledgeArticle.Status.PUBLISHED:
#             messages.success(
#                 request,
#                 f"Article '{article.title}' published successfully.",
#             )
#         else:
#             messages.success(
#                 request,
#                 f"Article '{article.title}' saved as draft successfully.",
#             )

#         # GO TO ARTICLE LIST
#         return redirect("knowledge_article_list")

#     return render(
#         request,
#         "knowledge-base/article-create.html",
#         {
#             "current": "knowledge_article_create",
#             "categories": categories,
#         },
#     )
@agent_or_supervisor_required
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


@agent_or_supervisor_required
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


@agent_or_supervisor_required
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


@agent_or_supervisor_required
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
        "knowledge-base/public-knowledge-base.html",
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