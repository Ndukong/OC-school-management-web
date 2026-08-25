from pathlib import Path

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-odgb28hdxl)l7n1%i8s%b(8c9!5m@5j)*tq0sh307vqt^&k#!*",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("ALLOWED_HOSTS", "*").split(",") if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "crispy_forms",
    "crispy_bootstrap5",
    "auditlog",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.AdminSuperuserOnlyMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.school_context",
                "core.context_processors.parent_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database: use DATABASE_URL (Railway Postgres plugin injects this) when present,
# otherwise fall back to SQLite for local development.
if db_url := os.environ.get("DATABASE_URL"):
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(db_url)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "OPTIONS": {
                "init_command": "PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;",
            },
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 6},
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Douala"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Media: default to local filesystem; switch to S3-compatible object storage
# (Cloudflare R2 / Supabase) on the hosted deployment by setting USE_S3=true.
USE_S3 = os.environ.get("USE_S3", "false").lower() == "true"
if USE_S3:
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "")
    AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", "")
    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "auto")
    AWS_DEFAULT_ACL = "public-read"
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_CUSTOM_DOMAIN = os.environ.get("AWS_S3_CUSTOM_DOMAIN", "")
    MEDIA_URL = os.environ.get(
        "MEDIA_URL",
        f"https://{AWS_S3_CUSTOM_DOMAIN or AWS_STORAGE_BUCKET_NAME}/",
    )
    MEDIA_ROOT = ""
else:
    MEDIA_URL = "media/"
    MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CRISPY_TEMPLATE_PACK = "bootstrap5"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

# Authentication
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# Session timeout (30 minutes)
SESSION_COOKIE_AGE = 1800
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Licensing
LICENSE_SECRET_KEY = os.environ.get(
    "LICENSE_SECRET_KEY", "oc-school-mgmt-license-secret-2024"
)

# Application version
APP_VERSION = "1.0.0"

# HTTPS / secure cookies (Railway terminates TLS and sets X-Forwarded-Proto)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
