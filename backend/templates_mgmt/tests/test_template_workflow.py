from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from templates_mgmt.models import Template, TemplateTask, TemplateActivity, UserTemplate

User = get_user_model()


class TemplateWorkflowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="workflow_user",
            password="Test12345!"
        )
        self.recipient = User.objects.create_user(
            username="recipient_user",
            password="Test12345!"
        )
        self.client.force_authenticate(user=self.user)

    def test_full_template_management_workflow(self):
        create_response = self.client.post(
            "/api/templates/",
            {
                "template_name": "Workflow Template",
                "description": "Template workflow test",
                "is_public": False,
                "template_version": 1,
                "created_by_type": "user",
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        template_id = create_response.data["template_id"]

        task_response = self.client.post(
            "/api/template-tasks/",
            {
                "template": template_id,
                "task_name": "Workflow Task",
                "description": "Task in workflow",
                "day_offset": 1,
                "duration_days": 2,
            },
            format="json",
        )

        self.assertEqual(task_response.status_code, status.HTTP_201_CREATED)

        activity_response = self.client.post(
            "/api/template-activities/",
            {
                "template": template_id,
                "activity_name": "Workflow Activity",
                "description": "Activity in workflow",
                "start_offset_days": 1,
                "end_offset_days": 3,
            },
            format="json",
        )

        self.assertEqual(activity_response.status_code, status.HTTP_201_CREATED)

        duplicate_response = self.client.post(
            f"/api/templates/{template_id}/duplicate/",
            format="json",
        )

        self.assertEqual(duplicate_response.status_code, status.HTTP_201_CREATED)
        copied_template_id = duplicate_response.data["template"]["template_id"]

        self.assertTrue(
            TemplateTask.objects.filter(template_id=copied_template_id).exists()
        )
        self.assertTrue(
            TemplateActivity.objects.filter(template_id=copied_template_id).exists()
        )

        update_response = self.client.put(
            f"/api/templates/{template_id}/",
            {
                "template_name": "Workflow Template Version 2",
                "description": "Updated workflow template",
                "is_public": False,
                "template_version": 1,
                "created_by_type": "user",
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)

        versions_response = self.client.get(
            f"/api/templates/{template_id}/versions/"
        )

        self.assertEqual(versions_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(versions_response.data), 2)

        share_response = self.client.post(
            f"/api/templates/{template_id}/share/",
            {"username": self.recipient.username},
            format="json",
        )

        self.assertEqual(share_response.status_code, status.HTTP_201_CREATED)

        shared_template_id = share_response.data["template"]["template_id"]

        self.assertTrue(
            UserTemplate.objects.filter(
                user=self.recipient,
                template_id=shared_template_id,
                access_type="shared",
            ).exists()
        )