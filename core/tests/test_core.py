"""Minimal but complete pytest suite for *core* app endpoints.
Covers happy‑paths, auth checks, DB persistence, and key error cases for every URL.
Run with: pytest -q
"""
import pytest
pytestmark = pytest.mark.django_db  # allow DB in the whole module
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
import json


User = get_user_model()

# ---------------------------------------------------------------------------
# Fixtures & global monkey‑patches
# ---------------------------------------------------------------------------

@pytest.fixture()
def api_client():
    """
    Fresh DRF APIClient for each test (no auth headers attached).
    """
    return APIClient()


@pytest.fixture()
def user_payload():
    """
    Canonical signup payload reused across tests.
    """
    return {
        "email": "alice@example.com",
        "password": "StrongPassw0rd!",
        "first_name": "Alice",
        "last_name": "Doe",
    }


@pytest.fixture()
def signup(api_client, user_payload):
    """
    Helper that signs the user up once, asserts success,
    and returns (JWT-tokens-dict, User-instance).
    """
    res = api_client.post(reverse("signup"), user_payload, format="json")
    assert res.status_code == 201
    return res.data, User.objects.get(email=user_payload["email"].lower())


@pytest.fixture()
def auth_client(api_client, signup):
    """
    Same as api_client but pre-authorised with the access-token produced
    by the `signup` fixture.  Used for endpoints that require authentication.
    """
    tokens, _ = signup
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")
    return api_client


# disable external SMS
@pytest.fixture(autouse=True)
def _patch_twilio(monkeypatch):
    """
    Any call that would normally send an SMS OTP is replaced with a
    lambda returning a hard-coded code (`"1234"`).  Works globally because
    of autouse=True.
    """
    monkeypatch.setattr(
        "core.services.phone_auth.send_phone_verification_otp", lambda *a, **kw: "1234",
    )

# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

def test_signup_and_login(api_client, user_payload):
    """
    * verifies signup returns 201 and both tokens
    * verifies login works with the correct password
    * verifies two distinct error paths:
        – 400 when the password is too short (fails validation)
        – 401 when the password is the right length but incorrect
    """
    # signup
    signup = api_client.post(reverse("signup"), user_payload, format="json")
    assert signup.status_code == 201 and {"access_token", "refresh_token"}.issubset(signup.data)

    # login succeeds
    login = api_client.post(reverse("login"), {
        "email": user_payload["email"],
        "password": user_payload["password"],
    }, format="json")
    assert login.status_code == 200 and {"access", "refresh"}.issubset(login.data)
    
    # wrong password (password too short)
    bad = api_client.post(reverse("login"), {"email": user_payload["email"], "password": "wrong"}, format="json")
    assert bad.status_code == 400
    
    # wrong password (correct length but wrong password)
    bad2 = api_client.post(reverse("login"), {"email": user_payload["email"], "password": "wrongpassword"}, format="json")
    assert bad2.status_code == 401


def test_token_refresh_and_blacklist(api_client, signup):
    """
    * refreshes an access-token successfully (200).
    * blacklists the refresh token.
    * attempts to refresh again → should now yield 401.
    """
    tokens, _ = signup
    fresh = api_client.post(reverse("token-refresh"), {"refresh": tokens["refresh_token"]}, format="json")
    assert fresh.status_code == 200 and "access" in fresh.data

    # blacklist & retry
    api_client.post(reverse("token-blacklist"), {"refresh": tokens["refresh_token"]}, format="json")
    reuse = api_client.post(reverse("token-refresh"), {"refresh": tokens["refresh_token"]}, format="json")
    assert reuse.status_code == 401

# ---------------------------------------------------------------------------
# Permission guardrail (unauthenticated access)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("url_name,method", [
    ("set-phone", "post"),
    ("auth-set-phone", "patch"),
    ("set-squirll-id", "patch"),
    ("userprofile", "get"),
    ("generate-qr-code", "get"),
])
def test_requires_auth(api_client, url_name, method):
    """
    Every protected endpoint should return 401 when no JWT is supplied.
    Uses parametrisation to hit five URLs in one test function.
    """
    fn = getattr(api_client, method)
    res = fn(reverse(url_name)) if method == "get" else fn(reverse(url_name), {})
    assert res.status_code == 401

# ---------------------------------------------------------------------------
# Phone number flow
# ---------------------------------------------------------------------------

def test_set_phone_and_verify(monkeypatch, auth_client):
    """
    Full happy-path:
      1) user POSTs phone → 200, OTP "sent"
      2) user PATCHes OTP → 200, phone stored in DB
    """
    # send OTP
    send = auth_client.post(
        reverse("set-phone"),
        {"phone_number": "+14165550111"},
        format="json",
    )
    assert send.status_code == 200

    # monkey-patch the *verify* helper so it succeeds & writes to DB
    def _fake_verify_and_set_phone(user, code):
        user.phone_number = "14165550111"
        user.save(update_fields=["phone_number"])
        return "14165550111"

    monkeypatch.setattr("core.views.verify_and_set_phone", _fake_verify_and_set_phone)
    
    #verify OTP
    verify = auth_client.patch(
        reverse("auth-set-phone"),
        {"otp_code": "1234"},
        format="json",
    )
    assert verify.status_code == 200
    assert User.objects.get(email="alice@example.com").phone_number == "14165550111"


# ---------------------------------------------------------------------------
# Squirll‑ID
# ---------------------------------------------------------------------------

def test_squirll_id_first_and_second(auth_client):
    """
    1st PATCH with a new ID → 200 & persisted.
    2nd PATCH (attempt to change) → 400.
    """
    first = auth_client.patch(reverse("set-squirll-id"), {"squirll_id": "alice@squirll.com"}, format="json")
    assert first.status_code == 200 and User.objects.get(email="alice@example.com").squirll_id == "alice@squirll.com"

    second = auth_client.patch(reverse("set-squirll-id"), {"squirll_id": "bob@squirll.com"}, format="json")
    assert second.status_code == 400

# ---------------------------------------------------------------------------
# Profile & QR code
# ---------------------------------------------------------------------------

def test_profile_and_qr(auth_client):
    """
    * GET /userprofile returns user data (200)
    * GET /generate-qr-code returns a PNG payload (200)
    """
    prof = auth_client.get(reverse("userprofile"))
    assert prof.status_code == 200 and prof.data["user"]["email"] == "alice@example.com"

    qr = auth_client.get(reverse("generate-qr-code"))
    assert qr.status_code == 200 and qr["Content-Type"] == "image/png" and qr.content.startswith(b"\x89PNG")

# ---------------------------------------------------------------------------
# DB health endpoint
# ---------------------------------------------------------------------------

def test_db_connection_success(api_client):
    """
    Healthy DB connection should reply with {"status": "success"}.
    """
    res = api_client.get(reverse("test-db-connection"))
    payload = json.loads(res.content)
    assert res.status_code == 200 and payload["status"] == "success"


def test_db_connection_failure(monkeypatch, api_client):
    """
    Simulate DB cursor failure -> endpoint should still return 200
    but JSON payload {"status": "error"} (so readiness probes don't crash).
    """
    from django.db import connection

    # make connection.cursor() raise
    monkeypatch.setattr(
        connection,
        "cursor",
        lambda *a, **kw: (_ for _ in ()).throw(Exception("boom")),
    )

    res = api_client.get(reverse("test-db-connection"))
    payload = json.loads(res.content)

    assert res.status_code == 200 and payload["status"] == "error"

# ---------------------------------------------------------------------------
# Password Reset Flow
# ---------------------------------------------------------------------------

def test_password_reset_full_flow(api_client):
    """
    Full happy-path password reset flow for an existing user:
    1) Create the user in the test database
    2) User requests password reset
    3) System generates token and sends email via SendGrid
    4) User verifies token is valid
    5) User confirms password reset with new password
    6) User can login with new password
    """
    # This test uses a real user and expects to send a real email.
    user_email = "thardapower@gmail.com"
    
    # First create the user in the test database
    user = User.objects.create_user(
        username=user_email,  # Required by AbstractUser
        email=user_email,
        password="OriginalPassword123!",
        first_name="Tharsi",
        last_name="Hanariyanayagam"
    )

    # 1. Request password reset
    reset_request = api_client.post(
        reverse("password-reset-request"),
        {"email": user_email},
        format="json"
    )
    assert reset_request.status_code == 200
    assert "success" in reset_request.data["status"]

    # Get the token from the database
    user = User.objects.get(email=user_email.lower())
    reset_token = user.password_resets.filter(is_used=False).first()
    assert reset_token is not None

    # 2. Verify token is valid
    verify_res = api_client.get(
        reverse("password-reset-verify", kwargs={"token": reset_token.token})
    )
    assert verify_res.status_code == 200
    assert verify_res.data["email"] == user_email

    # 3. Confirm password reset
    new_password = "NewStrongPass123!"
    confirm_res = api_client.post(
        reverse("password-reset-confirm", kwargs={"token": reset_token.token}),
        {
            "new_password": new_password,
            "confirm_password": new_password
        },
        format="json"
    )
    assert confirm_res.status_code == 200
    assert "success" in confirm_res.data["status"]

    # 4. Verify new password works
    new_login = api_client.post(
        reverse("login"),
        {"email": user_email, "password": new_password},
        format="json"
    )
    assert new_login.status_code == 200
    assert "access" in new_login.data


def test_password_reset_nonexistent_email(api_client, monkeypatch):
    """
    Requesting password reset for non-existent email should still return success
    (to prevent email enumeration attacks).
    """
    sent_emails = []
    def mock_send_mail(*args, **kwargs):
        sent_emails.append(kwargs)
        return True
    monkeypatch.setattr("core.services.password_reset.send_mail", mock_send_mail)
    
    reset_request = api_client.post(
        reverse("password-reset-request"),
        {"email": "nonexistent@example.com"},
        format="json"
    )
    assert reset_request.status_code == 200
    assert "success" in reset_request.data["status"]
    assert len(sent_emails) == 0  # No email actually sent


def test_password_reset_invalid_token(api_client):
    """
    Test various invalid token scenarios.
    """
    import uuid
    fake_token = str(uuid.uuid4())
    
    # Verify invalid token
    verify_res = api_client.get(
        reverse("password-reset-verify", kwargs={"token": fake_token})
    )
    assert verify_res.status_code == 400
    
    # Confirm with invalid token
    confirm_res = api_client.post(
        reverse("password-reset-confirm", kwargs={"token": fake_token}),
        {
            "new_password": "NewPass123!",
            "confirm_password": "NewPass123!"
        },
        format="json"
    )
    assert confirm_res.status_code == 400


def test_password_reset_token_expiry(api_client, user_payload, monkeypatch):
    """
    Test that expired tokens are properly rejected.
    """
    from django.utils import timezone
    from datetime import timedelta
    
    # Mock email sending
    monkeypatch.setattr("core.services.password_reset.send_mail", lambda *a, **kw: True)
    
    # Signup user
    api_client.post(reverse("signup"), user_payload, format="json")
    user = User.objects.get(email=user_payload["email"].lower())
    
    # Request password reset
    api_client.post(
        reverse("password-reset-request"),
        {"email": user_payload["email"]},
        format="json"
    )
    
    # Get token and manually expire it
    reset_token = user.password_resets.filter(is_used=False).first()
    reset_token.expires_at = timezone.now() - timedelta(hours=1)
    reset_token.save()
    
    # Verify token is expired
    verify_res = api_client.get(
        reverse("password-reset-verify", kwargs={"token": reset_token.token})
    )
    assert verify_res.status_code == 400
    assert "expired" in verify_res.data["message"].lower()


def test_password_reset_token_reuse(api_client, user_payload, monkeypatch):
    """
    Test that tokens can only be used once.
    """
    # Mock email sending
    monkeypatch.setattr("core.services.password_reset.send_mail", lambda *a, **kw: True)
    
    # Signup user
    api_client.post(reverse("signup"), user_payload, format="json")
    user = User.objects.get(email=user_payload["email"].lower())
    
    # Request password reset
    api_client.post(
        reverse("password-reset-request"),
        {"email": user_payload["email"]},
        format="json"
    )
    
    # Get token
    reset_token = user.password_resets.filter(is_used=False).first()
    
    # Use token once
    api_client.post(
        reverse("password-reset-confirm", kwargs={"token": reset_token.token}),
        {
            "new_password": "NewPass123!",
            "confirm_password": "NewPass123!"
        },
        format="json"
    )
    
    # Try to use it again
    reuse_res = api_client.post(
        reverse("password-reset-confirm", kwargs={"token": reset_token.token}),
        {
            "new_password": "AnotherPass123!",
            "confirm_password": "AnotherPass123!"
        },
        format="json"
    )
    assert reuse_res.status_code == 400
    assert "already been used" in reuse_res.data["message"]


def test_password_reset_validation_errors(api_client, user_payload, monkeypatch):
    """
    Test password validation during reset.
    """
    # Mock email sending
    monkeypatch.setattr("core.services.password_reset.send_mail", lambda *a, **kw: True)
    
    # Signup user and get token
    api_client.post(reverse("signup"), user_payload, format="json")
    user = User.objects.get(email=user_payload["email"].lower())
    api_client.post(
        reverse("password-reset-request"),
        {"email": user_payload["email"]},
        format="json"
    )
    reset_token = user.password_resets.filter(is_used=False).first()
    
    # Test password too short
    short_pass = api_client.post(
        reverse("password-reset-confirm", kwargs={"token": reset_token.token}),
        {
            "new_password": "short",
            "confirm_password": "short"
        },
        format="json"
    )
    assert short_pass.status_code == 400
    
    # Test password mismatch
    mismatch = api_client.post(
        reverse("password-reset-confirm", kwargs={"token": reset_token.token}),
        {
            "new_password": "ValidPass123!",
            "confirm_password": "DifferentPass123!"
        },
        format="json"
    )
    assert mismatch.status_code == 400
