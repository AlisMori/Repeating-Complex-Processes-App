from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import override_settings
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
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
        self.assertIn("tokens", response.data)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])

    def test_me_requires_jwt_authentication(self):
        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_accepts_bearer_token(self):
        login_response = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "StrongPass123!"},
            format="json",
        )
        access_token = login_response.data["tokens"]["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get(reverse("auth-me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "alice")

    def test_logout_blacklists_refresh_token(self):
        login_response = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "StrongPass123!"},
            format="json",
        )
        access_token = login_response.data["tokens"]["access"]
        refresh_token = login_response.data["tokens"]["refresh"]

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
