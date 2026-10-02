import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# 1) Load .env FIRST so os.getenv sees DJANGO_* vars
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# Ensure log directory exists before FileHandler opens
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 2) DEBUG from env (default True for local lab only)
DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"

# 3) SECRET_KEY — never commit a real key in this file
_secret = (os.getenv("DJANGO_SECRET_KEY") or "").strip()
if _secret:
    SECRET_KEY = _secret
elif DEBUG:
    SECRET_KEY = "django-insecure-dev-only-not-for-production"
else:
    raise RuntimeError(
        "DJANGO_SECRET_KEY must be set when DJANGO_DEBUG=False. "
        "Put it in .env or export it in the shell."
    )

# Paystack Setup
PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY", "")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")

# Plan price is in NGN major units (e.g. 2000.00). Paystack wants kobo.
def paystack_amount_kobo(amount_naira) -> int:
    return int(round(float(amount_naira) * 100))

# ---------------------------------------------------------------------------
# Hosts / CSRF
# Lab: 127.0.0.1 + localhost is enough for pure local work.
# Portal/openNDS lab: add your Mac LAN IP in .env.
# AWS later: set domain only in env (no * in production).
# ---------------------------------------------------------------------------
_default_hosts = "127.0.0.1,localhost"
_allowed = os.getenv("DJANGO_ALLOWED_HOSTS", _default_hosts if DEBUG else "")
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(",") if h.strip()]
if not DEBUG and not ALLOWED_HOSTS:
    raise RuntimeError(
        "DJANGO_ALLOWED_HOSTS must be set when DJANGO_DEBUG=False "
        "(comma-separated, e.g. portal.example.com,192.168.1.10)."
    )

_default_csrf = "http://127.0.0.1:8000,http://localhost:8000"
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", _default_csrf).split(",")
    if origin.strip()
]

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
    "access_policy",
    "payments",
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

CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True

# ---------------------------------------------------------------------------
# TLS — independent of DEBUG (Fix #3)
# Lab HTTP + openNDS:  DJANGO_USE_TLS=False
# AWS + real HTTPS:    DJANGO_USE_TLS=True
# ---------------------------------------------------------------------------
USE_TLS = os.getenv("DJANGO_USE_TLS", "False") == "True"

if USE_TLS:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

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

_db_engine = os.getenv("DJANGO_DB_ENGINE", "django.db.backends.sqlite3")

if _db_engine == "django.db.backends.postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DJANGO_DB_NAME", "openhaus_portal"),
            "USER": os.getenv("DJANGO_DB_USER", "openhaus"),
            "PASSWORD": os.getenv("DJANGO_DB_PASSWORD", ""),
            "HOST": os.getenv("DJANGO_DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DJANGO_DB_PORT", "5432"),
        }
    }
else:
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

# Lab default key OK for local; production should set OPENNDS_FAS_KEY in env (Fix #4 next)
OPENNDS_FAS_KEY = os.getenv(
    "OPENNDS_FAS_KEY",
    "f901698444084cb1ed54d306c9d61528848357f95461ce3099454b4b06496cdb" if DEBUG else "",
)
if not DEBUG and not OPENNDS_FAS_KEY:
    raise RuntimeError("OPENNDS_FAS_KEY must be set when DJANGO_DEBUG=False.")

# Explicit only. Do NOT tie to DEBUG — that grants verify bonus on every signup.
AUTH_AUTO_VERIFY_EMAIL = os.getenv("AUTH_AUTO_VERIFY_EMAIL", "False") == "True"

# Email (dev: print to console; prod: set SMTP via env)
if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = os.getenv(
        "EMAIL_BACKEND",
        "django.core.mail.backends.smtp.EmailBackend",
    )
    EMAIL_HOST = os.getenv("EMAIL_HOST", "")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL", "OpenHaus <noreply@openhaus.local>"
)
