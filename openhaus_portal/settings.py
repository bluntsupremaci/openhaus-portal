import os
from pathlib import Path
from django.utils.translation import gettext_lazy as _

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-change-this-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    # Django Apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party Apps
    "phonenumber_field",  # Phone number support

    # Openhaus Apps
    "accounts",
    "portal",
    "devices",
    "memberships",
    "quotas",
    "portal_sessions",
    "api",
    "openhaus_portal",

    # Future apps
    # "analytics",
    # "payments",
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
    'http://127.0.0.1',
    'http://localhost',
    'http://127.0.0.1:8000',
]

CSRF_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = False

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',   # Make sure this line exists
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
# Future: PostgreSQL
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': os.getenv('DB_NAME'),
#         ...
#     }
# }

AUTH_USER_MODEL = "accounts.CustomUser"

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
#MEDIA_URL = "/media/"          # Future
#MEDIA_ROOT = BASE_DIR / "media"  # Future

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Authentication
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/accounts/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# Phone numbers
PHONENUMBER_DEFAULT_REGION = "NG"
PHONENUMBER_DB_FORMAT = "INTERNATIONAL"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Email (Future)
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# ...

# Security (Production recommendations)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # etc.

# CORS (for future React frontend)
INSTALLED_APPS += ['corsheaders']
MIDDLEWARE.insert(1, 'corsheaders.middleware.CorsMiddleware')

CORS_ALLOW_ALL_ORIGINS = True  # For dev only. Restrict in production.

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs/openhaus.log',
        },
    },
    'loggers': {
        'django': {'handlers': ['console', 'file'], 'level': 'INFO'},
        'api': {'handlers': ['console', 'file'], 'level': 'DEBUG', 'propagate': True},
    },
}

# FAS Configuration
FAS_BASE_URL = 'http://127.0.0.1:8000'  # Update for production

# ==================== GUEST REWARD CONFIG ====================
GUEST_AD_ENABLED = True
GUEST_AD_REWARD_MB = 500                    # MB per successful ad watch
GUEST_AD_DAILY_LIMIT = 3                    # Max ads per day per MAC/IP
GUEST_AD_EXPIRY_HOURS = 24                  # How long reward lasts
GUEST_AD_REQUIRED_WATCH_SECONDS = 30        # Minimum ad watch time

