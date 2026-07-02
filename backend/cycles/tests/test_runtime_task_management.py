from datetime import date, timedelta

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from templates_mgmt.models import Template, TemplateTask, TemplateActivity
from cycles.models import CycleInstance, CycleTask, CycleActivity
from cycles.task_status_engine import mark_overdue_tasks


class RuntimeTaskManagementTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="test123"
        )
        self.client.force_authenticate(user=self.user)

        self.template = Template.objects.create(
            user=self.user,
            template_name="Onboarding Template",
            description="Testing"
        )

        self.task_a = TemplateTask.objects.create(
            template=self.template, task_name="A", day_offset=0, duration_days=2
        )
        self.task_b = TemplateTask.objects.create(
            template=self.template, task_name="B (optional)", day_offset=0, duration_days=1
        )
        self.activity_a = TemplateActivity.objects.create(
            template=self.template, activity_name="Orientation",
            start_offset_days=0, end_offset_days=1
        )

        self.cycle = CycleInstance.objects.create(
            user=self.user,
            template=self.template,
            cycle_name="June Cohort",
            start_date=date(2026, 7, 1)
        )

        self.cycle_task_a = CycleTask.objects.create(
            cycle=self.cycle, template_task=self.task_a, task_name="A",
            calculated_start_date=date(2026, 7, 1), calculated_end_date=date(2026, 7, 3),
            is_mandatory=True
        )
        self.cycle_task_b = CycleTask.objects.create(
            cycle=self.cycle, template_task=self.task_b, task_name="B (optional)",
            calculated_start_date=date(2026, 7, 1), calculated_end_date=date(2026, 7, 2),
            is_mandatory=False
        )
        self.cycle_activity = CycleActivity.objects.create(
            cycle=self.cycle, template_activity=self.activity_a, activity_name="Orientation",
            calculated_start_date=date(2026, 7, 1), calculated_end_date=date(2026, 7, 2)
        )

    # Valid and invalid status transitions

    def test_pending_to_in_progress_is_allowed(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "in_progress"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "in_progress")

    def test_pending_to_completed_is_rejected(self):
        # Must pass through in_progress first, no skipping straight to done.
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "completed"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "pending")

    def test_pending_to_skipped_is_allowed(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "skipped"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_completed_is_terminal(self):
        # A second pending mandatory task keeps the cycle running, so this
        # isolates the terminal-status check from cycle auto-completion
        # (that's covered separately below).
        CycleTask.objects.create(
            cycle=self.cycle, template_task=self.task_b, task_name="Keeps cycle running",
            calculated_start_date=date(2026, 7, 1), calculated_end_date=date(2026, 7, 2),
            is_mandatory=True
        )

        self.cycle_task_a.status = "in_progress"
        self.cycle_task_a.save(update_fields=["status"])
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        self.client.patch(url, {"status": "completed"})

        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.status, "running")

        response = self.client.patch(url, {"status": "pending"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_setting_overdue_directly_is_rejected(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "overdue"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_overdue_task_can_still_be_completed(self):
        self.cycle_task_a.status = "overdue"
        self.cycle_task_a.save(update_fields=["status"])
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "completed"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_setting_same_status_again_is_a_no_op(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "pending"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_available_statuses_reflects_current_state(self):
        url = reverse("cycle-tasks-available-statuses", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["current_status"], "pending")
        self.assertEqual(response.data["available_statuses"], ["in_progress", "skipped"])

    # Field locking, only status moves through this endpoint for tasks

    def test_task_name_and_other_fields_cannot_be_patched(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"task_name": "Renamed", "is_mandatory": False})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.task_name, "A")
        self.assertTrue(self.cycle_task_a.is_mandatory)

    # Activities: dates only, no status field exists on this model at all

    def test_activity_dates_can_be_patched_directly(self):
        url = reverse("cycle-activities-detail", args=[self.cycle_activity.cycle_activity_id])
        response = self.client.patch(url, {"calculated_end_date": "2026-07-05"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_activity.refresh_from_db()
        self.assertEqual(self.cycle_activity.calculated_end_date, date(2026, 7, 5))

    def test_activity_name_and_note_cannot_be_patched(self):
        url = reverse("cycle-activities-detail", args=[self.cycle_activity.cycle_activity_id])
        response = self.client.patch(url, {"activity_name": "Renamed", "note_text": "changed"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_activity.refresh_from_db()
        self.assertEqual(self.cycle_activity.activity_name, "Orientation")

    # Cycle auto-completion, mandatory tasks only, optional tasks don't block

    def test_cycle_stays_running_until_mandatory_task_completes(self):
        # B is optional, completing it alone must not complete the cycle,
        # A (mandatory) is still pending. Goes through the API so
        # perform_update -> maybe_complete_cycle actually runs.
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_b.cycle_task_id])
        self.client.patch(url, {"status": "in_progress"})
        response = self.client.patch(url, {"status": "completed"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.status, "running")

    def test_cycle_completes_once_mandatory_task_is_done_even_with_optional_pending(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        self.client.patch(url, {"status": "in_progress"})
        self.client.patch(url, {"status": "completed"})

        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.status, "completed")
        # B (optional) was never touched, mandatory-only is what mattered.
        self.cycle_task_b.refresh_from_db()
        self.assertEqual(self.cycle_task_b.status, "pending")

    def test_skipped_mandatory_task_also_counts_toward_completion(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "skipped"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.status, "completed")

    # Overdue background job

    def test_mark_overdue_tasks_flips_pending_tasks_past_their_end_date(self):
        self.cycle_task_a.calculated_end_date = date(2026, 7, 1)
        self.cycle_task_a.save(update_fields=["calculated_end_date"])

        count = mark_overdue_tasks(today=date(2026, 7, 2))

        self.assertEqual(count, 1)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "overdue")

    def test_mark_overdue_tasks_ignores_shut_down_cycles(self):
        self.cycle.status = "shut_down"
        self.cycle.save(update_fields=["status"])
        self.cycle_task_a.calculated_end_date = date(2026, 7, 1)
        self.cycle_task_a.save(update_fields=["calculated_end_date"])

        count = mark_overdue_tasks(today=date(2026, 7, 2))

        self.assertEqual(count, 0)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "pending")

    def test_mark_overdue_tasks_ignores_already_completed_tasks(self):
        self.cycle_task_a.status = "completed"
        self.cycle_task_a.calculated_end_date = date(2026, 7, 1)
        self.cycle_task_a.save(update_fields=["status", "calculated_end_date"])

        count = mark_overdue_tasks(today=date(2026, 7, 2))

        self.assertEqual(count, 0)

    # A completed or shut-down cycle is frozen entirely

    def test_status_update_blocked_on_shut_down_cycle(self):
        self.cycle.status = "shut_down"
        self.cycle.save(update_fields=["status"])

        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "in_progress"})
        self.assertEqual(response.status_code, 422)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "pending")

    def test_status_update_blocked_on_completed_cycle(self):
        self.cycle.status = "completed"
        self.cycle.save(update_fields=["status"])

        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "in_progress"})
        self.assertEqual(response.status_code, 422)

    def test_shift_blocked_on_shut_down_cycle(self):
        self.cycle.status = "shut_down"
        self.cycle.save(update_fields=["status"])

        url = reverse("cycle-tasks-shift", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.post(url, {"delay_days": 1, "scope": "single"})
        self.assertEqual(response.status_code, 422)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.calculated_start_date, date(2026, 7, 1))

    def test_shift_preview_blocked_on_shut_down_cycle(self):
        self.cycle.status = "shut_down"
        self.cycle.save(update_fields=["status"])

        url = reverse("cycle-tasks-shift-preview", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.post(url, {"delay_days": 1})
        self.assertEqual(response.status_code, 422)

    def test_activity_date_update_blocked_on_shut_down_cycle(self):
        self.cycle.status = "shut_down"
        self.cycle.save(update_fields=["status"])

        url = reverse("cycle-activities-detail", args=[self.cycle_activity.cycle_activity_id])
        response = self.client.patch(url, {"calculated_end_date": "2026-08-01"})
        self.assertEqual(response.status_code, 422)
        self.cycle_activity.refresh_from_db()
        self.assertEqual(self.cycle_activity.calculated_end_date, date(2026, 7, 2))

    def test_status_update_still_works_on_running_cycle(self):
        # Confirms the running case wasn't accidentally broken by the guard.
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "in_progress"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)