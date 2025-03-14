import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock

User = get_user_model()


@pytest.fixture()
def api_client() -> APIClient:
    """Provides an API client for testing"""
    return APIClient()


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """Clear the throttle cache before each test to avoid rate limiting issues"""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------------------
# Apple OAuth tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_apple_login_success(api_client, monkeypatch):
    """Test successful Apple OAuth login with new user creation"""
    # Mock the verification function to return valid payload
    def mock_verify(token):
        return {
            "email": "appleuser@example.com",
            "given_name": "Apple",
            "family_name": "User",
            "email_verified": True,
            "aud": "com.squirll.app",
            "iss": "https://appleid.apple.com",
            "sub": "001234.567890abcdef.1234",
            "token_type": "id_token"
        }, None
    
    monkeypatch.setattr("core.views.verify_apple_id_token", mock_verify)
    
    response = api_client.post(reverse("apple-login"), {
        "id_token": "mock_valid_apple_token"
    }, format="json")
    
    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data
    assert response.data["new_user"] is True
    
    # Verify user was created in database
    user = User.objects.get(email="appleuser@example.com")
    assert user.first_name == "Apple"
    assert user.last_name == "User"
    assert user.username == "appleuser@example.com"
    assert not user.has_usable_password()  # Should have unusable password


@pytest.mark.django_db
def test_apple_login_existing_user(api_client, monkeypatch):
    """Test Apple OAuth login with existing user"""
    # Create existing user
    existing_user = User.objects.create_user(
        email="existing@example.com",
        username="existing@example.com",
        first_name="Old",
        last_name="Name"
    )
    
    # Mock verification to return existing user's email
    def mock_verify(token):
        return {
            "email": "existing@example.com",
            "given_name": "New",
            "family_name": "UpdatedName",
            "email_verified": True,
            "aud": "com.squirll.app",
            "iss": "https://appleid.apple.com",
            "sub": "001234.567890abcdef.1234",
            "token_type": "id_token"
        }, None
    
    monkeypatch.setattr("core.views.verify_apple_id_token", mock_verify)
    
    response = api_client.post(reverse("apple-login"), {
        "id_token": "mock_valid_apple_token"
    }, format="json")
    
    assert response.status_code == 200
    assert response.data["new_user"] is False
    
    # Verify user info was updated
    existing_user.refresh_from_db()
    assert existing_user.first_name == "New"  # Should be updated
    assert existing_user.last_name == "UpdatedName"  # Should be updated


@pytest.mark.django_db
def test_apple_login_no_name_data(api_client, monkeypatch):
    """Test Apple OAuth login without name data (common after first login)"""
    def mock_verify(token):
        return {
            "email": "noname@example.com",
            "email_verified": True,
            "aud": "com.squirll.app",
            "iss": "https://appleid.apple.com",
            "sub": "001234.567890abcdef.1234",
            "token_type": "id_token"
        }, None
    
    monkeypatch.setattr("core.views.verify_apple_id_token", mock_verify)
    
    response = api_client.post(reverse("apple-login"), {
        "id_token": "mock_valid_apple_token"
    }, format="json")
    
    assert response.status_code == 200
    assert response.data["new_user"] is True
    
    # Verify user was created without name data
    user = User.objects.get(email="noname@example.com")
    assert user.first_name == ""
    assert user.last_name == ""


@pytest.mark.django_db
def test_apple_login_with_name_object(api_client, monkeypatch):
    """Test Apple OAuth login with name provided as object"""
    def mock_verify(token):
        return {
            "email": "nameobj@example.com",
            "name": {
                "firstName": "First",
                "lastName": "Last"
            },
            "email_verified": True,
            "aud": "com.squirll.app",
            "iss": "https://appleid.apple.com",
            "sub": "001234.567890abcdef.1234",
            "token_type": "id_token"
        }, None
    
    monkeypatch.setattr("core.views.verify_apple_id_token", mock_verify)
    
    response = api_client.post(reverse("apple-login"), {
        "id_token": "mock_valid_apple_token"
    }, format="json")
    
    assert response.status_code == 200
    
    # Verify user was created with name from object
    user = User.objects.get(email="nameobj@example.com")
    assert user.first_name == "First"
    assert user.last_name == "Last"


def test_apple_login_invalid_token(api_client, monkeypatch):
    """Test Apple OAuth with invalid token"""
    def mock_verify(token):
        return None, "Invalid token"
    
    monkeypatch.setattr("core.views.verify_apple_id_token", mock_verify)
    
    response = api_client.post(reverse("apple-login"), {
        "id_token": "invalid_apple_token"
    }, format="json")
    
    assert response.status_code == 401
    assert response.data["detail"] == "Invalid token"


def test_apple_login_missing_token(api_client):
    """Test Apple OAuth without providing id_token"""
    response = api_client.post(reverse("apple-login"), {}, format="json")
    
    assert response.status_code == 400
    assert "id_token is required" in response.data["detail"]


def test_apple_login_malformed_token(api_client):
    """Test Apple OAuth with malformed token data"""
    # Test with non-string token
    response = api_client.post(reverse("apple-login"), {
        "id_token": 123  # Not a string
    }, format="json")
    
    assert response.status_code == 400
    assert "Invalid token format" in response.data["detail"]


def test_apple_login_token_too_large(api_client):
    """Test Apple OAuth with overly large token"""
    large_token = "x" * 5000  # Exceeds 4096 char limit
    
    response = api_client.post(reverse("apple-login"), {
        "id_token": large_token
    }, format="json")
    
    assert response.status_code == 400
    assert "Invalid token format" in response.data["detail"]


def test_apple_login_expired_token(api_client, monkeypatch):
    """Test Apple OAuth with expired token"""
    def mock_verify(token):
        return None, "Token has expired"
    
    monkeypatch.setattr("core.views.verify_apple_id_token", mock_verify)
    
    response = api_client.post(reverse("apple-login"), {
        "id_token": "expired_apple_token"
    }, format="json")
    
    assert response.status_code == 401
    assert "expired" in response.data["detail"].lower()


def test_apple_login_wrong_audience(api_client, monkeypatch):
    """Test Apple OAuth with wrong audience"""
    def mock_verify(token):
        return None, "Invalid token audience"
    
    monkeypatch.setattr("core.views.verify_apple_id_token", mock_verify)
    
    response = api_client.post(reverse("apple-login"), {
        "id_token": "wrong_audience_token"
    }, format="json")
    
    assert response.status_code == 401
    assert "audience" in response.data["detail"].lower()


def test_apple_login_database_error(api_client, monkeypatch):
    """Test Apple OAuth when database operations fail"""
    def mock_verify(token):
        return {
            "email": "dbtest@example.com",
            "given_name": "DB",
            "family_name": "Test",
            "email_verified": True,
            "aud": "com.squirll.app",
            "iss": "https://appleid.apple.com",
            "sub": "001234.567890abcdef.1234",
            "token_type": "id_token"
        }, None
    
    # Mock User.objects.get_or_create to raise an exception
    def mock_get_or_create(*args, **kwargs):
        raise Exception("Database connection failed")
    
    monkeypatch.setattr("core.views.verify_apple_id_token", mock_verify)
    monkeypatch.setattr("core.views.User.objects.get_or_create", mock_get_or_create)
    
    response = api_client.post(reverse("apple-login"), {
        "id_token": "valid_apple_token"
    }, format="json")
    
    assert response.status_code == 500
    assert "error occurred during authentication" in response.data["detail"]


@pytest.mark.django_db 
def test_apple_login_email_case_insensitive(api_client, monkeypatch):
    """Test that email addresses are handled case-insensitively"""
    # Create user with lowercase email
    existing_user = User.objects.create_user(
        email="testuser@example.com",
        username="testuser@example.com",
        first_name="Test",
        last_name="User"
    )
    
    # Mock verification to return uppercase email
    def mock_verify(token):
        return {
            "email": "TESTUSER@EXAMPLE.COM",  # Uppercase
            "given_name": "Test",
            "family_name": "User",
            "email_verified": True,
            "aud": "com.squirll.app",
            "iss": "https://appleid.apple.com",
            "sub": "001234.567890abcdef.1234",
            "token_type": "id_token"
        }, None
    
    monkeypatch.setattr("core.views.verify_apple_id_token", mock_verify)
    
    response = api_client.post(reverse("apple-login"), {
        "id_token": "mock_valid_apple_token"
    }, format="json")
    
    assert response.status_code == 200
    assert response.data["new_user"] is False  # Should find existing user
    
    # Should still be only one user in the database
    assert User.objects.filter(email__iexact="testuser@example.com").count() == 1


@pytest.mark.django_db
def test_apple_login_subscription_type_default(api_client, monkeypatch):
    """Test that new Apple OAuth users get the default FREE subscription"""
    def mock_verify(token):
        return {
            "email": "newuser@example.com",
            "given_name": "New",
            "family_name": "User",
            "email_verified": True,
            "aud": "com.squirll.app",
            "iss": "https://appleid.apple.com",
            "sub": "001234.567890abcdef.1234",
            "token_type": "id_token"
        }, None
    
    monkeypatch.setattr("core.views.verify_apple_id_token", mock_verify)
    
    response = api_client.post(reverse("apple-login"), {
        "id_token": "mock_valid_apple_token"
    }, format="json")
    
    assert response.status_code == 200
    
    # Verify user was created with FREE subscription
    user = User.objects.get(email="newuser@example.com")
    assert user.subscription_type == User.FREE
    assert not user.is_premium


@pytest.mark.django_db
def test_apple_login_partial_name_update(api_client, monkeypatch):
    """Test that partial name updates work correctly"""
    # Create existing user with partial name
    existing_user = User.objects.create_user(
        email="partial@example.com",
        username="partial@example.com",
        first_name="",
        last_name="OldLast"
    )
    
    # Mock verification to return only first name
    def mock_verify(token):
        return {
            "email": "partial@example.com",
            "given_name": "NewFirst",
            # No family_name provided
            "email_verified": True,
            "aud": "com.squirll.app",
            "iss": "https://appleid.apple.com",
            "sub": "001234.567890abcdef.1234",
            "token_type": "id_token"
        }, None
    
    monkeypatch.setattr("core.views.verify_apple_id_token", mock_verify)
    
    response = api_client.post(reverse("apple-login"), {
        "id_token": "mock_valid_apple_token"
    }, format="json")
    
    assert response.status_code == 200
    
    # Verify only first name was updated
    existing_user.refresh_from_db()
    assert existing_user.first_name == "NewFirst"
    assert existing_user.last_name == "OldLast"  # Should remain unchanged


def test_apple_login_rate_limiting_concept(api_client, monkeypatch):
    """Test that rate limiting configuration exists (conceptual test)"""
    # This is a simplified test that just verifies the throttle class exists
    # and is properly configured for Apple OAuth, without actually triggering rate limits
    from core.views import OAuthRateThrottle
    from django.conf import settings
    
    # Verify the throttle class exists
    assert OAuthRateThrottle is not None
    assert OAuthRateThrottle.scope == 'oauth'
    
    # Verify the rate is configured in settings
    assert 'oauth' in settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']
    assert settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['oauth'] == '10/min'


# ---------------------------------------------------------------------------
# Apple OAuth utility tests
# ---------------------------------------------------------------------------

@patch('core.utils.apple_utils.requests.get')
def test_apple_public_keys_caching(mock_get):
    """Test that Apple public keys are cached properly"""
    from core.utils.apple_utils import _get_apple_public_keys, _apple_keys_cache
    
    # Clear cache
    _apple_keys_cache.clear()
    
    # Mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {"keys": [{"kid": "test", "n": "test", "e": "AQAB"}]}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    # First call should fetch from API
    keys1 = _get_apple_public_keys()
    assert mock_get.call_count == 1
    
    # Second call should use cache
    keys2 = _get_apple_public_keys()
    assert mock_get.call_count == 1  # Should not increase
    assert keys1 == keys2


@patch('core.utils.apple_utils.requests.get')
def test_apple_public_keys_request_failure(mock_get):
    """Test handling of Apple public keys request failure"""
    from core.utils.apple_utils import _get_apple_public_keys, _apple_keys_cache
    
    # Clear cache to ensure we don't get stale data
    _apple_keys_cache.clear()
    
    # Mock request failure
    mock_get.side_effect = Exception("Network error")
    
    result = _get_apple_public_keys()
    assert result is None


def test_apple_token_verification_missing_kid(monkeypatch):
    """Test Apple token verification with missing key ID"""
    from core.utils.apple_utils import verify_apple_id_token
    
    # Mock jwt.get_unverified_header to return header without kid
    def mock_get_header(token):
        return {"alg": "RS256", "typ": "JWT"}
    
    monkeypatch.setattr("core.utils.apple_utils.jwt.get_unverified_header", mock_get_header)
    
    payload, error = verify_apple_id_token("test_token")
    assert payload is None
    assert "Invalid token format" in error 