"""
Django base settings for squirll project.
Contains settings that are common between all environments.
"""
import os
import sys
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
import logging

from .env_utils import EnvValidator, get_environment

# ───────────────────────────────────────────────────────────
# Paths & env
# ───────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(env_file)

# Initialize environment validator
ENVIRONMENT = get_environment()
env_validator = EnvValidator(ENVIRONMENT)

# ───────────────────────────────────────────────────────────
# Installed apps
# ───────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # third-party
    "rest_framework",
    "corsheaders",
    "channels",
    "django_filters",
    "django_celery_beat",  # Celery Beat for scheduled tasks
    # local
    "analytics",
    "core",
    "management",
    "chatbot",
    "rest_framework_simplejwt.token_blacklist",
    "receipt_mgmt",
    "email_mgmt",
]

# ───────────────────────────────────────────────────────────
# Base middleware
# ───────────────────────────────────────────────────────────
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Security settings - Base security headers
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# ───────────────────────────────────────────────────────────
# Templates / WSGI / ASGI
# ───────────────────────────────────────────────────────────
ROOT_URLCONF = "squirll.urls"
WSGI_APPLICATION = "squirll.wsgi.application"
ASGI_APPLICATION = "squirll.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

# ───────────────────────────────────────────────────────────
# Auth settings
# ───────────────────────────────────────────────────────────
AUTH_USER_MODEL = "core.UserProfile"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ───────────────────────────────────────────────────────────
# REST Framework settings
# ───────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",  # General anonymous rate limit
        "user": "1000/hour",  # General authenticated user rate limit
        "oauth": "10/min",   # Specific rate limit for OAuth endpoints
    },
}

# JWT settings - Security hardened
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),  # Reduced from 30 minutes
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),     # Reduced from 90 days
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,                # Changed to True for security
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": None,  # Will be set from SECRET_KEY
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "JWK_URL": None,
    "LEEWAY": 0,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",
    "JTI_CLAIM": "jti",
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
}

# ───────────────────────────────────────────────────────────
# Internationalization
# ───────────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ───────────────────────────────────────────────────────────
# Static files
# ───────────────────────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ───────────────────────────────────────────────────────────
# Default primary key field type
# ───────────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField" 

# ───────────────────────────────────────────────────────────
# Google OAuth & Azure Services
# ───────────────────────────────────────────────────────────
google_oauth_config = env_validator.validate_google_oauth_config()
GOOGLE_OAUTH_CLIENT_IDS = google_oauth_config["CLIENT_IDS"]
GOOGLE_OAUTH_ALLOWED_AUDS = google_oauth_config["ALLOWED_AUDS"]

# OpenAI API configuration
OPENAI_API_KEY = env_validator.get_optional("OPENAI_API_KEY", "", "OpenAI API key for GPT models")

azure_config = env_validator.validate_azure_config()
DOCUMENT_INTELLIGENCE_ENDPOINT = azure_config["DOCUMENT_INTELLIGENCE_ENDPOINT"]
DOCUMENT_INTELLIGENCE_KEY = azure_config["DOCUMENT_INTELLIGENCE_KEY"]

# Store other Azure configs for use in environment-specific settings
AZURE_STORAGE_CONNECTION_STRING = azure_config["STORAGE_CONNECTION_STRING"]
AZURE_BLOB_CONTAINER_NAME = azure_config["BLOB_CONTAINER_NAME"]
AZURE_STORAGE_ACCOUNT_NAME = azure_config["STORAGE_ACCOUNT_NAME"]
AZURE_STORAGE_ACCOUNT_KEY = azure_config["STORAGE_ACCOUNT_KEY"]

# Azure Application Insights configuration
app_insights_config = env_validator.validate_azure_application_insights_config()
AZURE_APPLICATION_INSIGHTS_CONNECTION_STRING = app_insights_config["CONNECTION_STRING"]
AZURE_APPLICATION_INSIGHTS_INSTRUMENTATION_KEY = app_insights_config["INSTRUMENTATION_KEY"]
AZURE_APPLICATION_INSIGHTS_ENABLED = app_insights_config["ENABLED"]
AZURE_APPLICATION_INSIGHTS_SAMPLING_RATE = float(app_insights_config["SAMPLING_RATE"])
AZURE_APPLICATION_INSIGHTS_DISABLE_TELEMETRY = app_insights_config["DISABLE_TELEMETRY"]

# Application Insights OpenCensus configuration
if AZURE_APPLICATION_INSIGHTS_ENABLED and not AZURE_APPLICATION_INSIGHTS_DISABLE_TELEMETRY:
    # Configure OpenCensus for Azure Application Insights
    OPENCENSUS = {
        'TRACE': {
            'SAMPLER': f'opencensus.trace.samplers.ProbabilitySampler(rate={AZURE_APPLICATION_INSIGHTS_SAMPLING_RATE})',
            'EXPORTER': f'opencensus.ext.azure.trace_exporter.AzureExporter(connection_string="{AZURE_APPLICATION_INSIGHTS_CONNECTION_STRING}")' if AZURE_APPLICATION_INSIGHTS_CONNECTION_STRING else f'opencensus.ext.azure.trace_exporter.AzureExporter(instrumentation_key="{AZURE_APPLICATION_INSIGHTS_INSTRUMENTATION_KEY}")',
        }
    }
else:
    # Disable Application Insights if not configured or explicitly disabled
    OPENCENSUS = {
        'TRACE': {
            'SAMPLER': 'opencensus.trace.samplers.ProbabilitySampler(rate=0.0)',
        }
    }

twilio_config = env_validator.validate_twilio_config()
TWILIO_ACCOUNT_SID = twilio_config["ACCOUNT_SID"]
TWILIO_ACCOUNT_AUTH_TOKEN = twilio_config["AUTH_TOKEN"]
TWILIO_PHONE_NUMBER = twilio_config["PHONE_NUMBER"]

# ───────────────────────────────────────────────────────────
# Celery Configuration
# ───────────────────────────────────────────────────────────
celery_config = env_validator.validate_celery_config()
CELERY_BROKER_URL = celery_config.get("BROKER_URL", "redis://localhost:6379/2")
CELERY_RESULT_BACKEND = celery_config.get("RESULT_BACKEND", "redis://localhost:6379/2")
CELERY_TASK_ALWAYS_EAGER = celery_config.get("TASK_ALWAYS_EAGER", False)

# Celery task configuration
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# Celery Beat (Scheduler) Configuration
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_BEAT_SCHEDULE = {
    #Add scheduled tasks here
}



# ───────────────────────────────────────────────────────────
# Apple OAuth
# ───────────────────────────────────────────────────────────
def validate_apple_oauth_settings():
    """Validate Apple OAuth settings from environment"""
    bundle_id = os.environ.get("APPLE_BUNDLE_ID", "")
    key_id = os.environ.get("APPLE_KEY_ID", "")
    team_id = os.environ.get("APPLE_TEAM_ID", "")
    private_key = os.environ.get("APPLE_PRIVATE_KEY", "")
    
    if not bundle_id:
        if os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("production"):
            raise ValueError("APPLE_BUNDLE_ID must be set in production!")
        else:
            logger.warning("APPLE_BUNDLE_ID not set - Apple OAuth will not work")
    
    if not key_id:
        if os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("production"):
            raise ValueError("APPLE_KEY_ID must be set in production!")
        else:
            logger.warning("APPLE_KEY_ID not set - Apple OAuth will not work")
    
    if not team_id:
        if os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("production"):
            raise ValueError("APPLE_TEAM_ID must be set in production!")
        else:
            logger.warning("APPLE_TEAM_ID not set - Apple OAuth will not work")
    
    if not private_key:
        if os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("production"):
            raise ValueError("APPLE_PRIVATE_KEY must be set in production!")
        else:
            logger.warning("APPLE_PRIVATE_KEY not set - Apple OAuth will not work")
    
    return bundle_id, key_id, team_id, private_key

APPLE_BUNDLE_ID, APPLE_KEY_ID, APPLE_TEAM_ID, APPLE_PRIVATE_KEY = validate_apple_oauth_settings()

# Apple OAuth client ID (bundle ID) for token verification
APPLE_OAUTH_CLIENT_ID = APPLE_BUNDLE_ID

# ───────────────────────────────────────────────────────────
# Frontend URL for password reset links
# ───────────────────────────────────────────────────────────
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000') # NEED TO CHANGE THIS WHEN FRONTEND DEVELOPER MAKES CHANGE PASSWORD SCREEN

# ───────────────────────────────────────────────────────────
# Chatbot Configuration
# ───────────────────────────────────────────────────────────
# OpenAI Configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if OPENAI_API_KEY:
    import openai
    openai.api_key = OPENAI_API_KEY

# FAISS Configuration
FAISS_CACHE_DIR = Path(os.environ.get("FAISS_CACHE_DIR", "/tmp/faiss_cache"))

# Azure Blob Storage Configuration (for FAISS indexes)
AZURE_STORAGE_CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_ACCOUNT_NAME = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")
AZURE_STORAGE_ACCOUNT_KEY = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
FAISS_CONTAINER = os.environ.get("FAISS_CONTAINER", "faiss-indexes")
FAISS_PREFIX = os.environ.get("FAISS_PREFIX", "dev/")

# ───────────────────────────────────────────────────────────
# Sentry
# ───────────────────────────────────────────────────────────
sentry_dsn = env_validator.get_optional("SENTRY_DSN", "", "Sentry DSN for error tracking")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1 if ENVIRONMENT == "production" else 0.0,
        send_default_pii=True,
        environment=ENVIRONMENT,
    )

# ───────────────────────────────────────────────────────────
# Validate configuration
# ───────────────────────────────────────────────────────────
# This will raise an error if any required settings are missing
env_validator.validate_and_raise()
