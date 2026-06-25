from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import User
from templates_mgmt.models import (
    Template,
    TemplateTask,
    TemplateActivity,
    Tag,
)

class TaskActivityManagementTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
        username="testuser",
        email="test@test.com",
        password="test123"
        )

        self.client.force_authenticate(user=self.user)

        self.template = Template.objects.create(
            user=self.user,
            template_name="Test Template",
            description="Testing"
        )

    def test_create_template_task(self):
        url = reverse("template-tasks-list")

        data = {
            "template": self.template.template_id,
            "task_name": "Task 1",
            "description": "Test task",
            "day_offset": 1,
            "duration_days": 2
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            TemplateTask.objects.count(),
            1
        )

    def test_update_template_task(self):
        task = TemplateTask.objects.create(
        template=self.template,
        task_name="Old Name",
        day_offset=1
        )

        url = reverse(
            "template-tasks-detail",
            args=[task.template_task_id]
        )

        response = self.client.patch(
            url,
            {"task_name": "New Name"}
        )

        task.refresh_from_db()

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )
        self.assertEqual(
            task.task_name,
            "New Name"
        )

    def test_delete_template_task(self):
        task = TemplateTask.objects.create(
            template=self.template,
            task_name="Task",
            day_offset=1
        )

        url = reverse(
            "template-tasks-detail",
            args=[task.template_task_id]
        )

        response = self.client.delete(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT
        )
        self.assertEqual(
            TemplateTask.objects.count(),
            0
        )
    
    def test_create_template_activity(self):
        url = reverse("template-activities-list")

        data = {
            "template": self.template.template_id,
            "activity_name": "Activity 1",
            "description": "Test activity",
            "start_offset_days": 1,
            "end_offset_days": 3
        }

        response = self.client.post(url, data)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )
        self.assertEqual(
            TemplateActivity.objects.count(),
            1
        )

    def test_update_template_activity(self):
        activity = TemplateActivity.objects.create(
            template=self.template,
            activity_name="Old Activity",
            start_offset_days=1,
            end_offset_days=2
        )

        url = reverse(
            "template-activities-detail",
            args=[activity.template_activity_id]
        )

        response = self.client.patch(
            url,
            {"activity_name": "New Activity"}
        )

        activity.refresh_from_db()

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )
        self.assertEqual(
            activity.activity_name,
            "New Activity"
        )

    def test_delete_template_activity(self):
        activity = TemplateActivity.objects.create(
            template=self.template,
            activity_name="Activity",
            start_offset_days=1,
            end_offset_days=2
        )

        url = reverse(
            "template-activities-detail",
            args=[activity.template_activity_id]
        )

        response = self.client.delete(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT
        )
        self.assertEqual(
            TemplateActivity.objects.count(),
            0
        )

    def test_create_tag(self):
        url = reverse("tags-list")

        response = self.client.post(
            url,
            {"tag_name": "Important"}
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )
        self.assertEqual(
            Tag.objects.count(),
            1
        )

