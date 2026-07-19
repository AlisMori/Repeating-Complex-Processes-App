"""
/backend/tests/test_error_handling.py

Covers:
  - NFR-4.1: invalid field input returns a descriptive 400, not a server crash
  - Unauthorized / non-owned access returns 403 (or 404, where the object is
    outside the caller's queryset entirely — see note below) across every
    app's endpoints, not only blocked in the UI layer
  - NFR-4.3: an unhandled exception returns a generic message to the client,
    while full detail is still logged server-side

"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from cycles.models import CycleActivity, CycleInstance, CycleTask
from templates_mgmt.models import (
    Tag,
    Template,
    TemplateActivity,
    TemplateCategory,
    TemplateTask,
    UserTemplate,
)

User = get_user_model()


class BaseAPITestCase(APITestCase):
    """Common two-user setup so every "non-owned access" test has a
    genuine second owner to try to reach across, not just an
    anonymous caller.
    """

    def setUp(self):
        # By default DRF's APIClient re-raises server-side exceptions
        # instead of returning the 500 response the client would actually
        # see — useful for debugging, but it defeats the NFR-4.3 tests
        # below, which need to inspect the real client-facing response.
        self.client = self.client_class(raise_request_exception=False)
        self.owner = User.objects.create_user(
            username="owner_user", email="owner@example.com", password="Str0ngPassw0rd!"
        )
        self.other_user = User.objects.create_user(
            username="other_user", email="other@example.com", password="Str0ngPassw0rd!"
        )

    def auth_as_owner(self):
        self.client.force_authenticate(user=self.owner)

    def auth_as_other(self):
        self.client.force_authenticate(user=self.other_user)

    def auth_as_anonymous(self):
        self.client.force_authenticate(user=None)

    # ---- shared factories -------------------------------------------------

    def make_template(self, user, **kwargs):
        defaults = {"template_name": "Onboarding Template", "is_public": False}
        defaults.update(kwargs)
        return Template.objects.create(user=user, **defaults)

    def make_template_activity(self, template, **kwargs):
        defaults = {
            "activity_name": "Phase 1",
            "start_offset_days": 0,
            "end_offset_days": 10,
        }
        defaults.update(kwargs)
        return TemplateActivity.objects.create(template=template, **defaults)

    def make_template_task(self, template, **kwargs):
        defaults = {"task_name": "Collect documents", "day_offset": 1}
        defaults.update(kwargs)
        return TemplateTask.objects.create(template=template, **defaults)

    def make_cycle(self, user, template=None, **kwargs):
        defaults = {
            "cycle_name": "Q1 Onboarding",
            "start_date": date.today(),
            "status": "running",
        }
        defaults.update(kwargs)
        return CycleInstance.objects.create(user=user, template=template, **defaults)

    def make_cycle_task(self, cycle, **kwargs):
        today = date.today()
        defaults = {
            "task_name": "Sign contract",
            "calculated_start_date": today,
            "calculated_end_date": today + timedelta(days=2),
            "status": "pending",
        }
        defaults.update(kwargs)
        return CycleTask.objects.create(cycle=cycle, **defaults)

    def make_cycle_activity(self, cycle, **kwargs):
        today = date.today()
        defaults = {
            "activity_name": "Phase 1",
            "calculated_start_date": today,
            "calculated_end_date": today + timedelta(days=10),
        }
        defaults.update(kwargs)
        return CycleActivity.objects.create(cycle=cycle, **defaults)


# ---------------------------------------------------------------------------
# accounts app
# ---------------------------------------------------------------------------

class AccountsErrorHandlingTests(BaseAPITestCase):
    """RegisterView / LoginView / LogoutView / MeView / PasswordResetView /
    PasswordResetConfirmView.
    """

    def test_register_with_missing_fields_returns_400(self):
        # NFR-4.1
        url = reverse("auth-register")
        response = self.client.post(url, {"username": "", "email": "", "password": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)
        self.assertIn("email", response.data)
        self.assertIn("password", response.data)

    def test_register_with_duplicate_username_returns_400(self):
        url = reverse("auth-register")
        response = self.client.post(
            url,
            {
                "username": self.owner.username,
                "email": "someoneelse@example.com",
                "password": "AnotherStr0ngPass!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    def test_register_with_weak_password_returns_400(self):
        # RegisterSerializer.password runs Django's validate_password
        # validators, so a common/too-short password is rejected
        # descriptively rather than crashing.
        url = reverse("auth-register")
        response = self.client.post(
            url,
            {
                "username": "newperson",
                "email": "newperson@example.com",
                "password": "12345",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_login_with_invalid_credentials_returns_401_not_500(self):
        # LoginSerializer raises AuthenticationFailed (401), not a plain 400.
        url = reverse("auth-login")
        response = self.client.post(
            url, {"username": "nonexistent", "password": "wrongpass"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_with_malformed_refresh_token_returns_400(self):
        url = reverse("auth-logout")
        self.auth_as_owner()
        response = self.client.post(url, {"refresh": "not-a-real-jwt"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("refresh", response.data)

    def test_logout_requires_authentication(self):
        url = reverse("auth-logout")
        self.auth_as_anonymous()
        response = self.client.post(url, {"refresh": "irrelevant"})
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_me_requires_authentication(self):
        url = reverse("auth-me")
        self.auth_as_anonymous()
        response = self.client.get(url)
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_me_patch_with_invalid_field_value_returns_400(self):
        url = reverse("auth-me")
        self.auth_as_owner()
        response = self.client.patch(url, {"notification_opt_in": "not-a-boolean"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_request_with_invalid_email_returns_400(self):
        url = reverse("auth-password-reset")
        response = self.client.post(url, {"email": "not-an-email"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_password_reset_confirm_with_invalid_uid_returns_400(self):
        url = reverse("auth-password-reset-confirm")
        response = self.client.post(
            url,
            {
                "uid": "invalid-uid",
                "token": "invalid-token",
                "new_password": "irrelevantButLong1!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("uid", response.data)

    def test_token_refresh_with_garbage_token_returns_401_not_500(self):
        # A malformed/undecodable token blows up inside
        # RefreshToken(attrs["refresh"]) before SlidingTokenRefreshSerializer
        # even reaches its own session lookups — simplejwt's TokenError
        # there is what DRF turns into a response. This must never surface
        # as a raw 500; confirming it stays a clean, descriptive 401.
        url = reverse("auth-token-refresh")
        response = self.client.post(url, {"refresh": "garbage.token.value"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_with_revoked_session_returns_401_session_inactive(self):
        # SessionInactive — confirmed 401 with a structured
        # {"code": "session_inactive", "detail": ...} body, raised when
        # last_activity_at is older than the inactivity timeout (30 min
        # default). Session gets revoked and the old refresh blacklisted
        # as a side effect, not just rejected.
        from datetime import timedelta as _timedelta

        from accounts.models import AuthSession
        from django.utils import timezone
        from rest_framework_simplejwt.tokens import RefreshToken

        self.auth_as_owner()
        refresh = RefreshToken.for_user(self.owner)
        stale_activity = timezone.now() - _timedelta(minutes=45)
        session = AuthSession.objects.create(
            user=self.owner,
            current_refresh_jti=refresh["jti"],
            last_activity_at=stale_activity,
        )
        refresh["sid"] = str(session.session_id)

        url = reverse("auth-token-refresh")
        response = self.client.post(url, {"refresh": str(refresh)})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data.get("code"), "session_inactive")

        session.refresh_from_db()
        self.assertIsNotNone(session.revoked_at)

    @patch("accounts.views.RegisterSerializer.save")
    def test_unhandled_exception_on_register_returns_generic_message(self, mock_save):
        # NFR-4.3
        mock_save.side_effect = RuntimeError("unexpected database failure")
        url = reverse("auth-register")

        with self.assertLogs("django.request", level="ERROR") as captured_logs:
            response = self.client.post(
                url,
                {
                    "username": "brandnewuser",
                    "email": "brandnewuser@example.com",
                    "password": "Str0ngPassw0rd!",
                },
            )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        # Unrecognized exceptions (plain RuntimeError, not an APIException)
        # aren't converted into a DRF Response by DRF's own exception
        # handler — they fall through to Django's own 500 handling, so
        # this is a bare HttpResponseServerError with no .data attribute.
        # Check the raw body bytes instead.
        body = response.content.decode(errors="replace")
        self.assertNotIn("unexpected database failure", body)
        self.assertTrue(
            any("unexpected database failure" in msg for msg in captured_logs.output)
        )


# ---------------------------------------------------------------------------
# dashboard app
# ---------------------------------------------------------------------------

class DashboardErrorHandlingTests(BaseAPITestCase):
    """DashboardSummaryView — read-only aggregation over cycles.models."""

    def test_dashboard_requires_authentication(self):
        url = reverse("dashboard-summary")
        self.auth_as_anonymous()
        response = self.client.get(url)
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_dashboard_never_leaks_another_user_s_running_cycle(self):
        # FR-12.2's own boundary: another user's running cycle must
        # never appear in this user's aggregation payload.
        template = self.make_template(self.other_user)
        other_cycle = self.make_cycle(self.other_user, template=template)

        self.auth_as_owner()
        url = reverse("dashboard-summary")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = [c["cycle_id"] for c in response.data["active_cycles"]]
        self.assertNotIn(other_cycle.cycle_id, returned_ids)

    @patch("dashboard.views.DashboardSummaryView._serialize_cycle")
    def test_unhandled_exception_in_aggregation_returns_generic_message(
        self, mock_serialize
    ):
        # NFR-4.3
        template = self.make_template(self.owner)
        self.make_cycle(self.owner, template=template)
        mock_serialize.side_effect = ZeroDivisionError("division by zero")

        self.auth_as_owner()
        url = reverse("dashboard-summary")

        with self.assertLogs("django.request", level="ERROR"):
            response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertNotIn("division by zero", response.content.decode(errors="replace"))


# ---------------------------------------------------------------------------
# cycles app
# ---------------------------------------------------------------------------

class CyclesErrorHandlingTests(BaseAPITestCase):
    """CycleInstanceViewSet / CycleTaskViewSet / CycleActivityViewSet /
    TaskDependencyViewSet.

    owned_cycles_q is strictly user=request.user with no shared-access
    tier, so a non-owner is outside the queryset entirely -> 404, not
    403, on every cycle-scoped detail route.
    """

    def test_create_cycle_missing_start_date_returns_400(self):
        template = self.make_template(self.owner)
        self.auth_as_owner()
        url = reverse("cycles-list")
        response = self.client.post(
            url, {"template": template.pk, "cycle_name": "No date cycle"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_date", response.data)

    def test_create_cycle_from_inaccessible_template_returns_403(self):
        # validate_template on CycleInstanceSerializer -> PermissionDenied,
        # a 403 raised from inside the serializer, not the viewset's
        # permission_classes.
        private_template = self.make_template(self.other_user, is_public=False)
        self.auth_as_owner()
        url = reverse("cycles-list")
        response = self.client.post(
            url,
            {
                "template": private_template.pk,
                "cycle_name": "Borrowed template cycle",
                "start_date": str(date.today()),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieving_another_user_s_cycle_returns_404(self):
        template = self.make_template(self.other_user)
        other_cycle = self.make_cycle(self.other_user, template=template)
        self.auth_as_owner()
        url = reverse("cycles-detail", args=[other_cycle.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_updating_another_user_s_cycle_task_returns_404(self):
        template = self.make_template(self.other_user)
        other_cycle = self.make_cycle(self.other_user, template=template)
        other_task = self.make_cycle_task(other_cycle)

        self.auth_as_owner()
        url = reverse("cycle-tasks-detail", args=[other_task.pk])
        response = self.client.patch(url, {"status": "completed"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_status_transition_returns_400(self):
        template = self.make_template(self.owner)
        cycle = self.make_cycle(self.owner, template=template)
        task = self.make_cycle_task(cycle, status="pending")

        self.auth_as_owner()
        url = reverse("cycle-tasks-detail", args=[task.pk])
        response = self.client.patch(url, {"status": "not_a_real_status"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_changing_task_status_in_frozen_cycle_returns_422(self):
        # CycleFrozen -> 422, a descriptive, deliberate rejection, not a
        # crash and not a silent no-op.
        template = self.make_template(self.owner)
        cycle = self.make_cycle(self.owner, template=template, status="shut_down")
        task = self.make_cycle_task(cycle, status="pending")

        self.auth_as_owner()
        url = reverse("cycle-tasks-detail", args=[task.pk])
        response = self.client.patch(url, {"status": "completed"})
        self.assertEqual(response.status_code, 422)

    def test_completing_task_with_unresolved_prerequisites_returns_409(self):
        # find_unresolved_prerequisites reads the dependency graph at the
        # TEMPLATE_TASK level (TaskDependency: task depends_on
        # depends_on_task), then maps back to each CycleTask via its
        # template_task FK — so both cycle tasks need real template_task
        # links for the engine to see the relationship at all.
        # The dependent task starts "in_progress": ALLOWED_TRANSITIONS only
        # permits completed from in_progress/overdue, never directly from
        # pending, so the transition check itself must pass before the
        # unresolved-prerequisites check is ever reached.
        from cycles.models import TaskDependency

        template = self.make_template(self.owner)
        prereq_template_task = self.make_template_task(template, task_name="Prereq (template)")
        dependent_template_task = self.make_template_task(
            template, task_name="Dependent (template)"
        )
        TaskDependency.objects.create(
            task=dependent_template_task, depends_on_task=prereq_template_task
        )

        cycle = self.make_cycle(self.owner, template=template)
        self.make_cycle_task(
            cycle,
            task_name="Prereq",
            status="pending",
            template_task=prereq_template_task,
        )
        dependent = self.make_cycle_task(
            cycle,
            task_name="Dependent",
            status="in_progress",
            template_task=dependent_template_task,
        )

        self.auth_as_owner()
        url = reverse("cycle-tasks-detail", args=[dependent.pk])
        response = self.client.patch(url, {"status": "completed"})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get("error"), "prerequisites_unresolved")
        self.assertIn("unresolved_prerequisites", response.data)

    def test_resolving_unresolved_prerequisite_with_invalid_status_returns_400(self):
        # Resolution isn't a separate endpoint — it's the SAME PATCH to
        # cycle-tasks-detail, with a resolve_prerequisites dict
        # ({cycle_task_id: "completed"/"skipped"}) supplied alongside
        # status="completed". apply_prerequisite_resolution only accepts
        # "completed"/"skipped" for the prerequisite; anything else must be
        # rejected as a descriptive 400, not silently applied or a crash.
        from cycles.models import TaskDependency

        template = self.make_template(self.owner)
        prereq_template_task = self.make_template_task(template, task_name="Prereq (template)")
        dependent_template_task = self.make_template_task(
            template, task_name="Dependent (template)"
        )
        TaskDependency.objects.create(
            task=dependent_template_task, depends_on_task=prereq_template_task
        )

        cycle = self.make_cycle(self.owner, template=template)
        prereq_task = self.make_cycle_task(
            cycle,
            task_name="Prereq",
            status="pending",
            template_task=prereq_template_task,
        )
        dependent = self.make_cycle_task(
            cycle,
            task_name="Dependent",
            status="in_progress",
            template_task=dependent_template_task,
        )

        self.auth_as_owner()
        url = reverse("cycle-tasks-detail", args=[dependent.pk])
        response = self.client.patch(
            url,
            {
                "status": "completed",
                "resolve_prerequisites": {str(prereq_task.cycle_task_id): "in_progress"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("resolve_prerequisites", response.data)

    def test_shifting_a_fixed_date_task_without_override_returns_409(self):
        # apply_task_shift -> DependencyConflict("fixed_task_locked") -> 409,
        # a deliberate, descriptive rejection rather than silently moving
        # (or crashing on) a date the user marked as fixed.
        template = self.make_template(self.owner)
        template_task = self.make_template_task(template)
        cycle = self.make_cycle(self.owner, template=template)
        task = self.make_cycle_task(
            cycle, template_task=template_task, is_fixed_date=True
        )

        self.auth_as_owner()
        # TODO: confirm exact shift endpoint name/path once reviewed —
        # per the Design Doc reference (API-02) this is the "shift"
        # action on CycleTaskViewSet.
        url = reverse("cycle-tasks-shift", args=[task.pk])
        response = self.client.post(url, {"delay_days": 2, "scope": "single"})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get("error"), "fixed_task_locked")

    def test_shifting_a_cycle_task_in_a_non_running_cycle_returns_422(self):
        # assert_cycle_is_running -> CycleNotRunning -> 422, applied
        # consistently to every edit surface on a frozen cycle, per its
        # own docstring — not just direct status changes.
        template = self.make_template(self.owner)
        template_task = self.make_template_task(template)
        cycle = self.make_cycle(self.owner, template=template, status="completed")
        task = self.make_cycle_task(cycle, template_task=template_task)

        self.auth_as_owner()
        url = reverse("cycle-tasks-shift", args=[task.pk])
        response = self.client.post(url, {"delay_days": 1, "scope": "single"})
        self.assertEqual(response.status_code, 422)

    def test_note_endpoint_rejects_blank_note_with_400(self):
        template = self.make_template(self.owner)
        cycle = self.make_cycle(self.owner, template=template)
        task = self.make_cycle_task(cycle)

        self.auth_as_owner()
        url = reverse("cycle-tasks-note", args=[task.pk])
        response = self.client.post(url, {"note_text": "   "})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("note_text", response.data)

    def test_activity_resize_that_orphans_a_task_returns_400(self):
        template = self.make_template(self.owner)
        cycle = self.make_cycle(self.owner, template=template)
        today = date.today()
        activity = self.make_cycle_activity(
            cycle,
            calculated_start_date=today,
            calculated_end_date=today + timedelta(days=10),
        )
        self.make_cycle_task(
            cycle,
            cycle_activity=activity,
            calculated_start_date=today + timedelta(days=8),
            calculated_end_date=today + timedelta(days=9),
        )

        self.auth_as_owner()
        url = reverse("cycle-activities-detail", args=[activity.pk])
        # Shrinking the activity so the task above no longer fits inside it.
        response = self.client.patch(
            url,
            {
                "calculated_start_date": str(today),
                "calculated_end_date": str(today + timedelta(days=3)),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_creating_dependency_across_different_templates_returns_400(self):
        template_a = self.make_template(self.owner, template_name="Template A")
        template_b = self.make_template(self.owner, template_name="Template B")
        task_a = self.make_template_task(template_a)
        task_b = self.make_template_task(template_b)

        self.auth_as_owner()
        url = reverse("task-dependencies-list")
        response = self.client.post(
            url, {"task": task_b.pk, "depends_on_task": task_a.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("depends_on_task", response.data)

    def test_creating_dependency_on_template_without_edit_rights_returns_403(self):
        # Same-template pair, but the caller only has read (public here),
        # not edit rights -> serializer-level PermissionDenied.
        template = self.make_template(self.other_user, is_public=True)
        task_a = self.make_template_task(template, task_name="A")
        task_b = self.make_template_task(template, task_name="B")

        self.auth_as_owner()  # can see it (is_public), can't edit it
        url = reverse("task-dependencies-list")
        response = self.client.post(
            url, {"task": task_b.pk, "depends_on_task": task_a.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("cycles.views.generate_cycle_runtime_records")
    def test_unhandled_exception_on_cycle_create_returns_generic_message(
        self, mock_generate
    ):
        # NFR-4.3
        mock_generate.side_effect = RuntimeError("template graph corrupted")
        template = self.make_template(self.owner)

        self.auth_as_owner()
        url = reverse("cycles-list")

        with self.assertLogs("django.request", level="ERROR"):
            response = self.client.post(
                url,
                {
                    "template": template.pk,
                    "cycle_name": "Boom Cycle",
                    "start_date": str(date.today()),
                },
            )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertNotIn("template graph corrupted", response.content.decode(errors="replace"))


# ---------------------------------------------------------------------------
# templates_mgmt app
# ---------------------------------------------------------------------------

class TemplatesMgmtErrorHandlingTests(BaseAPITestCase):
    """TemplateViewSet / TemplateTaskViewSet / TemplateActivityViewSet /
    TagViewSet / TemplateCategoryViewSet.

    Read access (accessible_templates_q) includes owner, public, and any
    shared/saved UserTemplate row -> GET on those is 200. Edit access
    (editable_templates_q / user_can_edit_template) only includes owner
    or an "owner"-type UserTemplate row -> a shared/saved (read-only)
    user gets 403 on write actions; a total stranger with neither a
    UserTemplate row nor is_public=True gets 404 (outside the queryset).
    """

    def test_create_template_with_blank_name_returns_400(self):
        self.auth_as_owner()
        url = reverse("templates-list")
        response = self.client.post(url, {"template_name": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("template_name", response.data)

    def test_updating_a_stranger_s_private_template_returns_404(self):
        private_template = self.make_template(self.other_user, is_public=False)
        self.auth_as_owner()  # no UserTemplate row, not public
        url = reverse("templates-detail", args=[private_template.pk])
        response = self.client.patch(url, {"template_name": "hijacked"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_updating_a_shared_read_only_template_returns_403(self):
        shared_template = self.make_template(self.other_user, is_public=False)
        UserTemplate.objects.create(
            user=self.owner, template=shared_template, access_type="shared"
        )
        self.auth_as_owner()  # can see it, can't edit it
        url = reverse("templates-detail", args=[shared_template.pk])
        response = self.client.patch(url, {"template_name": "hijacked"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_deleting_a_public_template_without_edit_rights_returns_403(self):
        public_template = self.make_template(self.other_user, is_public=True)
        self.auth_as_owner()
        url = reverse("templates-detail", args=[public_template.pk])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_cycle_from_template_with_missing_start_date_returns_400(self):
        template = self.make_template(self.owner)
        self.auth_as_owner()
        url = reverse("templates-create-cycle", args=[template.pk])
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_date", response.data)

    def test_create_cycle_from_template_with_malformed_date_returns_400(self):
        template = self.make_template(self.owner)
        self.auth_as_owner()
        url = reverse("templates-create-cycle", args=[template.pk])
        response = self.client.post(url, {"start_date": "not-a-date"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_date", response.data)

    def test_download_with_unsupported_file_format_returns_400(self):
        template = self.make_template(self.owner)
        self.auth_as_owner()
        url = reverse("templates-download", args=[template.pk])
        response = self.client.get(url, {"file_format": "exe"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file_format", response.data)

    def test_download_of_inaccessible_template_returns_404(self):
        private_template = self.make_template(self.other_user, is_public=False)
        self.auth_as_owner()
        url = reverse("templates-download", args=[private_template.pk])
        response = self.client.get(url, {"file_format": "json"})
        # get_object() (queryset-scoped) 404s before download()'s own
        # user_can_access_template check ever runs.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_share_with_missing_username_returns_400(self):
        template = self.make_template(self.owner)
        self.auth_as_owner()
        url = reverse("templates-share", args=[template.pk])
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    def test_share_with_nonexistent_username_returns_404_not_500(self):
        template = self.make_template(self.owner)
        self.auth_as_owner()
        url = reverse("templates-share", args=[template.pk])
        response = self.client.post(url, {"username": "ghost_user_xyz"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_template_task_outside_activity_offset_range_returns_400(self):
        template = self.make_template(self.owner)
        activity = self.make_template_activity(
            template, start_offset_days=0, end_offset_days=5
        )
        self.auth_as_owner()
        url = reverse("template-tasks-list")
        response = self.client.post(
            url,
            {
                "template": template.pk,
                "template_activity": activity.pk,
                "task_name": "Out of range task",
                "day_offset": 10,
                "duration_days": 1,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("template_activity", response.data)

    def test_create_template_task_on_uneditable_template_returns_403(self):
        private_template = self.make_template(self.other_user, is_public=False)
        self.auth_as_owner()
        url = reverse("template-tasks-list")
        response = self.client.post(
            url,
            {
                "template": private_template.pk,
                "task_name": "Sneaky task",
                "day_offset": 1,
            },
        )
        # validate_template on TemplateTaskSerializer raises
        # PermissionDenied directly (403) at field-validation time, before
        # any get_object() call, so it's 403 even though this same
        # template would 404 on a detail route.
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_activity_resize_below_its_own_tasks_returns_400(self):
        template = self.make_template(self.owner)
        activity = self.make_template_activity(
            template, start_offset_days=0, end_offset_days=10
        )
        self.make_template_task(
            template, template_activity=activity, day_offset=8, duration_days=1
        )
        self.auth_as_owner()
        url = reverse("template-activities-detail", args=[activity.pk])
        response = self.client.patch(url, {"start_offset_days": 0, "end_offset_days": 3})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_creating_duplicate_category_name_returns_400(self):
        TemplateCategory.objects.create(user=self.owner, category_name="Academic")
        self.auth_as_owner()
        url = reverse("template-categories-list")
        response = self.client.post(url, {"category_name": "academic"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("category_name", response.data)

    def test_deleting_category_still_assigned_returns_400(self):
        category = TemplateCategory.objects.create(user=self.owner, category_name="Academic")
        self.make_template(self.owner, category=category)
        self.auth_as_owner()
        url = reverse("template-categories-detail", args=[category.pk])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deleting_another_user_s_category_returns_404(self):
        # TemplateCategoryViewSet.get_queryset scopes strictly to
        # user=request.user, no shared tier, so cross-user is 404.
        category = TemplateCategory.objects.create(
            user=self.other_user, category_name="Ops"
        )
        self.auth_as_owner()
        url = reverse("template-categories-detail", args=[category.pk])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_creating_duplicate_tag_name_returns_400(self):
        Tag.objects.create(user=self.owner, tag_name="Urgent")
        self.auth_as_owner()
        url = reverse("tags-list")
        response = self.client.post(url, {"tag_name": "urgent"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tag_name", response.data)

    def test_deleting_tag_still_in_use_returns_400(self):
        template = self.make_template(self.owner)
        task = self.make_template_task(template)
        tag = Tag.objects.create(user=self.owner, tag_name="Urgent")
        from templates_mgmt.models import TemplateTaskTag

        TemplateTaskTag.objects.create(template_task=task, tag=tag)

        self.auth_as_owner()
        url = reverse("tags-detail", args=[tag.pk])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deleting_another_user_s_tag_returns_404(self):
        tag = Tag.objects.create(user=self.other_user, tag_name="Ops")
        self.auth_as_owner()
        url = reverse("tags-detail", args=[tag.pk])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("templates_mgmt.views.deep_copy_template_contents")
    def test_unhandled_exception_on_share_returns_generic_message(self, mock_deep_copy):
        # NFR-4.3
        mock_deep_copy.side_effect = RuntimeError("copy engine failure")
        template = self.make_template(self.owner)

        self.auth_as_owner()
        url = reverse("templates-share", args=[template.pk])

        with self.assertLogs("django.request", level="ERROR"):
            response = self.client.post(url, {"username": self.other_user.username})

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertNotIn("copy engine failure", response.content.decode(errors="replace"))