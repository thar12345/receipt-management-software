"""
Environment variable validation and management utilities for squirll project.
Provides centralized, type-safe environment variable handling.
"""
import os
import logging
from typing import Optional, Dict, Any, List, Union

logger = logging.getLogger(__name__)


class EnvValidator:
    """Centralized environment variable validation and management."""
    
    def __init__(self, environment: str = "development"):
        self.environment = environment
        self.is_production = environment == "production"
        self.is_staging = environment == "staging"
        self.is_development = environment == "development"
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def get_required(self, key: str, description: str = "") -> str:
        """Get a required environment variable."""
        value = os.environ.get(key)
        if not value:
            error_msg = f"Required environment variable '{key}' is not set"
            if description:
                error_msg += f" ({description})"
            self.errors.append(error_msg)
            return ""
        return value
    
    def get_optional(self, key: str, default: str = "", description: str = "") -> str:
        """Get an optional environment variable with default."""
        value = os.environ.get(key, default)
        if not value and description:
            self.warnings.append(f"Optional environment variable '{key}' not set ({description})")
        return value
    
    def get_int(self, key: str, default: int, description: str = "") -> int:
        """Get an integer environment variable."""
        value = os.environ.get(key)
        if not value:
            return default
        
        try:
            return int(value)
        except ValueError:
            error_msg = f"Environment variable '{key}' must be an integer, got '{value}'"
            if description:
                error_msg += f" ({description})"
            self.errors.append(error_msg)
            return default
    
    def get_bool(self, key: str, default: bool, description: str = "") -> bool:
        """Get a boolean environment variable."""
        value = os.environ.get(key, "").lower()
        if not value:
            return default
        
        if value in ("true", "1", "yes", "on"):
            return True
        elif value in ("false", "0", "no", "off"):
            return False
        else:
            error_msg = f"Environment variable '{key}' must be a boolean, got '{value}'"
            if description:
                error_msg += f" ({description})"
            self.errors.append(error_msg)
            return default
    
    def get_list(self, key: str, default: List[str] = None, separator: str = ",", description: str = "") -> List[str]:
        """Get a list environment variable."""
        if default is None:
            default = []
        
        value = os.environ.get(key)
        if not value:
            return default
        
        return [item.strip() for item in value.split(separator) if item.strip()]
    
    def validate_required_for_production(self, key: str, description: str = "") -> str:
        """Validate that a variable is set in production, optional in other environments."""
        if self.is_production:
            return self.get_required(key, description)
        else:
            return self.get_optional(key, "", description)
    
    def validate_database_config(self) -> Dict[str, Any]:
        """Validate database configuration."""
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": self.get_required("PGDATABASE", "PostgreSQL database name"),
            "USER": self.get_required("PGUSER", "PostgreSQL username"),
            "PASSWORD": self.get_required("PGPASSWORD", "PostgreSQL password"),
            "HOST": self.get_required("PGHOST", "PostgreSQL host"),
            "PORT": self.get_int("PGPORT", 5432, "PostgreSQL port"),
            "OPTIONS": {"sslmode": "require"},
            "CONN_MAX_AGE": 60 if not self.is_development else 0,
        }
    
    def validate_redis_config(self) -> Dict[str, Any]:
        """Validate Redis configuration."""
        if self.is_development:
            return None  # Use in-memory for development
        
        host = self.get_required("REDIS_HOST", "Redis hostname")
        password = self.get_required("REDIS_PASSWORD", "Redis password")
        port = self.get_int("REDIS_PORT", 6380, "Redis SSL port")
        
        return {
            "host": host,
            "password": password,
            "port": port,
            "ssl": True,
        }
    
    def validate_email_config(self) -> Dict[str, Any]:
        """Validate email configuration."""
        if self.is_development:
            return {"BACKEND": "django.core.mail.backends.console.EmailBackend"}
        
        return {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "HOST": self.get_required("EMAIL_HOST", "SMTP host"),
            "PORT": self.get_int("EMAIL_PORT", 587, "SMTP port"),
            "HOST_USER": self.get_required("EMAIL_HOST_USER", "SMTP username"),
            "HOST_PASSWORD": self.get_required("EMAIL_HOST_PASSWORD", "SMTP password"),
            "USE_TLS": True,
            "DEFAULT_FROM_EMAIL": self.get_required("DEFAULT_FROM_EMAIL", "Default sender email"),
        }
    
    def validate_azure_config(self) -> Dict[str, str]:
        """Validate Azure services configuration."""
        return {
            "STORAGE_CONNECTION_STRING": self.validate_required_for_production(
                "AZURE_STORAGE_CONNECTION_STRING", "Azure Storage connection string"
            ),
            "BLOB_CONTAINER_NAME": self.get_optional(
                "AZURE_BLOB_CONTAINER_NAME", "receipts", "Azure Blob container name"
            ),
            "STORAGE_ACCOUNT_NAME": self.get_optional(
                "AZURE_STORAGE_ACCOUNT_NAME", "", "Azure Storage account name"
            ),
            "STORAGE_ACCOUNT_KEY": self.get_optional(
                "AZURE_STORAGE_ACCOUNT_KEY", "", "Azure Storage account key"
            ),
            "DOCUMENT_INTELLIGENCE_ENDPOINT": self.validate_required_for_production(
                "DOCUMENT_INTELLIGENCE_ENDPOINT", "Azure Document Intelligence endpoint"
            ),
            "DOCUMENT_INTELLIGENCE_KEY": self.validate_required_for_production(
                "DOCUMENT_INTELLIGENCE_KEY", "Azure Document Intelligence key"
            ),
        }
    
    def validate_azure_application_insights_config(self) -> Dict[str, Any]:
        """Validate Azure Application Insights configuration."""
        if self.is_development:
            # Optional in development - support both old and new variable names
            connection_string = (
                self.get_optional("AZURE_APPLICATION_INSIGHTS_CONNECTION_STRING", "", "Azure Application Insights connection string") or
                self.get_optional("APPLICATIONINSIGHTS_CONNECTION_STRING", "", "Azure Application Insights connection string (legacy)")
            )
            instrumentation_key = (
                self.get_optional("AZURE_APPLICATION_INSIGHTS_INSTRUMENTATION_KEY", "", "Azure Application Insights instrumentation key") or
                self.get_optional("APPLICATIONINSIGHTS_INSTRUMENTATION_KEY", "", "Azure Application Insights instrumentation key (legacy)")
            )
        else:
            # Required in production/staging - support both old and new variable names
            connection_string = (
                self.validate_required_for_production("AZURE_APPLICATION_INSIGHTS_CONNECTION_STRING", "Azure Application Insights connection string") or
                self.validate_required_for_production("APPLICATIONINSIGHTS_CONNECTION_STRING", "Azure Application Insights connection string (legacy)")
            )
            instrumentation_key = (
                self.validate_required_for_production("AZURE_APPLICATION_INSIGHTS_INSTRUMENTATION_KEY", "Azure Application Insights instrumentation key") or
                self.validate_required_for_production("APPLICATIONINSIGHTS_INSTRUMENTATION_KEY", "Azure Application Insights instrumentation key (legacy)")
            )
        
        return {
            "CONNECTION_STRING": connection_string,
            "INSTRUMENTATION_KEY": instrumentation_key,
            "ENABLED": bool(connection_string or instrumentation_key),
            "SAMPLING_RATE": self.get_optional(
                "AZURE_APPLICATION_INSIGHTS_SAMPLING_RATE", 
                "1.0" if self.is_development else "0.1", 
                "Application Insights sampling rate"
            ),
            "DISABLE_TELEMETRY": self.get_bool(
                "AZURE_APPLICATION_INSIGHTS_DISABLE_TELEMETRY", 
                False, 
                "Disable Application Insights telemetry"
            ),
        }
    
    def validate_twilio_config(self) -> Dict[str, str]:
        """Validate Twilio configuration."""
        return {
            "ACCOUNT_SID": self.get_optional("TWILIO_ACCOUNT_SID", "", "Twilio Account SID"),
            "AUTH_TOKEN": self.get_optional("TWILIO_ACCOUNT_AUTH_TOKEN", "", "Twilio Auth Token"),
            "PHONE_NUMBER": self.get_optional("TWILIO_PHONE_NUMBER", "", "Twilio Phone Number"),
        }
    
    def validate_celery_config(self) -> Dict[str, Any]:
        """Validate Celery configuration."""
        if self.is_development:
            # Development can use Azure Redis if configured, otherwise fall back to local Redis
            redis_host = self.get_optional("REDIS_HOST", "", "Redis hostname")
            redis_password = self.get_optional("REDIS_PASSWORD", "", "Redis password")
            redis_port = self.get_int("REDIS_PORT", 6380, "Redis port")
            
            if redis_host and redis_password:
                # Use Azure Redis configuration with SSL parameters
                broker_url = f"rediss://:{redis_password}@{redis_host}:{redis_port}/2?ssl_cert_reqs=CERT_NONE"
                result_backend = f"rediss://:{redis_password}@{redis_host}:{redis_port}/2?ssl_cert_reqs=CERT_NONE"
            else:
                # Fall back to local Redis
                broker_url = "redis://localhost:6379/2"
                result_backend = "redis://localhost:6379/2"
            
            return {
                "BROKER_URL": broker_url,
                "RESULT_BACKEND": result_backend,
                "TASK_ALWAYS_EAGER": True,  # Run tasks synchronously in development
            }
        
        # Production and staging use Redis with SSL
        redis_config = self.validate_redis_config()
        if not redis_config:
            self.errors.append("Redis configuration required for Celery in production/staging")
            return {}
        
        broker_url = f"rediss://:{redis_config['password']}@{redis_config['host']}:{redis_config['port']}/2?ssl_cert_reqs=CERT_NONE"
        
        return {
            "BROKER_URL": broker_url,
            "RESULT_BACKEND": broker_url,
            "TASK_ALWAYS_EAGER": False,  # Run tasks asynchronously
        }
    
    def validate_google_oauth_config(self) -> Dict[str, Any]:
        """Validate Google OAuth configuration."""
        client_ids_raw = self.validate_required_for_production(
            "GOOGLE_OAUTH_CLIENT_IDS", "Google OAuth client IDs (comma-separated)"
        )
        
        if not client_ids_raw:
            return {"CLIENT_IDS": "", "ALLOWED_AUDS": set()}
        
        # Parse client IDs
        allowed_auds = set()
        for client_config in client_ids_raw.split(","):
            client_config = client_config.strip()
            if not client_config:
                continue
                
            if ":" in client_config:
                # Format: "web:123456.apps.googleusercontent.com"
                platform, client_id = client_config.split(":", 1)
                allowed_auds.add(client_id.strip())
            else:
                # Format: "123456.apps.googleusercontent.com"
                allowed_auds.add(client_config)
        
        if not allowed_auds and self.is_production:
            self.errors.append("No valid Google OAuth client IDs found in GOOGLE_OAUTH_CLIENT_IDS")
        
        return {"CLIENT_IDS": client_ids_raw, "ALLOWED_AUDS": allowed_auds}
    
    def validate_and_raise(self):
        """Validate all configurations and raise errors if any are found."""
        if self.errors:
            error_msg = f"Configuration errors for {self.environment} environment:\n"
            error_msg += "\n".join(f"  - {error}" for error in self.errors)
            raise ValueError(error_msg)
        
        if self.warnings:
            logger.warning(f"Configuration warnings for {self.environment} environment:")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")


def get_environment() -> str:
    """Get the current environment from DJANGO_ENV or DJANGO_SETTINGS_MODULE."""
    # First try DJANGO_ENV
    env = os.environ.get("DJANGO_ENV", "").lower()
    if env in ("production", "staging", "development"):
        return env
    
    # Fallback to DJANGO_SETTINGS_MODULE
    settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
    if "production" in settings_module:
        return "production"
    elif "staging" in settings_module:
        return "staging"
    else:
        return "development" 