from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import KnowledgeArticle


@login_required
def public_knowledge_conversation(request):
    articles = KnowledgeArticle.objects.filter(
        status=KnowledgeArticle.Status.PUBLISHED,
        is_public=True,
    ).select_related("author")

    return render(
        request,
        "knowledge-base/public-knowledge-conversation.html",
        {
            "articles": articles,
            "current": "public_knowledge_conversation",
        },
    )