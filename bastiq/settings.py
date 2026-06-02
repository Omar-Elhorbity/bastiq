"""
Django settings for the Bastiq project.

Twelve-factor / env-driven: every deployment-specific value comes from the
environment. Secure defaults are applied automatically when ``DJANGO_DEBUG`` is
false (production), so a misconfigured prod box fails closed rather than open.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Small env helpers (no extra dependency — plain os.environ).
# --------------------------------------------------------------------------- #
def env_str(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def env_list(key: str, default: str = "") -> list[str]:
    raw = os.environ.get(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #
DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = env_str("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        # Dev-only fallback; never used when DEBUG is false.
        SECRET_KEY = "django-insecure-dev-key-do-not-use-in-production"  # noqa: S105
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
# Render (and most PaaS) inject an external hostname at runtime.
_render_host = env_str("RENDER_EXTERNAL_HOSTNAME")
if _render_host:
    ALLOWED_HOSTS.append(_render_host)

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Base URL used to build user-facing links (email verification, password reset,
# Stripe checkout redirects). Kept separate from ALLOWED_HOSTS on purpose.
FRONTEND_URL = env_str("FRONTEND_URL", "http://localhost:8000").rstrip("/")


# --------------------------------------------------------------------------- #
# Applications
# --------------------------------------------------------------------------- #
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "drf_spectacular",
]

LOCAL_APPS = [
    "core.apps.CoreConfig",
    "accounts.apps.AccountsConfig",
    "organizations.apps.OrganizationsConfig",
    "billing.apps.BillingConfig",
    "projects.apps.ProjectsConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves static assets (admin, Swagger UI) without a separate
    # web server. Must sit directly after SecurityMiddleware.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "bastiq.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "bastiq.wsgi.application"
ASGI_APPLICATION = "bastiq.asgi.application"


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
DATABASES = {
    "default": dj_database_url.config(
        default=env_str(
            "DATABASE_URL",
            "postgres://postgres:postgres@localhost:5432/bastiq",
        ),
        conn_max_age=env_int("DB_CONN_MAX_AGE", 600),
        conn_health_checks=True,
    )
}


# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": env_int("PASSWORD_MIN_LENGTH", 10)},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Fast hashing for the test suite only (opt-in via env). Keeps the default
# strong PBKDF2 hasher everywhere else.
if env_bool("USE_FAST_PASSWORD_HASHER", False):
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


# --------------------------------------------------------------------------- #
# DRF + JWT + OpenAPI
# --------------------------------------------------------------------------- #
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    # Secure default: every endpoint requires auth unless it explicitly opts out.
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        # Browsable API is an explicit handoff requirement.
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": env_int("DRF_PAGE_SIZE", 20),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": env_str("THROTTLE_ANON", "120/min"),
        "user": env_str("THROTTLE_USER", "1000/min"),
        # Tight scopes for credential-sensitive endpoints (applied per-view in M1).
        "login": env_str("THROTTLE_LOGIN", "10/min"),
        "register": env_str("THROTTLE_REGISTER", "10/hour"),
        "password_reset": env_str("THROTTLE_PASSWORD_RESET", "5/hour"),
        "email_verify": env_str("THROTTLE_EMAIL_VERIFY", "20/hour"),
    },
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("JWT_ACCESS_MINUTES", 30)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env_int("JWT_REFRESH_DAYS", 7)),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    # Signed with SECRET_KEY (HS256) by default.
}

# The schema (/api/schema) and Swagger UI (/api/docs) are public by default
# because the product demo requires a publicly reachable Swagger. Deployments
# that prefer to keep their API surface private can flip DOCS_REQUIRE_AUTH=true
# to require authentication for both. (drf-spectacular's own SERVE_PERMISSIONS
# governs these views — DRF's global IsAuthenticated default does not apply.)
_docs_permission = (
    "rest_framework.permissions.IsAuthenticated"
    if env_bool("DOCS_REQUIRE_AUTH", False)
    else "rest_framework.permissions.AllowAny"
)

SPECTACULAR_SETTINGS = {
    "TITLE": "Bastiq API",
    "DESCRIPTION": (
        "Multi-tenant SaaS backend: authentication, organizations & RBAC, "
        "Stripe billing, and org-scoped resources. Tenant-scoped endpoints "
        "require the `X-Organization-ID` header (validated against membership)."
    ),
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": [_docs_permission],
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api",
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
        "displayRequestDuration": True,
    },
}


# --------------------------------------------------------------------------- #
# Internationalization
# --------------------------------------------------------------------------- #
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# --------------------------------------------------------------------------- #
# Static files (WhiteNoise)
# --------------------------------------------------------------------------- #
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if DEBUG:
    # Serve static from the finders (no collectstatic needed in dev/tests) and
    # avoid WhiteNoise's "missing STATIC_ROOT" warning.
    WHITENOISE_USE_FINDERS = True
    WHITENOISE_AUTOREFRESH = True


# --------------------------------------------------------------------------- #
# Email
# --------------------------------------------------------------------------- #
# "console" logs emails to stdout (dev default). "smtp"/"sendgrid" send via SMTP;
# SendGrid uses the SMTP relay (user "apikey", password = SENDGRID_API_KEY), so
# no extra dependency is needed. Falls back to console if no transport configured.
_email_backend = env_str("EMAIL_BACKEND", "console").lower()
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", "no-reply@bastiq.local")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
SENDGRID_API_KEY = env_str("SENDGRID_API_KEY")

if _email_backend == "locmem":
    # In-memory backend for tests: messages land in django.core.mail.outbox.
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
elif _email_backend in {"smtp", "sendgrid"}:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
    EMAIL_PORT = env_int("EMAIL_PORT", 587)
    if _email_backend == "sendgrid":
        EMAIL_HOST = env_str("EMAIL_HOST", "smtp.sendgrid.net")
        EMAIL_HOST_USER = "apikey"
        EMAIL_HOST_PASSWORD = SENDGRID_API_KEY
    else:
        EMAIL_HOST = env_str("EMAIL_HOST", "localhost")
        EMAIL_HOST_USER = env_str("EMAIL_HOST_USER")
        EMAIL_HOST_PASSWORD = env_str("EMAIL_HOST_PASSWORD")
    # If a transport was requested but no credentials were provided, fall back to
    # console so the app still boots and emails are observable.
    if _email_backend == "sendgrid" and not SENDGRID_API_KEY:
        EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


# --------------------------------------------------------------------------- #
# Celery + Redis
# --------------------------------------------------------------------------- #
REDIS_URL = env_str("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = env_str("CELERY_RESULT_BACKEND", "")
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]


# --------------------------------------------------------------------------- #
# Logging — structured-ish, to stdout (12-factor).
# --------------------------------------------------------------------------- #
LOG_LEVEL = env_str("DJANGO_LOG_LEVEL", "INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "bastiq": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}


# --------------------------------------------------------------------------- #
# Security hardening — applied automatically in production (DEBUG=false).
# --------------------------------------------------------------------------- #
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 60 * 60 * 24 * 30)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # Honour the X-Forwarded-Proto header set by the PaaS load balancer.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    X_FRAME_OPTIONS = "DENY"
