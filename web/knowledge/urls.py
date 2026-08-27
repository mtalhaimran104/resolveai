from django.urls import path

from . import views


urlpatterns = [
    path(
        "article-list.html",
        views.article_list,
        name="knowledge_article_list",
    ),
    path(
        "knowledge/create/",
        views.article_create,
        name="knowledge_article_create",
    ),
    path(
        "knowledge/<int:pk>/",
        views.article_detail,
        name="knowledge_article_detail",
    ),
    path(
        "knowledge/<int:pk>/edit/",
        views.article_edit,
        name="knowledge_article_edit",
    ),
    path(
        "knowledge/<int:pk>/delete/",
        views.article_delete,
        name="knowledge_article_delete",
    ),
    path(
        "knowledge/<int:pk>/publish/",
        views.article_publish,
        name="knowledge_article_publish",
    ),

    # Public knowledge base
    path(
        "knowledge-base/",
        views.public_knowledge_base,
        name="public_knowledge_base",
    ),
    path(
        "knowledge-base/<slug:slug>/",
        views.public_article_detail,
        name="public_article_detail",
    ),
]