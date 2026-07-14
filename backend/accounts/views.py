from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from .auth_sessions import (
    build_token_payload,
    serialize_session_window,
    touch_authenticated_session,
)
from .serializers import (
    LoginSerializer,
    LoginUserSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    SlidingTokenRefreshSerializer,
    UserSerializer,
)


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
        serializer = UserSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


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


class SlidingTokenRefreshView(TokenRefreshView):
    serializer_class = SlidingTokenRefreshSerializer


class PasswordResetView(APIView):
    permission_classes = [permissions.AllowAny]

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

    def get(self, request, uidb64=None, token=None):
        return Response(
            {
                "uid": uidb64,
                "token": token,
                "detail": "Submit this uid and token to POST /api/auth/password-reset/confirm/ with a new password.",
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, uidb64=None, token=None):
        payload = request.data.copy()
        if uidb64 and "uid" not in payload:
            payload["uid"] = uidb64
        if token and "token" not in payload:
            payload["token"] = token

        serializer = PasswordResetConfirmSerializer(data=payload)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()

        return Response(
            {"message": "Password has been reset successfully."},
            status=status.HTTP_200_OK,
        )
