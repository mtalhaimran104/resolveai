"""
Django settings for the ResolveAI web portal (Phase 1).

Configuration values are read from environment variables so the same
settings file works both in Docker and on a developer's machine, without
needing a separate settings file per environment.
"""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default="False"):
    return os.getenv(name, default).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


SECRET_KEY = os.getenv("SECRET_KEY", "change-me")

DEBUG = env_bool("DEBUG", "True")

AI_SERVICE_URL = os.getenv(
    "AI_SERVICE_URL",
    "http://ai_service:8000",
)

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "ALLOWED_HOSTS",
        "localhost,127.0.0.1",
    ).split(",")
    if host.strip()
]


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # ResolveAI apps
    "core",
    "accounts",
    "dashboard",
    "organization",
    "classification",
    "tickets",
    "ai",
    "knowledge",
]


# ResolveAI uses its own user model instead of django.contrib.auth.User.
# This must be set before the first `migrate` on a fresh database;
# changing it afterwards means recreating the database.
AUTH_USER_MODEL = "accounts.User"


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "config.urls"


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.csrf",
                "accounts.context_processors.user_roles",
                "accounts.context_processors.sidebar_counts",
            ],
        },
    },
]


WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# Database
# ResolveAI uses MySQL, running in its own container in this phase.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv(
            "MYSQL_DATABASE",
            "resolve_ai",
        ),
        "USER": os.getenv(
            "MYSQL_USER",
            "resolve_ai_user",
        ),
        "PASSWORD": os.getenv(
            "MYSQL_PASSWORD",
            "resolve_ai_password",
        ),
        "HOST": os.getenv(
            "MYSQL_HOST",
            "localhost",
        ),
        "PORT": os.getenv(
            "MYSQL_PORT",
            "3307",
        ),
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        )
    },
]


# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Karachi"
USE_I18N = True
USE_TZ = True


# Static files
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]


# User-uploaded files (ticket attachments)
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"
