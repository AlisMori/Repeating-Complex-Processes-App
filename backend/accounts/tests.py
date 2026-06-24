from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import override_settings
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework import status
from rest_framework.test import APITestCase


User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="test@example.com",
    ALLOWED_HOSTS=["testserver", "localhost"],
)
class AuthApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="StrongPass123!",
        )

    def test_register_creates_user_with_hashed_password(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "username": "bob",
                "email": "bob@example.com",
                "password": "StrongPass456!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("user", response.data)
        self.assertNotIn("password", response.data)
        self.assertNotIn("password", response.data["user"])

        created_user = User.objects.get(username="bob")
        self.assertEqual(created_user.email, "bob@example.com")
        self.assertNotEqual(created_user.password, "StrongPass456!")
        self.assertTrue(created_user.check_password("StrongPass456!"))

    def test_register_rejects_duplicate_username(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "username": "alice",
                "email": "new@example.com",
                "password": "StrongPass456!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    def test_register_rejects_duplicate_email_case_insensitively(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "username": "bob",
                "email": "ALICE@EXAMPLE.COM",
                "password": "StrongPass456!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_login_returns_jwt_tokens(self):
        response = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "StrongPass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["username"], "alice")

    def test_login_rejects_invalid_password_with_generic_error(self):
        response = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "WrongPass123!"},
            format="json",
        )

        self.assertIn(
            response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED],
        )
        self.assertEqual(response.data["detail"], "Invalid username or password.")

    def test_login_rejects_nonexistent_user_with_generic_error(self):
        response = self.client.post(
            reverse("auth-login"),
            {"username": "missing", "password": "WrongPass123!"},
            format="json",
        )

        self.assertIn(
            response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED],
        )
        self.assertEqual(response.data["detail"], "Invalid username or password.")

    def test_login_response_excludes_password_fields(self):
        response = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "StrongPass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("password", response.data)
        self.assertNotIn("password", response.data["user"])

    def test_public_auth_endpoints_are_reachable_without_jwt(self):
        register_response = self.client.post(
            reverse("auth-register"),
            {
                "username": "bob",
                "email": "bob@example.com",
                "password": "StrongPass456!",
            },
            format="json",
        )
        login_response = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "StrongPass123!"},
            format="json",
        )
        password_reset_response = self.client.post(
            reverse("auth-password-reset"),
            {"email": "alice@example.com"},
            format="json",
        )
        uid = urlsafe_base64_encode(str(self.user.pk).encode())
        token = default_token_generator.make_token(self.user)
        password_reset_confirm_response = self.client.post(
            reverse("auth-password-reset-confirm"),
            {
                "uid": uid,
                "token": token,
                "new_password": "EvenStronger123!",
            },
            format="json",
        )

        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertEqual(password_reset_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            password_reset_confirm_response.status_code,
            status.HTTP_200_OK,
        )

    def test_me_requires_jwt_authentication(self):
        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_accepts_bearer_token(self):
        login_response = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "StrongPass123!"},
            format="json",
        )
        access_token = login_response.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get(reverse("auth-me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "alice")

    def test_me_rejects_invalid_jwt(self):
        token = AccessToken.for_user(self.user)
        token.set_exp(lifetime=timedelta(seconds=-1))

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get(reverse("auth-me"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_refresh_token(self):
        login_response = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "StrongPass123!"},
            format="json",
        )
        access_token = login_response.data["access"]
        refresh_token = login_response.data["refresh"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        logout_response = self.client.post(
            reverse("auth-logout"),
            {"refresh": refresh_token},
            format="json",
        )

        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

        refresh_response = self.client.post(
            reverse("auth-token-refresh"),
            {"refresh": refresh_token},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_authenticated_user(self):
        login_response = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "StrongPass123!"},
            format="json",
        )

        response = self.client.post(
            reverse("auth-logout"),
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_returns_400_when_refresh_token_is_missing(self):
        login_response = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "StrongPass123!"},
            format="json",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

        response = self.client.post(reverse("auth-logout"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["refresh"], ["This field is required."])

    def test_logout_returns_400_when_refresh_token_is_invalid(self):
        login_response = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "StrongPass123!"},
            format="json",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

        response = self.client.post(
            reverse("auth-logout"),
            {"refresh": "not-a-valid-refresh-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["refresh"], ["Invalid refresh token."])

    def test_password_reset_confirm_changes_password(self):
        uid = urlsafe_base64_encode(str(self.user.pk).encode())
        token = default_token_generator.make_token(self.user)

        response = self.client.post(
            reverse("auth-password-reset-confirm"),
            {
                "uid": uid,
                "token": token,
                "new_password": "EvenStronger123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("EvenStronger123!"))

    def test_password_reset_request_sends_email(self):
        response = self.client.post(
            reverse("auth-password-reset"),
            {"email": "alice@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
