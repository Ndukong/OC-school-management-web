import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

# Hosted deployments (Railway injects DATABASE_URL for Postgres) must be
# configured explicitly and refuse to boot otherwise. Offline/SQLite laptops
# keep the zero-config flow described in DEPLOYMENT.md.
IS_HOSTED = bool(os.environ.get("DATABASE_URL"))

_debug_env = os.environ.get("DJANGO_DEBUG", "")
if _debug_env:
    DEBUG = _debug_env.lower() in ("1", "true", "yes")
else:
    DEBUG = not IS_HOSTED

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if IS_HOSTED:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set on hosted deployments."
        )
    SECRET_KEY = "django-insecure-odgb28hdxl)l7n1%i8s%b(8c9!5m@5j)*tq0sh307vqt^&k#!*"

if "ALLOWED_HOSTS" in os.environ:
    ALLOWED_HOSTS = [
        h.strip() for h in os.environ["ALLOWED_HOSTS"].split(",") if h.strip()
    ]
elif IS_HOSTED:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be set on hosted deployments.")
else:
    ALLOWED_HOSTS = ["*"]

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
    "core.middleware.LicenseGateMiddleware",
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

# Media: local disk by default (offline / single-school deployments); S3-compatible
# object storage (Cloudflare R2) on hosted deployments via USE_S3=true.
# Declared explicitly through STORAGES - Django 5.1+ ignores the legacy
# DEFAULT_FILE_STORAGE / STATICFILES_STORAGE settings.
USE_S3 = os.environ.get("USE_S3", "false").lower() == "true"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

if USE_S3:
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "")
    AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", "")
    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "auto")
    AWS_S3_ADDRESSING_STYLE = "path"
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_QUERYSTRING_AUTH = False  # stable public URLs for photos/seals in report PDFs
    AWS_S3_FILE_OVERWRITE = True
    AWS_DEFAULT_ACL = None  # R2 manages access at the bucket level
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
    AWS_S3_CUSTOM_DOMAIN = os.environ.get("AWS_S3_CUSTOM_DOMAIN", "")
    MEDIA_URL = os.environ.get(
        "MEDIA_URL",
        f"https://{AWS_S3_CUSTOM_DOMAIN or AWS_STORAGE_BUCKET_NAME}/",
    )
    MEDIA_ROOT = ""
    STORAGES["default"]["BACKEND"] = "storages.backends.s3boto3.S3Boto3Storage"
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
LICENSE_SECRET_KEY = os.environ.get("LICENSE_SECRET_KEY", "")
if not LICENSE_SECRET_KEY:
    if IS_HOSTED:
        raise ImproperlyConfigured(
            "LICENSE_SECRET_KEY must be set on hosted deployments."
        )
    LICENSE_SECRET_KEY = "oc-school-mgmt-license-secret-2024"

# Application version
APP_VERSION = "1.0.0"

# HTTPS / secure cookies (Railway terminates TLS and sets X-Forwarded-Proto)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
