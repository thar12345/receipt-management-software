import random
from django.core.cache import cache
from twilio.rest import Client
from squirll.settings import TWILIO_ACCOUNT_SID, TWILIO_ACCOUNT_AUTH_TOKEN, TWILIO_PHONE_NUMBER
from django.contrib.auth import get_user_model
from rest_framework import serializers # For custom exceptions if needed

UserProfile = get_user_model()

# Custom Exceptions for better error handling in views
class PhoneAuthError(Exception):
    """Base class for phone auth errors."""
    pass

class OTPGenerationError(PhoneAuthError):
    """Error during OTP generation or sending."""
    pass

class OTPVerificationError(PhoneAuthError):
    """Base for OTP verification failures."""
    pass

class InvalidOTPError(OTPVerificationError):
    """Invalid OTP provided."""
    pass

class OTPExpiredError(OTPVerificationError):
    """OTP expired or not found."""
    pass


def send_phone_verification_otp(user, phone_number) -> str:
    """
    Generates an OTP, sends it via Twilio, and caches it.

    Args:
        user: The UserProfile instance.
        phone_number: The phone number (already validated for format and initial uniqueness).

    Returns:
        The OTP code that was sent (primarily for testing/logging if needed).

    Raises:
        OTPGenerationError: If Twilio SMS sending fails.
    """
    otp_code = str(random.randint(1000, 9999))

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_ACCOUNT_AUTH_TOKEN)
        client.messages.create(
            body=f"Your Squirll verification code is: {otp_code}",
            from_=TWILIO_PHONE_NUMBER,
            to=f"+{phone_number}", # Assuming phone_number is digits only, add '+' for Twilio
        )
    except Exception as e:
        # Log the exception e
        raise OTPGenerationError(f"Failed to send OTP via Twilio: {str(e)}")

    cache.set(
        f"phone_otp_for_user_{user.id}",
        {"phone_number": phone_number, "otp": otp_code},
        timeout=120,  # seconds
    )
    return otp_code


def verify_and_set_phone(user, otp_code_provided) -> str:
    """
    Verifies the OTP and sets the phone number on the user model if valid.

    Args:
        user: The UserProfile instance.
        otp_code_provided: The OTP code provided by the user.

    Returns:
        The verified phone number.

    Raises:
        OTPExpiredError: If the OTP is expired or was never generated.
        InvalidOTPError: If the provided OTP is incorrect.
        serializers.ValidationError: If the phone number fails final uniqueness check (should be rare).
    """
    cache_key = f"phone_otp_for_user_{user.id}"
    cached_data = cache.get(cache_key)

    if not cached_data:
        raise OTPExpiredError("OTP expired or not found. Please request a new one.")

    phone_number_from_cache = cached_data["phone_number"]
    stored_otp = cached_data["otp"]

    if stored_otp != otp_code_provided:
        raise InvalidOTPError("The OTP code provided is invalid.")

    # Final check for uniqueness before saving to prevent race conditions,
    # though SetPhoneSerializer should have caught most.
    # This assumes phone_number_from_cache is digits-only.
    if UserProfile.objects.filter(phone_number=phone_number_from_cache).exclude(pk=user.pk).exists():
        raise serializers.ValidationError({"phone_number": ["This phone number has just been claimed."]})

    user.phone_number = phone_number_from_cache
    user.save(update_fields=["phone_number"])
    cache.delete(cache_key)

    return phone_number_from_cache
