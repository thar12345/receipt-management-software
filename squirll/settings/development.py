"""
Development settings for squirll project.
"""
import os
import sys
from .base import *  # Import all base settings
from .env_utils import EnvValidator

# Initialize development environment validator
env_validator = EnvValidator("development")

# Add Application Insights to INSTALLED_APPS if enabled
if AZURE_APPLICATION_INSIGHTS_ENABLED:
    INSTALLED_APPS = INSTALLED_APPS + [
        'opencensus.ext.django',
    ]
    
    # Add Application Insights middleware if enabled
    MIDDLEWARE = [
        'opencensus.ext.django.middleware.OpencensusMiddleware',
    ] + MIDDLEWARE

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env_validator.get_optional("SECRET_KEY", "dev-secret-key-change-in-production", "Django secret key")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    # Dev backend
    "app-squirll-services-dev-015.azurewebsites.net",
]

CSRF_TRUSTED_ORIGINS = [
    "https://app-squirll-services-dev-015.azurewebsites.net",
    "https://app-squirll-web-dev-015.azurewebsites.net",
    "http://localhost:3000",  # Local development frontend
    "http://127.0.0.1:3000",  # Local development frontend
]

# Database
DATABASES = {
    "default": env_validator.validate_database_config()
}

# CORS settings for development
CORS_ALLOW_ALL_ORIGINS = True  # Permissive for development

# Additional CORS settings for mobile app development
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^squirll:\/\/.*$",  # For mobile app deep linking
]

# Allow null origin for mobile apps (Next.js with native bridges)
CORS_ALLOW_NULL_ORIGIN = True

# Channel layers - use Redis if available, otherwise in-memory
redis_host = os.environ.get("REDIS_HOST")
redis_port = os.environ.get("REDIS_PORT", "6380")
redis_password = os.environ.get("REDIS_PASSWORD")

if redis_host and redis_password:
    # Use Redis for channels and caching when configured (secure SSL connection)
    redis_ssl_url = f"rediss://:{redis_password}@{redis_host}:{redis_port}"
    
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [f"{redis_ssl_url}/0"],
            },
        }
    }
    
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": f"{redis_ssl_url}/1",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
            }
        }
    }
else:
    # Fall back to in-memory for local development
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }
    
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }

# Email backend for development

# Use SendGrid for real email sending
EMAIL_BACKEND = "core.utils.sendgridbackend.SendGridBackend"

# Email configuration
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@squirll.com")
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")

email_config = env_validator.validate_email_config()
EMAIL_BACKEND = email_config["BACKEND"]


# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "[{levelname}] {asctime} {name} | {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "default",
        },
    },
    "root": {"handlers": ["console"], "level": os.getenv("DJANGO_LOG_LEVEL", "INFO")},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "squirll": {"handlers": ["console"], "level": "DEBUG", "propagate": True},
    },
}

# Third-party API credentials (validated in base settings)
# Azure, Twilio, and Document Intelligence configs are already validated and set in base.py

# Validate development settings
env_validator.validate_and_raise()
