from django.contrib.auth import authenticate
from django.contrib.auth.forms import PasswordResetForm
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    RegisterSerializer,
    UserSerializer,
)


def build_token_payload(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


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
                    "tokens": build_token_payload(user),
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is None:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Logged in successfully.",
                "user": UserSerializer(user).data,
                "tokens": build_token_payload(user),
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"refresh": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response(
                {"refresh": ["Invalid refresh token."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

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


class PasswordResetView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response(
                {"email": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        form = PasswordResetForm(data={"email": email})

        if form.is_valid():
            form.save(
                request=request,
                use_https=request.is_secure(),
                from_email=None,
                email_template_name="registration/password_reset_email.html",
                subject_template_name="registration/password_reset_subject.txt",
            )

        return Response(
            {
                "message": "If an account with that email exists, a password reset email has been sent."
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
