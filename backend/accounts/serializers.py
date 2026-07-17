from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .auth_sessions import (
    SessionInactive,
    get_inactivity_expiry,
    serialize_session_window,
)
from .forms import SafeMessageIdPasswordResetForm
from .models import AuthSession
from .password_reset import (
    PASSWORD_RESET_TOKEN_STATUS_EXPIRED,
    PASSWORD_RESET_TOKEN_STATUS_VALID,
    get_password_reset_token_status,
    get_user_from_password_reset_uid,
)


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "notification_opt_in",
            "created_at",
        ]


class LoginUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


class RegisterSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "notification_opt_in",
            "password",
        ]

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_email(self, value):
        normalized_email = value.strip().lower()
        if User.objects.filter(email__iexact=normalized_email).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return normalized_email

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    default_error_messages = {
        "invalid_credentials": "Invalid username or password.",
    }

    def validate(self, attrs):
        request = self.context.get("request")
        username = attrs.get("username")
        password = attrs.get("password")

        user = authenticate(
            request=request,
            username=username,
            password=password,
        )

        if user is None:
            raise AuthenticationFailed(self.error_messages["invalid_credentials"])

        attrs["user"] = user
        return attrs


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = get_user_from_password_reset_uid(attrs["uid"])
        if user is None:
            raise serializers.ValidationError({"uid": ["Invalid reset link."]})

        token_status = get_password_reset_token_status(user, attrs["token"])
        if token_status == PASSWORD_RESET_TOKEN_STATUS_EXPIRED:
            raise serializers.ValidationError({"token": ["This reset link has expired."]})
        if token_status != PASSWORD_RESET_TOKEN_STATUS_VALID:
            raise serializers.ValidationError({"token": ["Invalid reset link."]})

        try:
            validate_password(attrs["new_password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})

        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self):
        request = self.context.get("request")
        django_request = getattr(request, "_request", request)
        form = SafeMessageIdPasswordResetForm(data={"email": self.validated_data["email"]})
        form.full_clean()
        form.save(
            request=django_request,
            use_https=django_request.is_secure() if django_request is not None else False,
            from_email=settings.DEFAULT_FROM_EMAIL,
            email_template_name="registration/password_reset_email.txt",
            html_email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
        )


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    default_error_messages = {
        "invalid_refresh": "Invalid refresh token.",
    }

    def validate_refresh(self, value):
        try:
            RefreshToken(value)
        except TokenError:
            raise serializers.ValidationError(self.error_messages["invalid_refresh"])
        return value

    def save(self):
        try:
            refresh = RefreshToken(self.validated_data["refresh"])
            request = self.context.get("request")
            if request is not None and str(refresh.get("user_id")) != str(request.user.id):
                raise TokenError("refresh token user mismatch")

            session_id = refresh.get("sid")
            if session_id and request is not None:
                AuthSession.objects.filter(
                    session_id=session_id,
                    user=request.user,
                    revoked_at__isnull=True,
                ).update(revoked_at=timezone.now())

            refresh.blacklist()
        except TokenError:
            raise serializers.ValidationError(
                {"refresh": [self.error_messages["invalid_refresh"]]}
            )


class SlidingTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = RefreshToken(attrs["refresh"])
        session_id = refresh.get("sid")
        refresh_jti = refresh.get("jti")

        if not session_id or not refresh_jti:
            raise AuthenticationFailed("Invalid refresh token.")

        with transaction.atomic():
            try:
                session = AuthSession.objects.select_for_update().get(
                    session_id=session_id,
                    user_id=refresh["user_id"],
                )
            except AuthSession.DoesNotExist as exc:
                raise AuthenticationFailed("Invalid refresh token.") from exc

            if session.revoked_at is not None:
                raise AuthenticationFailed("Invalid refresh token.")

            if session.current_refresh_jti != refresh_jti:
                raise AuthenticationFailed("Invalid refresh token.")

            if timezone.now() > get_inactivity_expiry(session.last_activity_at):
                session.revoked_at = timezone.now()
                session.save(update_fields=["revoked_at"])
                try:
                    refresh.blacklist()
                except TokenError:
                    pass
                raise SessionInactive()

            data = super().validate(attrs)

            rotated_refresh = data.get("refresh")
            if rotated_refresh:
                rotated_token = RefreshToken(rotated_refresh)
                session.current_refresh_jti = rotated_token["jti"]
                session.save(update_fields=["current_refresh_jti"])

            data.update(serialize_session_window(session))
            return data
