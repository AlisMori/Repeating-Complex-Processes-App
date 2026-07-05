from datetime import date

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from templates_mgmt.models import Template, TemplateActivity, TemplateTask
from cycles.models import CycleActivity, CycleInstance, CycleTask


class CycleInstanceEngineTests(APITestCase):

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

        self.task = TemplateTask.objects.create(
            template=self.template,
            task_name="Sign contract",
            day_offset=0,
            duration_days=2,
            is_mandatory=True,
            is_fixed_date=False,
            reminder_lead_days=[1],
            note_text="Send to legal for review first"
        )

        self.optional_task = TemplateTask.objects.create(
            template=self.template,
            task_name="Send welcome kit",
            day_offset=3,
            duration_days=None,
            is_mandatory=False,
            is_fixed_date=True,
            reminder_lead_days=[],
            note_text=None
        )

        self.activity = TemplateActivity.objects.create(
            template=self.template,
            activity_name="Orientation week",
            start_offset_days=0,
            end_offset_days=5,
            note_text="Runs alongside onboarding tasks"
        )

    def test_create_cycle_from_template_produces_running_cycle(self):
        url = reverse("cycles-list")

        data = {
            "template": self.template.template_id,
            "cycle_name": "June Cohort",
            "start_date": "2026-07-01"
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CycleInstance.objects.count(), 1)

        cycle = CycleInstance.objects.first()
        self.assertEqual(cycle.status, "running")
        self.assertEqual(cycle.user, self.user)

    def test_cycle_creation_generates_runtime_task_records(self):
        url = reverse("cycles-list")

        data = {
            "template": self.template.template_id,
            "cycle_name": "June Cohort",
            "start_date": "2026-07-01"
        }

        self.client.post(url, data)

        cycle = CycleInstance.objects.first()

        self.assertEqual(CycleTask.objects.filter(cycle=cycle).count(), 2)
        self.assertTrue(
            CycleTask.objects.filter(cycle=cycle, task_name="Sign contract").exists()
        )
        self.assertTrue(
            CycleTask.objects.filter(cycle=cycle, task_name="Send welcome kit").exists()
        )

    def test_cycle_creation_generates_runtime_activity_records(self):
        url = reverse("cycles-list")

        data = {
            "template": self.template.template_id,
            "cycle_name": "June Cohort",
            "start_date": "2026-07-01"
        }

        self.client.post(url, data)

        cycle = CycleInstance.objects.first()

        self.assertEqual(CycleActivity.objects.filter(cycle=cycle).count(), 1)
        self.assertTrue(
            CycleActivity.objects.filter(cycle=cycle, activity_name="Orientation week").exists()
        )

    def test_day_offsets_convert_to_correct_absolute_dates(self):
        url = reverse("cycles-list")

        data = {
            "template": self.template.template_id,
            "cycle_name": "June Cohort",
            "start_date": "2026-07-01"
        }

        self.client.post(url, data)

        cycle = CycleInstance.objects.first()

        mandatory_task = CycleTask.objects.get(cycle=cycle, task_name="Sign contract")
        self.assertEqual(mandatory_task.calculated_start_date, date(2026, 7, 1))
        self.assertEqual(mandatory_task.calculated_end_date, date(2026, 7, 3))

        optional_task = CycleTask.objects.get(cycle=cycle, task_name="Send welcome kit")
        self.assertEqual(optional_task.calculated_start_date, date(2026, 7, 4))
        self.assertEqual(optional_task.calculated_end_date, date(2026, 7, 4))

        cycle_activity = CycleActivity.objects.get(cycle=cycle, activity_name="Orientation week")
        self.assertEqual(cycle_activity.calculated_start_date, date(2026, 7, 1))
        self.assertEqual(cycle_activity.calculated_end_date, date(2026, 7, 6))

    def test_cycle_creation_copies_runtime_field_values(self):
        url = reverse("cycles-list")

        data = {
            "template": self.template.template_id,
            "cycle_name": "June Cohort",
            "start_date": "2026-07-01"
        }

        self.client.post(url, data)

        cycle = CycleInstance.objects.first()

        mandatory_task = CycleTask.objects.get(cycle=cycle, task_name="Sign contract")
        self.assertTrue(mandatory_task.is_mandatory)
        self.assertFalse(mandatory_task.is_fixed_date)
        self.assertEqual(mandatory_task.reminder_lead_days, [1])
        self.assertEqual(mandatory_task.note_text, "Send to legal for review first")

        optional_task = CycleTask.objects.get(cycle=cycle, task_name="Send welcome kit")
        self.assertFalse(optional_task.is_mandatory)
        self.assertTrue(optional_task.is_fixed_date)
        self.assertEqual(optional_task.reminder_lead_days, [])
        self.assertIsNone(optional_task.note_text)

        cycle_activity = CycleActivity.objects.get(cycle=cycle, activity_name="Orientation week")
        self.assertEqual(cycle_activity.note_text, "Runs alongside onboarding tasks")

    def test_cycle_shutdown_changes_status_from_running_to_shut_down(self):
        cycle = CycleInstance.objects.create(
            user=self.user,
            template=self.template,
            cycle_name="June Cohort",
            start_date=date(2026, 7, 1)
        )

        url = reverse("cycles-shut-down", args=[cycle.cycle_id])

        response = self.client.post(url)

        cycle.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(cycle.status, "shut_down")

    def test_cycle_status_cannot_be_set_directly_on_creation(self):
        url = reverse("cycles-list")

        data = {
            "template": self.template.template_id,
            "cycle_name": "June Cohort",
            "start_date": "2026-07-01",
            "status": "shut_down"
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "running")