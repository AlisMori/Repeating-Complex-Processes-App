from django.contrib.auth import get_user_model
from datetime import date
from rest_framework import status
from rest_framework.test import APITestCase

from templates_mgmt.models import Template, TemplateTask, TemplateActivity
from cycles.models import CycleInstance

User = get_user_model()


class TaskActivityWorkflowTests(APITestCase):
    """Every task/activity create, update, or delete on a template a
    cycle has already been created from forks a new template version,
    the original template and its rows are frozen, untouched. These
    workflows follow the version forward at each step instead of
    assuming the same row keeps getting edited in place.
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
        # A cycle already exists, so every edit below is expected to
        # fork (see get_editable_template in templates_mgmt/services.py).
        CycleInstance.objects.create(
            user=self.user, template=self.template, cycle_name="Existing run", start_date=date.today(),
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
        self.assertIn("new_template_version", create_response.data)

        task_id = create_response.data["template_task_id"]
        self.assertTrue(TemplateTask.objects.filter(pk=task_id).exists())
        # self.template already had a cycle on it, so creating the
        # task forked a new version, self.template's own row is
        # untouched and still has no tasks of its own.
        self.assertEqual(TemplateTask.objects.filter(template=self.template).count(), 0)

        update_response = self.client.patch(
            f"/api/template-tasks/{task_id}/",
            {
                "task_name": "Updated Task",
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        # No cycle has ever been created from THIS version yet (the
        # one the task just landed on), so this edit writes in place
        # instead of forking yet again.
        self.assertNotIn("new_template_version", update_response.data)

        updated_task_id = update_response.data["template_task_id"]
        self.assertEqual(updated_task_id, task_id)
        updated_task = TemplateTask.objects.get(pk=updated_task_id)
        self.assertEqual(updated_task.task_name, "Updated Task")

        delete_response = self.client.delete(
            f"/api/template-tasks/{updated_task_id}/"
        )

        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertNotIn("new_template_version", delete_response.data)
        self.assertFalse(TemplateTask.objects.filter(pk=updated_task_id).exists())

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
        self.assertIn("new_template_version", create_response.data)

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
        # Same reasoning as the task workflow above: this fresh version
        # has never been used by a cycle yet, so it's edited in place.
        self.assertNotIn("new_template_version", update_response.data)

        updated_activity_id = update_response.data["template_activity_id"]
        self.assertEqual(updated_activity_id, activity_id)
        updated_activity = TemplateActivity.objects.get(pk=updated_activity_id)
        self.assertEqual(updated_activity.activity_name, "Updated Activity")

        delete_response = self.client.delete(
            f"/api/template-activities/{updated_activity_id}/"
        )

        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertNotIn("new_template_version", delete_response.data)
        self.assertFalse(TemplateActivity.objects.filter(pk=updated_activity_id).exists())