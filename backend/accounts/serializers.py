from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework.exceptions import AuthenticationFailed
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken


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
    new_password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate(self, attrs):
        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"uid": ["Invalid reset link."]})

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": ["Invalid or expired reset token."]})

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
        form = PasswordResetForm(data={"email": self.validated_data["email"]})
        form.full_clean()
        form.save(
            request=request,
            use_https=request.is_secure() if request is not None else False,
            from_email=settings.DEFAULT_FROM_EMAIL,
            email_template_name="registration/password_reset_email.html",
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
            RefreshToken(self.validated_data["refresh"]).blacklist()
        except TokenError:
            raise serializers.ValidationError(
                {"refresh": [self.error_messages["invalid_refresh"]]}
            )
