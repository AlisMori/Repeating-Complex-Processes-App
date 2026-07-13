from datetime import date

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from templates_mgmt.models import Template, TemplateTask, TemplateActivity
from cycles.models import CycleInstance, CycleTask, CycleActivity


class NotesManagementTests(APITestCase):
    """POST/DELETE .../note/ on both CycleTask and CycleActivity.
    note_text is deliberately locked out of the generic PATCH (see
    CycleTaskSerializer.update / CycleActivitySerializer.update), this
    action is the only way to touch it.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="noteuser", email="note@test.com", password="test123"
        )
        self.client.force_authenticate(user=self.user)

        self.template = Template.objects.create(
            user=self.user, template_name="Note Template", description="d"
        )
        self.task = TemplateTask.objects.create(
            template=self.template, task_name="Task", day_offset=0, duration_days=2
        )
        self.activity = TemplateActivity.objects.create(
            template=self.template, activity_name="Activity", start_offset_days=0, end_offset_days=3
        )
        self.cycle = CycleInstance.objects.create(
            user=self.user, template=self.template, cycle_name="Cycle",
            start_date=date(2026, 7, 1)
        )
        self.cycle_task = CycleTask.objects.create(
            cycle=self.cycle, template_task=self.task, task_name="Task",
            calculated_start_date=date(2026, 7, 1), calculated_end_date=date(2026, 7, 3)
        )
        self.cycle_activity = CycleActivity.objects.create(
            cycle=self.cycle, template_activity=self.activity, activity_name="Activity",
            calculated_start_date=date(2026, 7, 1), calculated_end_date=date(2026, 7, 4)
        )

    def test_add_note_to_task(self):
        url = reverse("cycle-tasks-note", args=[self.cycle_task.cycle_task_id])
        response = self.client.post(url, {"note_text": "Call the vendor first"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_task.refresh_from_db()
        self.assertEqual(self.cycle_task.note_text, "Call the vendor first")

    def test_update_existing_note_on_task(self):
        self.cycle_task.note_text = "Old note"
        self.cycle_task.save(update_fields=["note_text"])

        url = reverse("cycle-tasks-note", args=[self.cycle_task.cycle_task_id])
        response = self.client.post(url, {"note_text": "New note"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_task.refresh_from_db()
        self.assertEqual(self.cycle_task.note_text, "New note")

    def test_delete_note_from_task(self):
        self.cycle_task.note_text = "Something"
        self.cycle_task.save(update_fields=["note_text"])

        url = reverse("cycle-tasks-note", args=[self.cycle_task.cycle_task_id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_task.refresh_from_db()
        self.assertIsNone(self.cycle_task.note_text)

    def test_add_note_with_blank_text_is_rejected(self):
        url = reverse("cycle-tasks-note", args=[self.cycle_task.cycle_task_id])
        response = self.client.post(url, {"note_text": "   "}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_note_with_missing_text_is_rejected(self):
        url = reverse("cycle-tasks-note", args=[self.cycle_task.cycle_task_id])
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_note_edit_blocked_on_frozen_cycle(self):
        self.cycle.status = "shut_down"
        self.cycle.save(update_fields=["status"])

        url = reverse("cycle-tasks-note", args=[self.cycle_task.cycle_task_id])
        response = self.client.post(url, {"note_text": "Too late"}, format="json")
        self.assertEqual(response.status_code, 422)
        self.cycle_task.refresh_from_db()
        self.assertIsNone(self.cycle_task.note_text)

    def test_note_still_locked_out_of_generic_patch(self):
        # Guard against a regression, note_text must stay protected on
        # the normal PATCH endpoint even with the note action existing.
        url = reverse("cycle-tasks-detail", args=[self.cycle_task.cycle_task_id])
        response = self.client.patch(url, {"note_text": "Sneaky"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_task.refresh_from_db()
        self.assertIsNone(self.cycle_task.note_text)

    def test_add_note_to_activity(self):
        url = reverse("cycle-activities-note", args=[self.cycle_activity.cycle_activity_id])
        response = self.client.post(url, {"note_text": "Room booked"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_activity.refresh_from_db()
        self.assertEqual(self.cycle_activity.note_text, "Room booked")

    def test_delete_note_from_activity(self):
        self.cycle_activity.note_text = "Something"
        self.cycle_activity.save(update_fields=["note_text"])

        url = reverse("cycle-activities-note", args=[self.cycle_activity.cycle_activity_id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_activity.refresh_from_db()
        self.assertIsNone(self.cycle_activity.note_text)

    def test_activity_note_edit_blocked_on_frozen_cycle(self):
        self.cycle.status = "completed"
        self.cycle.save(update_fields=["status"])

        url = reverse("cycle-activities-note", args=[self.cycle_activity.cycle_activity_id])
        response = self.client.post(url, {"note_text": "Too late"}, format="json")
        self.assertEqual(response.status_code, 422)