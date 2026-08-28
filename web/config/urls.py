from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.urls import include, path
urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include("dashboard.urls")),
    path("tickets/", include("tickets.urls")),
    path("api/v1/ai/", include("ai.urls")),
    path("", include("organization.urls")),
    path("", include("classification.urls")),
    path("assets/<path:path>", serve, {"document_root": settings.BASE_DIR / "assets"}),
    path("knowledge-base/", include("knowledge.urls")),
]
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
