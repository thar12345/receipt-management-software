from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework import status
from core.serializers import UserSignupSerializer, LoginSerializer, SetPhoneSerializer, SquirllIDSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from rest_framework.permissions import IsAuthenticated
from core.services.phone_auth import send_phone_verification_otp, verify_and_set_phone, OTPGenerationError, InvalidOTPError, OTPExpiredError, PhoneAuthError
from core.services.email_verification import (
    send_verification_email, 
    verify_email_token, 
    resend_verification_email,
    EmailVerificationError,
    TokenExpiredError,
    TokenNotFoundError,
    TokenAlreadyUsedError
)
from core.services.password_reset import (
    send_password_reset_email,
    verify_password_reset_token,
    reset_user_password,
    PasswordResetError,
    TokenExpiredError as PasswordResetTokenExpiredError,
    TokenNotFoundError as PasswordResetTokenNotFoundError,
    TokenAlreadyUsedError as PasswordResetTokenAlreadyUsedError,
    UserNotFoundError
)
from rest_framework import serializers
import io
from django.http import HttpResponse
import qrcode
from django.db import connection
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.utils.google_utils import verify_google_id_token
from core.utils.apple_utils import verify_apple_id_token
from rest_framework.throttling import AnonRateThrottle

import logging
logger = logging.getLogger(__name__)

User = get_user_model()
# Create your views here.
@api_view(["POST"])
def signup(request):
    signupserializer = UserSignupSerializer(data=request.data)
    if not signupserializer.is_valid():
        return Response(signupserializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    user = signupserializer.save()
    
    # Send verification email
    email_sent = send_verification_email(user, request)
    if not email_sent:
        logger.warning(f"Failed to send verification email to {user.email}")
    
    # Generate JWT tokens for the new user (even if email is not verified)
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    response_data = {
        "status": "success",
        "message": "Account created successfully. Please check your email to verify your account.",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "email_verification_sent": email_sent,
        "requires_email_verification": True,
    }
    
    return Response(response_data, status=status.HTTP_201_CREATED)


def verify_email(request, token):
    """
    Verify email using the token sent in verification email.
    GET /core/auth/verify-email/<token>/
    """
    try:
        user = verify_email_token(token)
        logger.info(f"Email verified successfully for user {user.email}")
        
        # Render success page
        return render(request, 'core/emails/email_verification_success.html', {
            'user': user,
        })
        
    except TokenNotFoundError:
        logger.warning(f"Invalid verification token attempted: {token}")
        return render(request, 'core/emails/email_verification_error.html', {
            'error_message': 'Invalid verification link. Please check your email for the correct link or request a new one.',
            'error_type': 'invalid',
        }, status=400)
        
    except TokenExpiredError:
        logger.warning(f"Expired verification token attempted: {token}")
        return render(request, 'core/emails/email_verification_error.html', {
            'error_message': 'This verification link has expired. Please request a new verification email.',
            'error_type': 'expired',
        }, status=400)
        
    except TokenAlreadyUsedError:
        logger.warning(f"Already used verification token attempted: {token}")
        return render(request, 'core/emails/email_verification_error.html', {
            'error_message': 'This verification link has already been used. Your email may already be verified.',
            'error_type': 'used',
        }, status=400)
        
    except Exception as e:
        logger.error(f"Unexpected error during email verification: {str(e)}")
        return render(request, 'core/emails/email_verification_error.html', {
            'error_message': 'An unexpected error occurred while verifying your email. Please try again.',
            'error_type': 'general',
        }, status=500)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resend_verification_email_view(request):
    """
    Resend verification email to the authenticated user.
    POST /api/auth/resend-verification-email/
    """
    user = request.user
    
    try:
        email_sent = resend_verification_email(user, request)
        
        if email_sent:
            return Response({
                "status": "success",
                "message": "Verification email sent successfully. Please check your inbox.",
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                "status": "error",
                "message": "Failed to send verification email. Please try again later.",
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except EmailVerificationError as e:
        return Response({
            "status": "error",
            "message": str(e),
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Unexpected error during email resend: {str(e)}")
        return Response({
            "status": "error",
            "message": "An error occurred while sending the verification email. Please try again.",
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def email_verification_status(request):
    """
    Get the current email verification status for the authenticated user.
    GET /api/auth/email-verification-status/
    """
    user = request.user
    
    return Response({
        "is_email_verified": user.is_email_verified,
        "email": user.email,
        "email_verified_at": user.email_verified_at,
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
def login(request):
    """
    POST /api/auth/login/
    Body: {"email": "...", "password": "..."}
    Returns: {"access": "...", "refresh": "..."}
    """
    ser = LoginSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    email = ser.validated_data["email"].lower()
    password = ser.validated_data["password"]

    # Because we saved username=email during sign-up, we can authenticate via username.
    user = authenticate(request, username=email, password=password)
    if user is None:
        return Response(
            {"detail": "Invalid email or password."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    refresh = RefreshToken.for_user(user)
    return Response(
        {"access": str(refresh.access_token), "refresh": str(refresh)},
        status=status.HTTP_200_OK
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_phone(request):
    serializer = SetPhoneSerializer(data=request.data, context={"request": request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    phone_number = serializer.validated_data["phone_number"]
    user = request.user

    try:
        send_phone_verification_otp(user, phone_number)
        return Response(
            {"status": "success", "message": "OTP sent successfully."},
            status=status.HTTP_200_OK,
        )
    except OTPGenerationError as e:
        # Log the error e if you have logging configured
        return Response(
            {"status": "error", "message": str(e)}, # Or a more generic server error message
            status=status.HTTP_500_INTERNAL_SERVER_ERROR, # Or BAD_REQUEST if client can fix
        )
    except Exception as e: # Catch any other unexpected errors
        # Log the error e
        return Response(
            {"status": "error", "message": "An unexpected error occurred while sending OTP."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def auth_set_phone(request):
    otp_code = request.data.get("otp_code")
    if not otp_code:
        return Response(
            {"otp_code": ["This field is required."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = request.user

    try:
        verify_and_set_phone(user, otp_code)
        return Response(
            {"status": "success", "message": "Phone number verified and added."},
            status=status.HTTP_200_OK,
        )
    except InvalidOTPError as e:
        return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
    except OTPExpiredError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except serializers.ValidationError as e: # Catch validation error from service (e.g. uniqueness)
        return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
    except PhoneAuthError as e: # Catch other specific auth errors
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e: # Catch any other unexpected errors
        # Log the error e
        return Response(
            {"status": "error", "message": "An unexpected error occurred during phone verification."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )



@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def set_squirll_id(request):
    ser = SquirllIDSerializer(instance=request.user, data=request.data, partial=True)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
    ser.save()
    return Response(
        {"status": "success", "message": "Squirll id saved successfully."},
        status=status.HTTP_200_OK,
    )

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def userprofile(request):
    """
    Return info for the currently authenticated user 
    (which is now an instance of `core.UserProfile`).
    """
    user = request.user 

    data = {
        "squirll_id": user.squirll_id,
        "email": user.email,
        "phone_number": user.phone_number,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "user_id": user.id,
    }

    return Response({"status": "success", "user": data}, status=200)


# Test DB Connection Endpoint
@api_view(["GET"])
def test_db_connection(request):
    try:
        # Attempt a simple query
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "success", "message": "Database is connected!"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})

#QR Code Endpoint
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def generate_user_qr_view(request):
    """
    Generates and returns a QR code image (PNG) for the authenticated user's
    username@squirll.com. 
    """
    # We assume the 'username' is the user's username field
    # and you want to combine it with "@squirll.com"
    user_email = f"{request.user.username}@squirll.com"
    
    # Create the QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4
    )
    qr.add_data(user_email)
    qr.make(fit=True)
 
    # Convert to image
    img = qr.make_image(fill_color="black", back_color="white")
 
    # Save image to an in-memory buffer
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
 
    # Return as an HTTP response with PNG image data
    return HttpResponse(buffer, content_type="image/png")


class OAuthRateThrottle(AnonRateThrottle):
    """Custom throttle class for OAuth endpoints"""
    scope = 'oauth'

@api_view(["POST"])
@throttle_classes([OAuthRateThrottle])
def google_login(request):
    """
    Exchange a Google ID-token for JWT access and refresh tokens.
    
    Body: {"id_token": "..."}
    Returns: {"access": "...", "refresh": "...", "new_user": boolean}
    """
    
    # Log the attempt with user agent for debugging
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    client_ip = request.META.get('REMOTE_ADDR', 'Unknown')
    logger.info(f"Google OAuth login attempt from {client_ip} - {user_agent}")
    
    # Basic input validation
    token = request.data.get("id_token")
    if not token:
        logger.warning("Google OAuth: Missing id_token in request")
        return Response(
            {"detail": "id_token is required"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    # Basic token validation
    if not isinstance(token, str) or len(token) > 2048:  # Google tokens are ~1000 chars
        return Response({"detail": "Invalid token format"}, status=400)

    # Verify the Google ID token
    payload, error = verify_google_id_token(token)
    if error:
        logger.warning(f"Google OAuth verification failed: {error}")
        return Response(
            {"detail": error}, 
            status=status.HTTP_401_UNAUTHORIZED
        )

    # Extract user information from the verified payload
    email = payload["email"].lower()
    first = payload.get("given_name", "")
    last  = payload.get("family_name", "")

    try:
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "first_name": first,
                "last_name": last,
                "subscription_type": User.FREE,
            },
        )
        new_user = False
        if created:
            user.set_unusable_password()
            user.save() 
            new_user = True
            logger.info(f"Google OAuth: Created new user account for {email}")
        else:
            # Update user info if they already exist (in case name changed)
            if user.first_name != first or user.last_name != last:
                user.first_name = first
                user.last_name = last
                user.save(update_fields=["first_name", "last_name"])
                logger.info(f"Google OAuth: Updated user info for {email}")
            
            logger.info(f"Google OAuth: Existing user login for {email}")

        refresh = RefreshToken.for_user(user)
        logger.info(f"Google OAuth: Successful login for {email}")
        
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "new_user": new_user,
            },
            status=status.HTTP_200_OK,
        )
        
    except Exception as e:
        logger.error(f"Google OAuth: Unexpected error during user creation/login for {email}: {str(e)}")
        return Response(
            {"detail": "An error occurred during authentication. Please try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@throttle_classes([OAuthRateThrottle])
def apple_login(request):
    """
    Exchange an Apple ID-token for JWT access and refresh tokens.
    
    Body: {"id_token": "..."}
    Returns: {"access": "...", "refresh": "...", "new_user": boolean}
    """
    
    # Log the attempt with user agent for debugging
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    client_ip = request.META.get('REMOTE_ADDR', 'Unknown')
    logger.info(f"Apple OAuth login attempt from {client_ip} - {user_agent}")
    
    # Basic input validation
    token = request.data.get("id_token")
    if not token:
        logger.warning("Apple OAuth: Missing id_token in request")
        return Response(
            {"detail": "id_token is required"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Basic token validation
    if not isinstance(token, str) or len(token) > 4096:  # Apple tokens can be larger than Google
        logger.warning("Apple OAuth: Invalid token format")
        return Response(
            {"detail": "Invalid token format"}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    # Verify the Apple ID token
    payload, error = verify_apple_id_token(token)
    if error:
        logger.warning(f"Apple OAuth verification failed: {error}")
        return Response(
            {"detail": error}, 
            status=status.HTTP_401_UNAUTHORIZED
        )

    # Extract user information from the verified payload
    email = payload["email"].lower()
    
    # Apple can provide names in different formats
    first_name = ""
    last_name = ""
    
    # Check for direct name fields (common on first login)
    if "given_name" in payload:
        first_name = payload["given_name"]
    if "family_name" in payload:
        last_name = payload["family_name"]
    
    # Check for nested name object (alternative format)
    if "name" in payload and isinstance(payload["name"], dict):
        name_obj = payload["name"]
        if "firstName" in name_obj:
            first_name = name_obj["firstName"]
        if "lastName" in name_obj:
            last_name = name_obj["lastName"]

    try:
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "first_name": first_name,
                "last_name": last_name,
                "subscription_type": User.FREE,
            },
        )
        
        new_user = False
        if created:
            # For new users, set up all fields and save once
            user.set_unusable_password()
            user.is_email_verified = True  # Apple emails are always verified
            user.email_verified_at = timezone.now()
            user.save(update_fields=['password', 'is_email_verified', 'email_verified_at'])
            new_user = True
            logger.info(f"Apple OAuth: Created new user account for {email}")
        else:
            # Update existing user info - combine all updates into single save
            updated_fields = []
            
            # Update name fields if we have new data
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated_fields.append("first_name")
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                updated_fields.append("last_name")
            
            # Mark email as verified if it wasn't already (Apple emails are always verified)
            if not user.is_email_verified:
                user.is_email_verified = True
                user.email_verified_at = timezone.now()
                updated_fields.extend(["is_email_verified", "email_verified_at"])
            
            # Save all updates in a single database operation
            if updated_fields:
                user.save(update_fields=updated_fields)
                logger.info(f"Apple OAuth: Updated user info for {email}")
            
            logger.info(f"Apple OAuth: Existing user login for {email}")

        refresh = RefreshToken.for_user(user)
        logger.info(f"Apple OAuth: Successful login for {email}")
        
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "new_user": new_user,
            },
            status=status.HTTP_200_OK,
        )
        
    except Exception as e:
        logger.error(f"Apple OAuth: Unexpected error during user creation/login for {email}: {str(e)}")
        return Response(
            {"detail": "An error occurred during authentication. Please try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
def password_reset_request(request):
    """
    Request password reset by email.
    POST /api/auth/password-reset/
    Body: {"email": "user@example.com"}
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data["email"]
    
    try:
        # Always return success to prevent email enumeration
        send_password_reset_email(email, request)
        
        return Response({
            "status": "success",
            "message": "If an account with that email exists, a password reset link has been sent."
        }, status=status.HTTP_200_OK)
        
    except UserNotFoundError:
        # Still return success to prevent email enumeration
        return Response({
            "status": "success", 
            "message": "If an account with that email exists, a password reset link has been sent."
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Password reset request error: {str(e)}")
        return Response({
            "status": "error",
            "message": "An error occurred while processing your request. Please try again."
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
def password_reset_verify(request, token):
    """
    Verify password reset token (check if it's valid without using it).
    GET /api/auth/password-reset/verify/<token>/
    """
    try:
        reset_token = verify_password_reset_token(token)
        return Response({
            "status": "success",
            "message": "Password reset token is valid.",
            "email": reset_token.user.email,
        }, status=status.HTTP_200_OK)
        
    except PasswordResetTokenNotFoundError:
        return Response({
            "status": "error",
            "message": "Invalid password reset link. Please request a new one.",
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except PasswordResetTokenExpiredError:
        return Response({
            "status": "error",
            "message": "This password reset link has expired. Please request a new one.",
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except PasswordResetTokenAlreadyUsedError:
        return Response({
            "status": "error",
            "message": "This password reset link has already been used. Please request a new one if needed.",
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Password reset verification error: {str(e)}")
        return Response({
            "status": "error",
            "message": "An error occurred while verifying the reset link.",
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
def password_reset_confirm(request, token):
    """
    Confirm password reset with new password.
    POST /api/auth/password-reset/confirm/<token>/
    Body: {"new_password": "...", "confirm_password": "..."}
    """
    # Add token to request data for validation
    data = request.data.copy()
    data['token'] = token
    
    serializer = PasswordResetConfirmSerializer(data=data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        new_password = serializer.validated_data["new_password"]
        user = reset_user_password(token, new_password)
        
        return Response({
            "status": "success",
            "message": "Your password has been reset successfully. You can now log in with your new password.",
            "email": user.email,
        }, status=status.HTTP_200_OK)
        
    except PasswordResetTokenNotFoundError:
        return Response({
            "status": "error",
            "message": "Invalid password reset link. Please request a new one.",
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except PasswordResetTokenExpiredError:
        return Response({
            "status": "error",
            "message": "This password reset link has expired. Please request a new one.",
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except PasswordResetTokenAlreadyUsedError:
        return Response({
            "status": "error",
            "message": "This password reset link has already been used. Please request a new one if needed.",
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Password reset confirmation error: {str(e)}")
        return Response({
            "status": "error",
            "message": "An error occurred while resetting your password. Please try again.",
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
