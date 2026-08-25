from django.urls import path
from . import views

# NOTE: login/logout/register/password-reset used to be duplicated here
# AND in accounts/urls.py, with no namespacing on either include(). Since
# both apps defined url names like "login" with no args, whichever was
# registered later in config/urls.py silently won every {% url %}/reverse()
# call, permanently shadowing the other app's views. accounts/urls.py is
# now the single source of truth for all of those; this app only owns the
# dashboard and the general admin "system" pages that don't have a home
# in any other app yet.

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    # Sidebar "SYSTEM" section for admins. There's no dedicated model for
    # any of these yet (no Notification/AuditLog/SystemSetting tables), so
    # these are thin views over the existing static templates - same
    # "static mock data, not yet implemented" pattern already used by
    # agent_faq_list(). Wire them up to real models when those phases land.
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/settings/", views.notification_settings, name="notification_settings"),
    path("settings/general/", views.general_settings, name="general_settings"),
    path("settings/email/", views.email_settings, name="email_settings"),
    path("settings/security/", views.security_settings, name="security_settings"),
    path("settings/tickets/", views.ticket_settings, name="ticket_settings"),
    path("system-health/", views.system_health, name="system_health"),
    path("activity-log/", views.activity_log, name="activity_log"),

    # Demo Knowledge Base / AI pages copied from supplied HTML template.
    path("knowledge-base/article-list.html", views.demo_kb_article_list, name="demo_kb_article_list"),
    path("knowledge-base/article-create.html", views.demo_kb_article_create, name="demo_kb_article_create"),
    path("knowledge-base/public-knowledge-base.html", views.demo_kb_public, name="demo_kb_public"),
    path("knowledge-base/article-detail.html", views.demo_kb_article_detail, name="demo_kb_article_detail"),
    path("knowledge-base/article-edit.html", views.demo_kb_article_edit, name="demo_kb_article_edit"),
    path("knowledge-base/article-versions.html", views.demo_kb_article_versions, name="demo_kb_article_versions"),

    path("ai/ai-overview.html", views.demo_ai_overview, name="demo_ai_overview"),
    path("ai/ai-analysis-list.html", views.demo_ai_analysis_list, name="demo_ai_analysis_list"),
    path("ai/ai-analysis-detail.html", views.demo_ai_analysis_detail, name="demo_ai_analysis_detail"),
    path("ai/ai-suggestions.html", views.demo_ai_suggestions, name="demo_ai_suggestions"),
    path("ai/low-confidence-results.html", views.demo_ai_low_confidence, name="demo_ai_low_confidence"),
    path("ai/model-performance.html", views.demo_ai_model_performance, name="demo_ai_model_performance"),
    path("ai/ai-service-status.html", views.demo_ai_service_status, name="demo_ai_service_status"),
]
