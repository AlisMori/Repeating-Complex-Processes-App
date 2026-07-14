from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from .models import AuthSession


SESSION_INACTIVE_DETAIL = "Your session expired after 30 minutes of inactivity."


class SessionInactive(APIException):
    status_code = 401
    default_code = "session_inactive"

    def __init__(self, detail=SESSION_INACTIVE_DETAIL):
        super().__init__(
            detail={
                "code": self.default_code,
                "detail": detail,
            }
        )


def get_inactivity_timeout():
    return getattr(settings, "AUTH_SESSION_INACTIVITY_TIMEOUT", timedelta(minutes=30))


def get_inactivity_expiry(last_activity_at):
    return last_activity_at + get_inactivity_timeout()


def serialize_session_window(session):
    inactivity_expires_at = get_inactivity_expiry(session.last_activity_at)
    return {
        "last_activity_at": session.last_activity_at.isoformat(),
        "inactivity_expires_at": inactivity_expires_at.isoformat(),
    }


def build_token_payload(user):
    now = timezone.now()
    refresh = RefreshToken.for_user(user)
    session = AuthSession.objects.create(
        user=user,
        current_refresh_jti=refresh["jti"],
        last_activity_at=now,
    )
    sid = str(session.session_id)
    refresh["sid"] = sid
    access = refresh.access_token
    access["sid"] = sid

    return {
        "access": str(access),
        "refresh": str(refresh),
        **serialize_session_window(session),
    }


def get_authenticated_session(request, lock=False):
    token = getattr(request, "auth", None)
    session_id = token.get("sid") if token else None
    if not session_id:
        raise AuthenticationFailed("Authentication credentials were not provided.")

    queryset = AuthSession.objects
    if lock:
        queryset = queryset.select_for_update()

    try:
        session = queryset.get(session_id=session_id, user=request.user)
    except AuthSession.DoesNotExist as exc:
        raise AuthenticationFailed("Authentication credentials were not provided.") from exc

    if session.revoked_at is not None:
        raise AuthenticationFailed("Authentication credentials were not provided.")

    return session


def touch_authenticated_session(request):
    with transaction.atomic():
        session = get_authenticated_session(request, lock=True)
        session.last_activity_at = timezone.now()
        session.save(update_fields=["last_activity_at"])
        return session
