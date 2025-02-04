from django.urls import path
from core import views
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenBlacklistView,
)

urlpatterns = [
    # Auth endpoints
    path("auth/signup/", views.signup, name="signup"),
    path("auth/login/", views.login, name="login"),
    path("auth/google/", views.google_login, name="google-login"),
    path("auth/apple/", views.apple_login, name="apple-login"),

    # Email verification endpoints
    path("auth/verify-email/<uuid:token>/", views.verify_email, name="verify-email"),
    path("auth/resend-verification-email/", views.resend_verification_email_view, name="resend-verification-email"),
    path("auth/email-verification-status/", views.email_verification_status, name="email-verification-status"),

    # Password reset endpoints
    path("auth/password-reset/", views.password_reset_request, name="password-reset-request"),
    path("auth/password-reset/verify/<uuid:token>/", views.password_reset_verify, name="password-reset-verify"),
    path("auth/password-reset/confirm/<uuid:token>/", views.password_reset_confirm, name="password-reset-confirm"),

    # Token refresh endpoints
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('token/blacklist/', TokenBlacklistView.as_view(), name='token-blacklist'),

    # Onboarding endpoints
    path("user/set-squirll-id/", views.set_squirll_id, name="set-squirll-id"),
    path("user/set-phone/", views.set_phone, name="set-phone"),
    path("user/auth-set-phone/", views.auth_set_phone, name="auth-set-phone"), 

    # User profile endpoints
    path("user/profile/", views.userprofile, name="userprofile"),

    # QR Code endpoints
    path("qr-code/generate/", views.generate_user_qr_view, name="generate-qr-code"),

    # Test DB Connection Endpoint
    path("test-db-connection/", views.test_db_connection, name="test-db-connection"),
]
