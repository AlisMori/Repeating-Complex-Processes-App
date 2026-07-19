from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from django.urls import reverse

from templates_mgmt.models import Template, TemplateTask, TemplateActivity
from cycles.models import CycleInstance, CycleTask, CycleActivity


User = get_user_model()


class ApiDatabaseIntegrationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="api_db_user",
            password="Test12345!"
        )
        self.client.force_authenticate(user=self.user)

    def test_template_api_persists_template_to_database(self):
        response = self.client.post(
            "/api/templates/",
            {
                "template_name": "API DB Template",
                "description": "Created through API",
                "is_public": False,
                "template_version": 1,
                "created_by_type": "user",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Template.objects.filter(template_name="API DB Template").exists()
        )

    def test_template_task_api_persists_task_to_database(self):
        template = Template.objects.create(
            user=self.user,
            template_name="Task Parent Template",
        )

        response = self.client.post(
            "/api/template-tasks/",
            {
                "template": template.template_id,
                "task_name": "API DB Task",
                "description": "Created through API",
                "day_offset": 1,
                "duration_days": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            TemplateTask.objects.filter(task_name="API DB Task").exists()
        )

    def test_template_activity_api_persists_activity_to_database(self):
        template = Template.objects.create(
            user=self.user,
            template_name="Activity Parent Template",
        )

        response = self.client.post(
            "/api/template-activities/",
            {
                "template": template.template_id,
                "activity_name": "API DB Activity",
                "description": "Created through API",
                "start_offset_days": 1,
                "end_offset_days": 3,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            TemplateActivity.objects.filter(activity_name="API DB Activity").exists()
        )

    def test_template_api_reads_template_from_database(self):
        template = Template.objects.create(
            user=self.user,
            template_name="Readable Template",
            description="Stored in database",
        )

        response = self.client.get(f"/api/templates/{template.template_id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["template_name"], "Readable Template")

    def test_cycle_creation_generates_runtime_records(self):
        template = Template.objects.create(
            user=self.user,
            template_name="Runtime Template",
        )

        activity = TemplateActivity.objects.create(
            template=template,
            activity_name="Orientation",
            start_offset_days=0,
            end_offset_days=5,
        )

        task = TemplateTask.objects.create(
            template=template,
            task_name="Sign contract",
            day_offset=0,
            duration_days=2,
            template_activity=activity,
        )

        response = self.client.post(
            reverse("cycles-list"),
            {
                "template": template.template_id,
                "cycle_name": "June Cohort",
                "start_date": "2026-07-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        cycle = CycleInstance.objects.get(cycle_name="June Cohort")

        self.assertEqual(
            CycleTask.objects.filter(cycle=cycle).count(),
            1,
        )

        self.assertEqual(
            CycleActivity.objects.filter(cycle=cycle).count(),
            1,
        )

    def test_shift_api_persists_cascade_update(self):
        template = Template.objects.create(
            user=self.user,
            template_name="Shift Template",
        )

        task_a = TemplateTask.objects.create(
            template=template,
            task_name="A",
            day_offset=0,
            duration_days=2,
        )

        response = self.client.post(
            reverse("cycles-list"),
            {
                "template": template.template_id,
                "cycle_name": "Shift Cycle",
                "start_date": "2026-07-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        cycle = CycleInstance.objects.get(cycle_name="Shift Cycle")
        runtime_task = CycleTask.objects.get(
            cycle=cycle,
            task_name="A",
        )

        original_date = runtime_task.calculated_start_date

        response = self.client.post(
            reverse(
                "cycle-tasks-shift",
                args=[runtime_task.cycle_task_id],
            ),
            {
                "delay_days": 2,
                "scope": "single",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        runtime_task.refresh_from_db()

        self.assertNotEqual(
            runtime_task.calculated_start_date,
            original_date,
        )