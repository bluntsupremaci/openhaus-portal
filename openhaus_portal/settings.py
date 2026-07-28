import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Ensure log directory exists before FileHandler opens
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-change-this-in-production")
DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"

# Prefer explicit hosts via env in non-debug
_allowed = os.getenv("DJANGO_ALLOWED_HOSTS", "*")
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "phonenumber_field",
    "accounts",
    "portal",
    "devices",
    "memberships",
    "quotas",
    "portal_sessions",
    "api",
    "openhaus_portal",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "openhaus_portal.urls"
WSGI_APPLICATION = "openhaus_portal.wsgi.application"

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "http://127.0.0.1,http://localhost,http://127.0.0.1:8000",
    ).split(",")
    if origin.strip()
]

CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True

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
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_USER_MODEL = "accounts.CustomUser"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/accounts/dashboard/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

PHONENUMBER_DEFAULT_REGION = "NG"
PHONENUMBER_DB_FORMAT = "INTERNATIONAL"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Optional CORS (only if package installed)
try:
    import corsheaders  # noqa: F401

    INSTALLED_APPS += ["corsheaders"]
    MIDDLEWARE.insert(1, "corsheaders.middleware.CorsMiddleware")
    CORS_ALLOW_ALL_ORIGINS = DEBUG
except ImportError:
    pass

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "openhaus.log"),
            "formatter": "standard",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
        },
        "api": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "openhaus": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# FAS / captive portal
FAS_BASE_URL = os.getenv("FAS_BASE_URL", "http://127.0.0.1:8000")
FAS_PORTAL_LOGIN_URL = "/accounts/login/"
FAS_GUEST_URL = "/accounts/guest/"

# Dev-only: auto-verify email on signup when True
AUTH_AUTO_VERIFY_EMAIL = os.getenv("AUTH_AUTO_VERIFY_EMAIL", "False") == "True" or DEBUG

# Guest defaults (GuestConfig model remains source of truth when present)
GUEST_AD_ENABLED = True
GUEST_AD_REWARD_MB = 500
GUEST_AD_DAILY_LIMIT = 3
GUEST_AD_EXPIRY_HOURS = 24
GUEST_AD_REQUIRED_WATCH_SECONDS = 30