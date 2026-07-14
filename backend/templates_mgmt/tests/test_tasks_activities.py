from django.urls import reverse
from datetime import date
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import User
from templates_mgmt.models import (
    Template,
    TemplateTask,
    TemplateActivity,
    Tag,
)
from cycles.models import CycleInstance

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
        # A cycle already exists from this template in every test
        # below, so editing it is expected to fork a new version
        # (see templates_mgmt/services.py: get_editable_template only
        # forks once a cycle depends on the current row).
        CycleInstance.objects.create(
            user=self.user, template=self.template, cycle_name="Existing run", start_date=date.today(),
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
        # Any edit forks a new template version, the original task row
        # is frozen, the response points at the new version's own copy.
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

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )
        self.assertIn("new_template_version", response.data)

        task.refresh_from_db()
        self.assertEqual(task.task_name, "Old Name")

        new_task_id = response.data["template_task_id"]
        self.assertNotEqual(new_task_id, task.template_task_id)
        new_task = TemplateTask.objects.get(pk=new_task_id)
        self.assertEqual(new_task.task_name, "New Name")

    def test_delete_template_task(self):
        # Deleting forks a version too, the copy is what actually gets
        # removed, the original frozen row is never touched.
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
            status.HTTP_200_OK
        )
        self.assertIn("new_template_version", response.data)

        new_template_id = response.data["new_template_version"]["template_id"]
        self.assertEqual(
            TemplateTask.objects.filter(template_id=new_template_id).count(),
            0
        )
        # The original task, on the now-frozen original version, still
        # exists, deleting later never reaches back to it.
        self.assertTrue(TemplateTask.objects.filter(pk=task.template_task_id).exists())

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

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )
        self.assertIn("new_template_version", response.data)

        activity.refresh_from_db()
        self.assertEqual(activity.activity_name, "Old Activity")

        new_activity_id = response.data["template_activity_id"]
        self.assertNotEqual(new_activity_id, activity.template_activity_id)
        new_activity = TemplateActivity.objects.get(pk=new_activity_id)
        self.assertEqual(new_activity.activity_name, "New Activity")

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
            status.HTTP_200_OK
        )
        self.assertIn("new_template_version", response.data)

        new_template_id = response.data["new_template_version"]["template_id"]
        self.assertEqual(
            TemplateActivity.objects.filter(template_id=new_template_id).count(),
            0
        )
        self.assertTrue(TemplateActivity.objects.filter(pk=activity.pk).exists())

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

    def test_list_template_tasks_filters_by_template(self):
        """
        GET /template-tasks/?template=<id> must only return tasks
        belonging to that template — not every task across every
        template the user can access.
        """
        other_template = Template.objects.create(
            user=self.user,
            template_name="Other Template",
            description="A different template owned by the same user",
        )

        task_in_first = TemplateTask.objects.create(
            template=self.template,
            task_name="Task in first template",
            day_offset=1,
        )
        TemplateTask.objects.create(
            template=other_template,
            task_name="Task in other template",
            day_offset=2,
        )

        url = reverse("template-tasks-list")
        response = self.client.get(url, {"template": self.template.template_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {row["template_task_id"] for row in response.data}
        self.assertEqual(returned_ids, {task_in_first.template_task_id})

    def test_list_template_activities_filters_by_template(self):
        """
        GET /template-activities/?template=<id> must only return
        activities belonging to that template — not every activity
        across every template the user can access.
        """
        other_template = Template.objects.create(
            user=self.user,
            template_name="Other Template",
            description="A different template owned by the same user",
        )

        activity_in_first = TemplateActivity.objects.create(
            template=self.template,
            activity_name="Activity in first template",
            start_offset_days=1,
            end_offset_days=2,
        )
        TemplateActivity.objects.create(
            template=other_template,
            activity_name="Activity in other template",
            start_offset_days=1,
            end_offset_days=2,
        )

        url = reverse("template-activities-list")
        response = self.client.get(url, {"template": self.template.template_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {row["template_activity_id"] for row in response.data}
        self.assertEqual(returned_ids, {activity_in_first.template_activity_id})

    def test_list_template_tasks_without_filter_still_scoped_to_user(self):
        """
        Without a ?template= filter, the endpoint should still only
        ever return tasks the user can access (existing access-control
        behaviour) — this filter is additive, not a replacement.
        """
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@test.com",
            password="test123",
        )
        other_users_template = Template.objects.create(
            user=other_user,
            template_name="Not mine",
        )
        TemplateTask.objects.create(
            template=other_users_template,
            task_name="Should not be visible",
            day_offset=1,
        )

        url = reverse("template-tasks-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_names = {row["task_name"] for row in response.data}
        self.assertNotIn("Should not be visible", returned_names)

    def test_create_template_task_with_activity_link(self):
        activity = TemplateActivity.objects.create(
            template=self.template,
            activity_name="Activity Container",
            start_offset_days=1,
            end_offset_days=5,
        )

        url = reverse("template-tasks-list")

        response = self.client.post(
            url,
            {
                "template": self.template.template_id,
                "template_activity": activity.template_activity_id,
                "task_name": "Linked Task",
                "description": "Task linked to activity",
                "day_offset": 2,
                "duration_days": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Creating a task also forks a version, so the task links to the
        # NEW version's copy of the activity, not the original instance.
        task = TemplateTask.objects.get(task_name="Linked Task")
        self.assertEqual(task.template_activity.activity_name, "Activity Container")
        self.assertEqual(task.template_activity.template_id, task.template_id)
        self.assertNotEqual(task.template_activity_id, activity.template_activity_id)

    def test_task_outside_activity_range_expands_activity(self):
        activity = TemplateActivity.objects.create(
            template=self.template,
            activity_name="Expandable Activity",
            start_offset_days=3,
            end_offset_days=5,
        )

        task = TemplateTask.objects.create(
            template=self.template,
            template_activity=activity,
            task_name="Edge Task",
            day_offset=3,
            duration_days=1,
        )

        url = reverse("template-tasks-detail", args=[task.template_task_id])

        response = self.client.patch(
            url,
            {
                "day_offset": 1,
                "duration_days": 6,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # The original activity is frozen, unchanged.
        activity.refresh_from_db()
        self.assertEqual(activity.start_offset_days, 3)
        self.assertEqual(activity.end_offset_days, 5)

        # The new version's copy of the activity is the one that widened.
        new_task_id = response.data["template_task_id"]
        new_task = TemplateTask.objects.get(pk=new_task_id)
        new_activity = new_task.template_activity
        self.assertEqual(new_activity.start_offset_days, 1)
        self.assertEqual(new_activity.end_offset_days, 7)

    def test_delete_activity_deletes_linked_tasks(self):
        activity = TemplateActivity.objects.create(
            template=self.template,
            activity_name="Activity With Tasks",
            start_offset_days=1,
            end_offset_days=5,
        )

        TemplateTask.objects.create(
            template=self.template,
            template_activity=activity,
            task_name="Linked Task",
            day_offset=2,
            duration_days=1,
        )

        url = reverse("template-activities-detail", args=[activity.template_activity_id])

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("new_template_version", response.data)

        new_template_id = response.data["new_template_version"]["template_id"]
        # Neither the activity nor its linked task exist on the new
        # version, deleting the activity took the task with it there.
        self.assertFalse(
            TemplateActivity.objects.filter(template_id=new_template_id).exists()
        )
        self.assertFalse(
            TemplateTask.objects.filter(
                template_id=new_template_id, task_name="Linked Task"
            ).exists()
        )
        # The original activity and task, on the frozen original
        # version, are both untouched.
        self.assertTrue(TemplateActivity.objects.filter(pk=activity.pk).exists())
        self.assertTrue(TemplateTask.objects.filter(task_name="Linked Task").exists())