from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView
from django.contrib.auth import get_user_model

from .password_reset import (
    PASSWORD_RESET_TOKEN_STATUS_EXPIRED,
    PASSWORD_RESET_TOKEN_STATUS_VALID,
    get_password_reset_token_status,
    get_user_from_password_reset_uid,
)
from .auth_sessions import (
    build_token_payload,
    serialize_session_window,
    touch_authenticated_session,
)
from .serializers import (
    DeleteAccountSerializer,
    LoginSerializer,
    LoginUserSerializer,
    LogoutSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    ShareNotificationSerializer,
    SlidingTokenRefreshSerializer,
    UserSerializer,
    UserLookupSerializer,
    UserProfileUpdateSerializer,
)
from .models import ShareNotification


User = get_user_model()


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            return Response(
                {
                    "message": "Account created successfully.",
                    "user": UserSerializer(user).data,
                    **build_token_payload(user),
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data["user"]

        return Response(
            {
                "user": LoginUserSerializer(user).data,
                **build_token_payload(user),
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data, context={"request": request})

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()

        return Response(
            {"message": "Logged out successfully."},
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            UserSerializer(request.user).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        serializer = UserProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(
            {"message": "Password updated successfully."},
            status=status.HTTP_200_OK,
        )


class DeleteAccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = DeleteAccountSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(
            {"message": "Account deleted successfully."},
            status=status.HTTP_200_OK,
        )


class ActivityView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        session = touch_authenticated_session(request)
        return Response(
            {
                "detail": "Activity recorded.",
                "code": "activity_recorded",
                **serialize_session_window(session),
            },
            status=status.HTTP_200_OK,
        )


class UserSearchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        if not query:
            return Response([], status=status.HTTP_200_OK)

        users = User.objects.filter(username__icontains=query).exclude(pk=request.user.pk).order_by(
            "username"
        )[:8]
        return Response(UserLookupSerializer(users, many=True).data, status=status.HTTP_200_OK)


class ShareNotificationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        notifications = ShareNotification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).select_related("sender", "template")
        return Response(
            ShareNotificationSerializer(notifications, many=True).data,
            status=status.HTTP_200_OK,
        )


class MarkShareNotificationsReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ids = request.data.get("ids") or []
        queryset = ShareNotification.objects.filter(recipient=request.user, is_read=False)
        if ids:
            queryset = queryset.filter(notification_id__in=ids)
        updated = queryset.update(is_read=True)
        return Response({"updated": updated}, status=status.HTTP_200_OK)


class SlidingTokenRefreshView(TokenRefreshView):
    serializer_class = SlidingTokenRefreshSerializer


class PasswordResetView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(
            data=request.data,
            context={"request": request},
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()

        return Response(
            {
                "message": "If an account exists for this email, a password reset link has been sent."
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset_confirm"

    def get(self, request, uidb64=None, token=None):
        user = get_user_from_password_reset_uid(uidb64)
        if user is None:
            return Response(
                {
                    "code": "invalid_link",
                    "detail": "This password reset link is invalid.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        token_status = get_password_reset_token_status(user, token)
        if token_status == PASSWORD_RESET_TOKEN_STATUS_VALID:
            return Response(
                {
                    "code": "valid_link",
                    "detail": "This password reset link is valid.",
                    "uid": uidb64,
                    "token": token,
                },
                status=status.HTTP_200_OK,
            )

        if token_status == PASSWORD_RESET_TOKEN_STATUS_EXPIRED:
            return Response(
                {
                    "code": "expired_link",
                    "detail": "This password reset link has expired.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "code": "invalid_link",
                "detail": "This password reset link is invalid.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    def post(self, request, uidb64=None, token=None):
        payload = request.data.copy()
        if uidb64 and "uid" not in payload:
            payload["uid"] = uidb64
        if token and "token" not in payload:
            payload["token"] = token

        serializer = PasswordResetConfirmSerializer(data=payload)

        if not serializer.is_valid():
            errors = dict(serializer.errors)
            token_errors = errors.get("token", [])
            uid_errors = errors.get("uid", [])

            if "This reset link has expired." in token_errors:
                errors["code"] = "expired_link"
            elif "Invalid reset link." in token_errors or "Invalid reset link." in uid_errors:
                errors["code"] = "invalid_link"

            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()

        return Response(
            {"message": "Password has been reset successfully."},
            status=status.HTTP_200_OK,
        )
