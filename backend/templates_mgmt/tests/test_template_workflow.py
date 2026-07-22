from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import ShareNotification
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
        # No cycle is ever created from this template in this test, so
        # task/activity creates write in place onto the still-current,
        # still-unused row (see get_editable_template). Duplicating
        # forks a real new version (Vx+1) of the current row though,
        # which freezes it, so the later direct edit against that now
        # non-current id forks again — a client still has to follow
        # the version forward from that point on.
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
        self.assertNotIn("new_template_version", task_response.data)

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
        self.assertNotIn("new_template_version", activity_response.data)

        # current_template_id now has both the task and the activity,
        # duplicating it should carry both across, and forks it
        # forward to Vx+1, freezing current_template_id itself.
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

        # current_template_id is frozen now (superseded by the
        # duplicate's fork), editing it directly by id forks it again.
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
        # Original -> duplicate's fork -> this update's fork, at least
        # 3 versions in the lineage by now.
        self.assertGreaterEqual(len(versions_response.data), 3)

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
        self.assertTrue(
            ShareNotification.objects.filter(
                recipient=self.recipient,
                sender=self.user,
                template_id=shared_template_id,
                template_name="Workflow Template Version 2",
                is_read=False,
            ).exists()
        )
