from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import base36_to_int, urlsafe_base64_decode


User = get_user_model()

PASSWORD_RESET_TOKEN_STATUS_VALID = "valid"
PASSWORD_RESET_TOKEN_STATUS_INVALID = "invalid"
PASSWORD_RESET_TOKEN_STATUS_EXPIRED = "expired"


def get_user_from_password_reset_uid(uidb64):
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        return User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError, User.DoesNotExist):
        return None


def get_password_reset_token_status(user, token):
    if not token or "-" not in token:
        return PASSWORD_RESET_TOKEN_STATUS_INVALID

    if default_token_generator.check_token(user, token):
        return PASSWORD_RESET_TOKEN_STATUS_VALID

    try:
        timestamp_b36, _hash = token.split("-", 1)
        token_timestamp = base36_to_int(timestamp_b36)
    except (TypeError, ValueError):
        return PASSWORD_RESET_TOKEN_STATUS_INVALID

    current_timestamp = default_token_generator._num_seconds(default_token_generator._now())
    if current_timestamp - token_timestamp > settings.PASSWORD_RESET_TIMEOUT:
        return PASSWORD_RESET_TOKEN_STATUS_EXPIRED

    return PASSWORD_RESET_TOKEN_STATUS_INVALID
