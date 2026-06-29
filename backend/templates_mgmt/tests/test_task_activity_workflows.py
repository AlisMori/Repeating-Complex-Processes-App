from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from templates_mgmt.models import Template, TemplateTask, TemplateActivity

User = get_user_model()


class TaskActivityWorkflowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="workflow_test_user",
            password="Test12345!"
        )
        self.client.force_authenticate(user=self.user)

        self.template = Template.objects.create(
            user=self.user,
            template_name="Workflow Template",
            description="Template for task and activity workflow testing",
        )

    def test_task_workflow_create_update_delete(self):
        create_response = self.client.post(
            "/api/template-tasks/",
            {
                "template": self.template.template_id,
                "task_name": "Initial Task",
                "description": "Created during workflow test",
                "day_offset": 1,
                "duration_days": 2,
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        task_id = create_response.data["template_task_id"]
        self.assertTrue(TemplateTask.objects.filter(pk=task_id).exists())

        update_response = self.client.patch(
            f"/api/template-tasks/{task_id}/",
            {
                "task_name": "Updated Task",
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)

        task = TemplateTask.objects.get(pk=task_id)
        self.assertEqual(task.task_name, "Updated Task")

        delete_response = self.client.delete(
            f"/api/template-tasks/{task_id}/"
        )

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TemplateTask.objects.filter(pk=task_id).exists())

    def test_activity_workflow_create_update_delete(self):
        create_response = self.client.post(
            "/api/template-activities/",
            {
                "template": self.template.template_id,
                "activity_name": "Initial Activity",
                "description": "Created during workflow test",
                "start_offset_days": 1,
                "end_offset_days": 3,
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        activity_id = create_response.data["template_activity_id"]
        self.assertTrue(TemplateActivity.objects.filter(pk=activity_id).exists())

        update_response = self.client.patch(
            f"/api/template-activities/{activity_id}/",
            {
                "activity_name": "Updated Activity",
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)

        activity = TemplateActivity.objects.get(pk=activity_id)
        self.assertEqual(activity.activity_name, "Updated Activity")

        delete_response = self.client.delete(
            f"/api/template-activities/{activity_id}/"
        )

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TemplateActivity.objects.filter(pk=activity_id).exists())