from typing import Tuple, Optional
from google.oauth2 import id_token
from google.auth.transport import requests
from django.conf import settings
import logging
from google.auth.exceptions import GoogleAuthError

GOOGLE_REQUEST = requests.Request()
logger = logging.getLogger(__name__)


def verify_google_id_token(token: str) -> Tuple[Optional[dict], Optional[str]]:
    """
    Return (payload, error).  If verification fails, payload is None and
    error is a user-friendly message.
    """
    try:
        payload = id_token.verify_oauth2_token(token, GOOGLE_REQUEST)
    except ValueError as e:
        logger.warning(f"Invalid Google ID token format: {str(e)}")
        return None, "Invalid ID token"
    except GoogleAuthError as e:
        logger.warning(f"Google auth error: {str(e)}")
        return None, "Google authentication failed"
    except Exception as e:
        logger.error(f"Unexpected error verifying Google token: {str(e)}")
        return None, "Authentication service temporarily unavailable"

    # Audience check
    if payload["aud"] not in settings.GOOGLE_OAUTH_ALLOWED_AUDS:
        return None, "Unrecognised Google client"

    # Issuer check
    if payload["iss"] not in ("https://accounts.google.com",
                              "accounts.google.com"):
        return None, "Wrong issuer"

    # Email verified?
    if not payload.get("email_verified", False):
        return None, "Google account email is not verified" 

    return payload, None
