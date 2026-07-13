from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from templates_mgmt.models import Template, TemplateTask, TemplateActivity

User = get_user_model()


class TaskActivityWorkflowTests(APITestCase):
    """Every task/activity create, update, or delete forks a new
    template version, the original template and its rows are frozen,
    untouched. These workflows follow the version forward at each step
    instead of assuming the same row keeps getting edited in place.
    """

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
        self.assertIn("new_template_version", update_response.data)

        # The original task is frozen, untouched, still "Initial Task".
        original_task = TemplateTask.objects.get(pk=task_id)
        self.assertEqual(original_task.task_name, "Initial Task")

        # The update landed on the new version's copy of the task instead.
        updated_task_id = update_response.data["template_task_id"]
        self.assertNotEqual(updated_task_id, task_id)
        updated_task = TemplateTask.objects.get(pk=updated_task_id)
        self.assertEqual(updated_task.task_name, "Updated Task")

        delete_response = self.client.delete(
            f"/api/template-tasks/{updated_task_id}/"
        )

        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertIn("new_template_version", delete_response.data)
        # The delete itself forks yet another version, the task that
        # actually disappears is this newest version's own copy, not
        # updated_task_id, which now belongs to the version just before
        # it and stays exactly as it was, same as every other fork.
        newest_template_id = delete_response.data["new_template_version"]["template_id"]
        self.assertEqual(
            TemplateTask.objects.filter(template_id=newest_template_id).count(), 0
        )
        self.assertTrue(TemplateTask.objects.filter(pk=updated_task_id).exists())
        self.assertTrue(TemplateTask.objects.filter(pk=task_id).exists())

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
        self.assertIn("new_template_version", update_response.data)

        original_activity = TemplateActivity.objects.get(pk=activity_id)
        self.assertEqual(original_activity.activity_name, "Initial Activity")

        updated_activity_id = update_response.data["template_activity_id"]
        self.assertNotEqual(updated_activity_id, activity_id)
        updated_activity = TemplateActivity.objects.get(pk=updated_activity_id)
        self.assertEqual(updated_activity.activity_name, "Updated Activity")

        delete_response = self.client.delete(
            f"/api/template-activities/{updated_activity_id}/"
        )

        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertIn("new_template_version", delete_response.data)
        newest_template_id = delete_response.data["new_template_version"]["template_id"]
        self.assertEqual(
            TemplateActivity.objects.filter(template_id=newest_template_id).count(), 0
        )
        self.assertTrue(TemplateActivity.objects.filter(pk=updated_activity_id).exists())
        self.assertTrue(TemplateActivity.objects.filter(pk=activity_id).exists())