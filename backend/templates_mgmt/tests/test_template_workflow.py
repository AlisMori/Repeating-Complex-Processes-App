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
        # Each task/activity create forks a new template version, a real
        # client has to follow the current version forward at each step
        # rather than reusing the id it started with, this test does the
        # same: current_template_id always points at whatever version the
        # previous step actually landed on.
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
        current_template_id = create_response.data["template_id"]

        task_response = self.client.post(
            "/api/template-tasks/",
            {
                "template": current_template_id,
                "task_name": "Workflow Task",
                "description": "Task in workflow",
                "day_offset": 1,
                "duration_days": 2,
            },
            format="json",
        )

        self.assertEqual(task_response.status_code, status.HTTP_201_CREATED)
        current_template_id = task_response.data["new_template_version"]["template_id"]

        activity_response = self.client.post(
            "/api/template-activities/",
            {
                "template": current_template_id,
                "activity_name": "Workflow Activity",
                "description": "Activity in workflow",
                "start_offset_days": 1,
                "end_offset_days": 3,
            },
            format="json",
        )

        self.assertEqual(activity_response.status_code, status.HTTP_201_CREATED)
        current_template_id = activity_response.data["new_template_version"]["template_id"]

        # By now current_template_id has both the task and the activity,
        # duplicating it should carry both across.
        duplicate_response = self.client.post(
            f"/api/templates/{current_template_id}/duplicate/",
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
            f"/api/templates/{current_template_id}/",
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
        current_template_id = update_response.data["template"]["template_id"]

        versions_response = self.client.get(
            f"/api/templates/{current_template_id}/versions/"
        )

        self.assertEqual(versions_response.status_code, status.HTTP_200_OK)
        # Original -> task fork -> activity fork -> this update's fork,
        # at least 4 versions in the lineage by now.
        self.assertGreaterEqual(len(versions_response.data), 4)

        share_response = self.client.post(
            f"/api/templates/{current_template_id}/share/",
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
        # The share carried the task and activity across too.
        self.assertTrue(
            TemplateTask.objects.filter(template_id=shared_template_id).exists()
        )
        self.assertTrue(
            TemplateActivity.objects.filter(template_id=shared_template_id).exists()
        )