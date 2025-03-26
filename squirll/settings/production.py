"""
Production settings for squirll project.
"""
import os
from .base import *  # Import all base settings
from .env_utils import EnvValidator

# Initialize production environment validator
env_validator = EnvValidator("production")

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
SECRET_KEY = env_validator.get_required("SECRET_KEY", "Django secret key")

DEBUG = False

ALLOWED_HOSTS = [
    # Production placeholders
    "api.squirll.com",  # Production backend placeholder
    "app.squirll.com",  # Production frontend placeholder
    # Add your actual production domains here when ready
]

# Security settings
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Additional security headers
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

CSRF_TRUSTED_ORIGINS = [
    # Production placeholders
    "https://api.squirll.com",  # Production backend placeholder
    "https://app.squirll.com",  # Production frontend placeholder
    # Add your actual production domains here when ready
]

# Database with connection pooling
DATABASES = {
    "default": env_validator.validate_database_config()
}

# CORS settings for production
CORS_ALLOW_ALL_ORIGINS = False  # Keep this False for security
CORS_ALLOWED_ORIGINS = [
    # Production placeholders
    "https://app.squirll.com",  # Production frontend placeholder
    # Add your actual production domains here when ready
]

# Allow mobile apps (Next.js with native bridges) using regex and null origin
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^squirll:\/\/.*$",  # For deep linking in your mobile apps
]

# Allow null origin for mobile apps (Next.js with native bridges)
CORS_ALLOW_NULL_ORIGIN = True

# Allow mobile app authentication
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# Allow credentials (for authentication)
CORS_ALLOW_CREDENTIALS = True

# Redis configuration (secure SSL connection)
redis_config = env_validator.validate_redis_config()
if redis_config:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [
                    f"rediss://:{redis_config['password']}@{redis_config['host']}:{redis_config['port']}/0"
                ],
            },
        }
    }

    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": f"rediss://:{redis_config['password']}@{redis_config['host']}:{redis_config['port']}/1",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
            }
        }
    }

# Email configuration
email_config = env_validator.validate_email_config()
EMAIL_BACKEND = email_config["BACKEND"]
EMAIL_HOST = email_config["HOST"]
EMAIL_PORT = email_config["PORT"]
EMAIL_HOST_USER = email_config["HOST_USER"]
EMAIL_HOST_PASSWORD = email_config["HOST_PASSWORD"]
EMAIL_USE_TLS = email_config["USE_TLS"]
DEFAULT_FROM_EMAIL = email_config["DEFAULT_FROM_EMAIL"]

# Logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": (
                "{levelname} {asctime} {module} {process:d} "
                "{thread:d} {message}"
            ),
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}

# Third-party API credentials (validated in base settings)
# Azure, Twilio, and Document Intelligence configs are already validated and set in base.py

# Rate limiting - Production specific (more restrictive)
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # Inherit from base settings
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/day",      # Restrictive for anonymous users
        "user": "1000/day",     # Reasonable for authenticated users
        "oauth": "10/min",      # OAuth endpoints (inherited from base)
    },
}

# Validate all production settings
env_validator.validate_and_raise()
