from datetime import date

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from templates_mgmt.models import Template, TemplateTask
from cycles.models import CycleInstance, CycleTask


class UndoTransitionTests(APITestCase):
    """
    completed/skipped/in_progress -> pending. Added to support the
    common "misclick" / "changed my mind" case. Deliberately narrow:
    pending is the only allowed destination from a terminal state,
    not a general reopening of every transition.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="test123"
        )
        self.client.force_authenticate(user=self.user)

        self.template = Template.objects.create(
            user=self.user,
            template_name="Undo Test Template",
            description="Testing"
        )

        self.task_a = TemplateTask.objects.create(
            template=self.template, task_name="A", day_offset=0, duration_days=2
        )

        self.cycle = CycleInstance.objects.create(
            user=self.user,
            template=self.template,
            cycle_name="Undo Test Cycle",
            start_date=date(2026, 7, 1)
        )

        self.cycle_task_a = CycleTask.objects.create(
            cycle=self.cycle, template_task=self.task_a, task_name="A",
            calculated_start_date=date(2026, 7, 1), calculated_end_date=date(2026, 7, 3),
            is_mandatory=True
        )

    def _patch_status(self, cycle_task_id, new_status):
        url = reverse("cycle-tasks-detail", args=[cycle_task_id])
        return self.client.patch(url, {"status": new_status})

    def test_completed_can_be_undone_to_pending(self):
        self.cycle_task_a.status = "completed"
        self.cycle_task_a.save()

        response = self._patch_status(self.cycle_task_a.cycle_task_id, "pending")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "pending")

    def test_skipped_can_be_undone_to_pending(self):
        self.cycle_task_a.status = "skipped"
        self.cycle_task_a.save()

        response = self._patch_status(self.cycle_task_a.cycle_task_id, "pending")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "pending")

    def test_in_progress_can_be_undone_to_pending(self):
        self.cycle_task_a.status = "in_progress"
        self.cycle_task_a.save()

        response = self._patch_status(self.cycle_task_a.cycle_task_id, "pending")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "pending")

    def test_completed_cannot_jump_directly_to_in_progress(self):
        self.cycle_task_a.status = "completed"
        self.cycle_task_a.save()

        response = self._patch_status(self.cycle_task_a.cycle_task_id, "in_progress")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "completed")

    def test_completed_cannot_jump_directly_to_skipped(self):
        self.cycle_task_a.status = "completed"
        self.cycle_task_a.save()

        response = self._patch_status(self.cycle_task_a.cycle_task_id, "skipped")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_skipped_cannot_jump_directly_to_completed(self):
        self.cycle_task_a.status = "skipped"
        self.cycle_task_a.save()

        response = self._patch_status(self.cycle_task_a.cycle_task_id, "completed")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_undo_still_blocked_once_cycle_is_no_longer_running(self):
        """
        Once the user explicitly confirms cycle completion, the cycle
        is frozen and its completed task can no longer be undone.
        """
        complete_response = self._patch_status(self.cycle_task_a.cycle_task_id, "in_progress")
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        complete_response = self._patch_status(self.cycle_task_a.cycle_task_id, "completed")
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)

        cycle_response = self.client.post(reverse("cycles-complete", args=[self.cycle.cycle_id]))
        self.assertEqual(cycle_response.status_code, status.HTTP_200_OK)

        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.status, "completed")

        undo_response = self._patch_status(self.cycle_task_a.cycle_task_id, "pending")

        self.assertNotEqual(undo_response.status_code, status.HTTP_200_OK)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "completed")
