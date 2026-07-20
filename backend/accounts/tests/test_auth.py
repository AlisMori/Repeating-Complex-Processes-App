from datetime import timedelta
import re
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.forms import format_password_reset_expiry
from accounts.models import AuthSession
from cycles.models import CycleInstance
from templates_mgmt.models import Template


User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="test@example.com",
    ALLOWED_HOSTS=["testserver", "localhost"],
    FRONTEND_URL="http://localhost:5173",
)
class AuthApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="StrongPass123!",
        )

    def build_reset_uid(self):
        return urlsafe_base64_encode(str(self.user.pk).encode())

    def build_reset_token(self):
        return default_token_generator.make_token(self.user)

    def extract_reset_urls(self, text):
        return re.findall(r"http://localhost:5173/auth/password-reset/confirm/\S+", text)

    def login_and_get_tokens(self):
        response = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response

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
        response = self.login_and_get_tokens()

        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["username"], "alice")

    def test_login_creates_authenticated_session(self):
        response = self.login_and_get_tokens()

        self.assertIn("last_activity_at", response.data)
        self.assertIn("inactivity_expires_at", response.data)
        session = AuthSession.objects.get(user=self.user)
        self.assertIsNone(session.revoked_at)
        self.assertEqual(AuthSession.objects.count(), 1)

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
        uid = self.build_reset_uid()
        token = self.build_reset_token()
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
        login_response = self.login_and_get_tokens()
        access_token = login_response.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get(reverse("auth-me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "alice")

    def test_me_patch_updates_profile_fields(self):
        login_response = self.login_and_get_tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")

        response = self.client.patch(
            reverse("auth-me"),
            {
                "first_name": "Alice",
                "last_name": "Ng",
                "email": "alice.ng@example.com",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Alice")
        self.assertEqual(self.user.last_name, "Ng")
        self.assertEqual(self.user.email, "alice.ng@example.com")

    def test_me_patch_rejects_duplicate_email(self):
        User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="StrongPass456!",
        )
        login_response = self.login_and_get_tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")

        response = self.client.patch(
            reverse("auth-me"),
            {"email": "BOB@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["email"], ["A user with that email already exists."])

    def test_change_password_updates_hashed_password(self):
        login_response = self.login_and_get_tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")

        response = self.client.post(
            reverse("auth-change-password"),
            {
                "current_password": "StrongPass123!",
                "new_password": "EvenStronger123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("EvenStronger123!"))
        self.assertNotEqual(self.user.password, "EvenStronger123!")

    def test_change_password_rejects_wrong_current_password(self):
        login_response = self.login_and_get_tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")

        response = self.client.post(
            reverse("auth-change-password"),
            {
                "current_password": "WrongPass123!",
                "new_password": "EvenStronger123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["current_password"], ["Current password is incorrect."])

    def test_change_password_rejects_weak_new_password(self):
        login_response = self.login_and_get_tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")

        response = self.client.post(
            reverse("auth-change-password"),
            {
                "current_password": "StrongPass123!",
                "new_password": "123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.data)

    def test_delete_account_deletes_user_and_owned_records(self):
        template = Template.objects.create(user=self.user, template_name="Owned Template")
        CycleInstance.objects.create(
            user=self.user,
            template=template,
            cycle_name="Owned Cycle",
            start_date=timezone.localdate(),
            status="running",
        )
        login_response = self.login_and_get_tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")

        response = self.client.post(
            reverse("auth-delete-account"),
            {
                "confirmation_text": "DELETE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertEqual(CycleInstance.objects.count(), 0)

    def test_delete_account_rejects_wrong_confirmation_text(self):
        login_response = self.login_and_get_tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")

        response = self.client.post(
            reverse("auth-delete-account"),
            {
                "confirmation_text": "delete",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["confirmation_text"],
            ["Type DELETE to confirm account deletion."],
        )

    def test_me_rejects_invalid_jwt(self):
        token = AccessToken.for_user(self.user)
        token.set_exp(lifetime=timedelta(seconds=-1))

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get(reverse("auth-me"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_refresh_token(self):
        login_response = self.login_and_get_tokens()
        access_token = login_response.data["access"]
        refresh_token = login_response.data["refresh"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        logout_response = self.client.post(
            reverse("auth-logout"),
            {"refresh": refresh_token},
            format="json",
        )

        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(AuthSession.objects.get(user=self.user).revoked_at)

        refresh_response = self.client.post(
            reverse("auth-token-refresh"),
            {"refresh": refresh_token},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_authenticated_user(self):
        login_response = self.login_and_get_tokens()

        response = self.client.post(
            reverse("auth-logout"),
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_returns_400_when_refresh_token_is_missing(self):
        login_response = self.login_and_get_tokens()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

        response = self.client.post(reverse("auth-logout"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["refresh"], ["This field is required."])

    def test_logout_returns_400_when_refresh_token_is_invalid(self):
        login_response = self.login_and_get_tokens()
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
        uid = self.build_reset_uid()
        token = self.build_reset_token()
        new_password = "EvenStronger123!"

        response = self.client.post(
            reverse("auth-password-reset-confirm"),
            {
                "uid": uid,
                "token": token,
                "new_password": new_password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

    def test_password_reset_confirm_allows_login_with_new_password(self):
        uid = self.build_reset_uid()
        token = self.build_reset_token()
        new_password = "EvenStronger123!"

        reset_response = self.client.post(
            reverse("auth-password-reset-confirm"),
            {
                "uid": uid,
                "token": token,
                "new_password": new_password,
            },
            format="json",
        )
        login_response = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": new_password},
            format="json",
        )

        self.assertEqual(reset_response.status_code, status.HTTP_200_OK)
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_response.data)

    def test_access_token_can_expire_while_session_remains_active(self):
        login_response = self.login_and_get_tokens()
        expired_access = AccessToken(login_response.data["access"])
        expired_access.set_exp(lifetime=timedelta(seconds=-1))

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {expired_access}")
        me_response = self.client.get(reverse("auth-me"))

        self.assertEqual(me_response.status_code, status.HTTP_401_UNAUTHORIZED)

        refresh_response = self.client.post(
            reverse("auth-token-refresh"),
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_response.data)
        self.assertIsNone(AuthSession.objects.get(user=self.user).revoked_at)

    def test_refresh_succeeds_while_session_is_active(self):
        login_response = self.login_and_get_tokens()
        session = AuthSession.objects.get(user=self.user)
        session.last_activity_at = timezone.now() - timedelta(minutes=29)
        session.save(update_fields=["last_activity_at"])

        refresh_response = self.client.post(
            reverse("auth-token-refresh"),
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn("refresh", refresh_response.data)
        self.assertIn("inactivity_expires_at", refresh_response.data)

    def test_refresh_fails_after_inactivity_timeout(self):
        login_response = self.login_and_get_tokens()
        session = AuthSession.objects.get(user=self.user)
        session.last_activity_at = timezone.now() - timedelta(minutes=31)
        session.save(update_fields=["last_activity_at"])

        refresh_response = self.client.post(
            reverse("auth-token-refresh"),
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(refresh_response.data["code"], "session_inactive")
        self.assertEqual(
            refresh_response.data["detail"],
            "Your session expired after 30 minutes of inactivity.",
        )

    def test_activity_endpoint_updates_last_activity(self):
        login_response = self.login_and_get_tokens()
        session = AuthSession.objects.get(user=self.user)
        earlier = timezone.now() - timedelta(minutes=10)
        session.last_activity_at = earlier
        session.save(update_fields=["last_activity_at"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")
        response = self.client.post(reverse("auth-activity"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        session.refresh_from_db()
        self.assertGreater(session.last_activity_at, earlier)
        self.assertEqual(response.data["code"], "activity_recorded")

    def test_anonymous_user_cannot_update_activity(self):
        response = self.client.post(reverse("auth-activity"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_activity_endpoint_ignores_client_supplied_timestamp(self):
        login_response = self.login_and_get_tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")

        response = self.client.post(
            reverse("auth-activity"),
            {"last_activity_at": "1999-01-01T00:00:00Z"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(response.data["last_activity_at"], "1999-01-01T00:00:00Z")

    def test_rotated_refresh_token_cannot_be_reused(self):
        login_response = self.login_and_get_tokens()
        first_refresh = self.client.post(
            reverse("auth-token-refresh"),
            {"refresh": login_response.data["refresh"]},
            format="json",
        )
        second_refresh = self.client.post(
            reverse("auth-token-refresh"),
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(first_refresh.status_code, status.HTTP_200_OK)
        self.assertEqual(second_refresh.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_multiple_refresh_attempts_keep_session_state_consistent(self):
        login_response = self.login_and_get_tokens()
        response = self.client.post(
            reverse("auth-token-refresh"),
            {"refresh": login_response.data["refresh"]},
            format="json",
        )
        session = AuthSession.objects.get(user=self.user)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(AuthSession.objects.count(), 1)
        self.assertNotEqual(session.current_refresh_jti, "")

        replay_response = self.client.post(
            reverse("auth-token-refresh"),
            {"refresh": login_response.data["refresh"]},
            format="json",
        )
        session.refresh_from_db()

        self.assertEqual(replay_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(AuthSession.objects.count(), 1)

    def test_password_reset_confirm_rejects_old_password_after_change(self):
        uid = self.build_reset_uid()
        token = self.build_reset_token()

        reset_response = self.client.post(
            reverse("auth-password-reset-confirm"),
            {
                "uid": uid,
                "token": token,
                "new_password": "EvenStronger123!",
            },
            format="json",
        )
        old_password_login_response = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "StrongPass123!"},
            format="json",
        )

        self.assertEqual(reset_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            old_password_login_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            old_password_login_response.data["detail"],
            "Invalid username or password.",
        )

    def test_password_reset_confirm_reused_token_fails(self):
        uid = self.build_reset_uid()
        token = self.build_reset_token()

        first_response = self.client.post(
            reverse("auth-password-reset-confirm"),
            {
                "uid": uid,
                "token": token,
                "new_password": "EvenStronger123!",
            },
            format="json",
        )
        second_response = self.client.post(
            reverse("auth-password-reset-confirm"),
            {
                "uid": uid,
                "token": token,
                "new_password": "AnotherStrong123!",
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            second_response.data["token"],
            ["Invalid reset link."],
        )

    def test_password_reset_confirm_invalid_token_fails(self):
        uid = self.build_reset_uid()

        response = self.client.post(
            reverse("auth-password-reset-confirm"),
            {
                "uid": uid,
                "token": "invalid-token",
                "new_password": "EvenStronger123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["token"], ["Invalid reset link."])

    def test_password_reset_confirm_weak_password_fails(self):
        uid = self.build_reset_uid()
        token = self.build_reset_token()

        response = self.client.post(
            reverse("auth-password-reset-confirm"),
            {
                "uid": uid,
                "token": token,
                "new_password": "123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.data)

    def test_password_reset_request_sends_email(self):
        response = self.client.post(
            reverse("auth-password-reset"),
            {"email": "alice@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"],
            "If an account exists for this email, a password reset link has been sent.",
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Recurra – Reset Your Password")

    def test_password_reset_request_unknown_email_returns_generic_success(self):
        response = self.client.post(
            reverse("auth-password-reset"),
            {"email": "missing@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"],
            "If an account exists for this email, a password reset link has been sent.",
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_request_rejects_invalid_email(self):
        response = self.client.post(
            reverse("auth-password-reset"),
            {"email": "not-an-email"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["email"], ["Enter a valid email address."])
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_request_does_not_reveal_account_existence(self):
        existing_response = self.client.post(
            reverse("auth-password-reset"),
            {"email": "alice@example.com"},
            format="json",
        )
        mail.outbox.clear()
        unknown_response = self.client.post(
            reverse("auth-password-reset"),
            {"email": "missing@example.com"},
            format="json",
        )

        self.assertEqual(existing_response.status_code, status.HTTP_200_OK)
        self.assertEqual(unknown_response.status_code, status.HTTP_200_OK)
        self.assertEqual(existing_response.data, unknown_response.data)

    def test_password_reset_email_uses_professional_multipart_templates(self):
        response = self.client.post(
            reverse("auth-password-reset"),
            {"email": "alice@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        expected_uid = self.build_reset_uid()
        expected_expiry_text = format_password_reset_expiry(
            settings.PASSWORD_RESET_TIMEOUT
        )

        self.assertEqual(email.subject, "Recurra – Reset Your Password")
        self.assertNotRegex(email.body, r"<[^>]+>")
        self.assertEqual(len(email.alternatives), 1)

        html_body, mimetype = email.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn(">Reset Password<", html_body)

        plain_urls = self.extract_reset_urls(email.body)

        self.assertEqual(len(plain_urls), 1)
        self.assertIn(expected_uid, plain_urls[0])
        self.assertIn(expected_uid, html_body)
        self.assertIn(f'href="{plain_urls[0]}"', html_body)
        self.assertIn(f">{plain_urls[0]}<", html_body)
        self.assertTrue(
            default_token_generator.check_token(
                self.user, plain_urls[0].rstrip("/").split("/")[-1]
            )
        )

        expiry_sentence = (
            f"This link will expire in {expected_expiry_text} and can only be used once."
        )
        self.assertIn(expiry_sentence, email.body)
        self.assertIn(expiry_sentence, html_body)

    @override_settings(PASSWORD_RESET_TIMEOUT=7200)
    def test_password_reset_email_expiry_text_tracks_password_reset_timeout(self):
        response = self.client.post(
            reverse("auth-password-reset"),
            {"email": "alice@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        html_body, mimetype = email.alternatives[0]
        self.assertEqual(mimetype, "text/html")

        expiry_sentence = (
            "This link will expire in 2 hours and can only be used once."
        )
        self.assertIn(expiry_sentence, email.body)
        self.assertIn(expiry_sentence, html_body)

    def test_password_reset_confirm_expired_token_fails(self):
        uid = self.build_reset_uid()
        token = self.build_reset_token()
        expired_time = default_token_generator._now() + timedelta(
            seconds=settings.PASSWORD_RESET_TIMEOUT + 1
        )

        with patch.object(default_token_generator, "_now", return_value=expired_time):
            response = self.client.post(
                reverse("auth-password-reset-confirm"),
                {
                    "uid": uid,
                    "token": token,
                    "new_password": "EvenStronger123!",
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["token"], ["This reset link has expired."])

    def test_password_reset_confirm_validation_endpoint_accepts_valid_link(self):
        uid = self.build_reset_uid()
        token = self.build_reset_token()

        response = self.client.get(reverse("password_reset_confirm", args=[uid, token]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "valid_link")
        self.assertEqual(response.data["uid"], uid)
        self.assertEqual(response.data["token"], token)

    def test_password_reset_confirm_validation_endpoint_rejects_invalid_link(self):
        uid = self.build_reset_uid()

        response = self.client.get(
            reverse("password_reset_confirm", args=[uid, "invalid-token"])
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid_link")

    def test_password_reset_confirm_validation_endpoint_rejects_expired_link(self):
        uid = self.build_reset_uid()
        token = self.build_reset_token()
        expired_time = default_token_generator._now() + timedelta(
            seconds=settings.PASSWORD_RESET_TIMEOUT + 1
        )

        with patch.object(default_token_generator, "_now", return_value=expired_time):
            response = self.client.get(reverse("password_reset_confirm", args=[uid, token]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "expired_link")

    def test_password_reset_request_is_throttled(self):
        responses = [
            self.client.post(
                reverse("auth-password-reset"),
                {"email": "alice@example.com"},
                format="json",
            )
            for _ in range(6)
        ]

        for response in responses[:5]:
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(responses[5].status_code, status.HTTP_429_TOO_MANY_REQUESTS)
