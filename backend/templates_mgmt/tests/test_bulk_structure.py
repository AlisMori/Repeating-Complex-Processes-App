from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from templates_mgmt.models import (
    Tag,
    Template,
    TemplateActivity,
    TemplateActivityTag,
    TemplateTask,
    TemplateTaskTag,
)
from cycles.models import TaskDependency


User = get_user_model()


class SaveStructureTests(APITestCase):
    """Covers POST /templates/{id}/save_structure/ — the atomic,
    validate-everything-before-writing-anything replacement for the
    old one-API-call-per-task/activity/dependency approach.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="bulk_owner", password="Test12345!")
        self.other_user = User.objects.create_user(username="bulk_other", password="Test12345!")
        self.client.force_authenticate(user=self.user)
        self.template = Template.objects.create(user=self.user, template_name="Exam Flow", description="")
        self.url = f"/api/templates/{self.template.template_id}/save_structure/"

    def test_first_ever_save_writes_in_place_with_no_fork(self):
        # Nothing exists on this template yet, so there's no version a
        # cycle could possibly already be using — writing in place
        # avoids leaving a throwaway empty version behind forever.
        tag = Tag.objects.create(user=self.user, tag_name="Important")
        payload = {
            "activities": [
                {"local_id": "A1", "activity_name": "Week 1", "start_offset_days": 0, "end_offset_days": 10, "tag_ids": [tag.tag_id]},
            ],
            "tasks": [
                {"local_id": "T1", "task_name": "Kickoff", "day_offset": 0, "duration_days": 2, "activity_local_id": "A1", "tag_ids": [tag.tag_id]},
                {"local_id": "T2", "task_name": "Follow-up", "day_offset": 2, "duration_days": 1, "activity_local_id": "A1"},
            ],
            "dependencies": [
                {"task_local_id": "T2", "depends_on_local_id": "T1"},
            ],
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_id = response.data["new_template_version"]["template_id"]

        # No fork at all — same row, still current.
        self.assertEqual(new_id, self.template.template_id)
        self.assertTrue(Template.objects.get(pk=self.template.template_id).is_current_version)
        self.assertEqual(Template.objects.filter(parent_template=self.template).count(), 0)

        self.assertEqual(TemplateActivity.objects.filter(template_id=new_id).count(), 1)
        self.assertEqual(TemplateTask.objects.filter(template_id=new_id).count(), 2)
        self.assertEqual(TaskDependency.objects.filter(task__template_id=new_id).count(), 1)

        new_task = TemplateTask.objects.get(template_id=new_id, task_name="Kickoff")
        new_activity = TemplateActivity.objects.get(template_id=new_id, activity_name="Week 1")
        self.assertTrue(TemplateTaskTag.objects.filter(template_task=new_task, tag=tag).exists())
        self.assertTrue(TemplateActivityTag.objects.filter(template_activity=new_activity, tag=tag).exists())

    def test_editing_an_unlocked_populated_template_still_writes_in_place(self):
        # This template already has content from an earlier draft
        # save, but still no cycle has ever been created from it, so
        # there's still nothing a fork would be protecting. This is
        # exactly the "keep saving while drafting" flow, it must not
        # fork a new version on every single save.
        TemplateTask.objects.create(
            template=self.template, task_name="Original", day_offset=0, duration_days=1,
        )
        payload = {
            "activities": [],
            "tasks": [{"local_id": "T1", "task_name": "Replacement", "day_offset": 0, "duration_days": 1}],
            "dependencies": [],
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_id = response.data["new_template_version"]["template_id"]

        self.assertEqual(new_id, self.template.template_id)
        self.assertEqual(Template.objects.filter(parent_template=self.template).count(), 0)
        self.assertTrue(Template.objects.get(pk=self.template.template_id).is_current_version)

        # The old draft content was replaced, not piled on top of.
        self.assertFalse(TemplateTask.objects.filter(template=self.template, task_name="Original").exists())
        self.assertEqual(TemplateTask.objects.filter(template_id=new_id).count(), 1)
        self.assertEqual(TemplateTask.objects.get(template_id=new_id).task_name, "Replacement")

    def test_editing_a_template_a_cycle_was_created_from_forks_exactly_one_new_version(self):
        # Once a cycle actually exists from this template, THIS is the
        # case that must fork rather than overwrite, freezing the
        # version that cycle depends on.
        from datetime import date
        from cycles.models import CycleInstance

        TemplateTask.objects.create(
            template=self.template, task_name="Original", day_offset=0, duration_days=1,
        )
        CycleInstance.objects.create(
            user=self.user, template=self.template, cycle_name="Run 1", start_date=date.today(),
        )
        payload = {
            "activities": [],
            "tasks": [{"local_id": "T1", "task_name": "Replacement", "day_offset": 0, "duration_days": 1}],
            "dependencies": [],
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_id = response.data["new_template_version"]["template_id"]

        self.assertNotEqual(new_id, self.template.template_id)
        self.assertEqual(Template.objects.filter(parent_template=self.template).count(), 1)
        self.assertFalse(Template.objects.get(pk=self.template.template_id).is_current_version)
        self.assertTrue(Template.objects.get(pk=new_id).is_current_version)

        # Old version's own task is untouched, exactly as it was.
        self.assertTrue(TemplateTask.objects.filter(template=self.template, task_name="Original").exists())
        self.assertEqual(TemplateTask.objects.filter(template_id=new_id).count(), 1)
        self.assertEqual(TemplateTask.objects.get(template_id=new_id).task_name, "Replacement")

    def test_resubmitting_twice_before_any_cycle_exists_keeps_writing_in_place(self):
        payload = {
            "activities": [],
            "tasks": [{"local_id": "T1", "task_name": "Solo task", "day_offset": 0, "duration_days": 1}],
            "dependencies": [],
        }

        first = self.client.post(self.url, payload, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        first_id = first.data["new_template_version"]["template_id"]
        self.assertEqual(TemplateTask.objects.filter(template_id=first_id).count(), 1)

        # Simulates "Back" then resubmitting the exact same structure
        # while still drafting (no cycle yet) — same row both times,
        # not a second throwaway version, and never more than one task.
        url_on_current_version = f"/api/templates/{first_id}/save_structure/"
        second = self.client.post(url_on_current_version, payload, format="json")
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        second_id = second.data["new_template_version"]["template_id"]

        self.assertEqual(TemplateTask.objects.filter(template_id=second_id).count(), 1)
        self.assertEqual(first_id, second_id)

    def test_resubmitting_twice_after_a_cycle_exists_forks_each_time(self):
        from datetime import date
        from cycles.models import CycleInstance

        payload = {
            "activities": [],
            "tasks": [{"local_id": "T1", "task_name": "Solo task", "day_offset": 0, "duration_days": 1}],
            "dependencies": [],
        }

        first = self.client.post(self.url, payload, format="json")
        first_id = first.data["new_template_version"]["template_id"]
        CycleInstance.objects.create(
            user=self.user, template_id=first_id, cycle_name="Run 1", start_date=date.today(),
        )

        url_on_current_version = f"/api/templates/{first_id}/save_structure/"
        second = self.client.post(url_on_current_version, payload, format="json")
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        second_id = second.data["new_template_version"]["template_id"]

        self.assertEqual(TemplateTask.objects.filter(template_id=second_id).count(), 1)
        self.assertNotEqual(first_id, second_id)

    def test_invalid_activity_bounds_rejects_with_no_writes(self):
        before_count = Template.objects.count()
        payload = {
            "activities": [{"local_id": "A1", "activity_name": "Bad", "start_offset_days": 5, "end_offset_days": 5}],
            "tasks": [],
            "dependencies": [],
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(response.data["errors"]), 1)
        self.assertEqual(Template.objects.count(), before_count)
        self.assertTrue(Template.objects.get(pk=self.template.template_id).is_current_version)

    def test_task_not_fitting_activity_rejects_with_no_writes(self):
        payload = {
            "activities": [{"local_id": "A1", "activity_name": "Week 1", "start_offset_days": 0, "end_offset_days": 5}],
            "tasks": [{"local_id": "T1", "task_name": "Overflow", "day_offset": 4, "duration_days": 3, "activity_local_id": "A1"}],
            "dependencies": [],
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(TemplateActivity.objects.filter(template=self.template).count(), 0)
        self.assertEqual(TemplateTask.objects.filter(template=self.template).count(), 0)

    def test_circular_dependency_rejects_with_no_writes(self):
        payload = {
            "activities": [],
            "tasks": [
                {"local_id": "T1", "task_name": "A", "day_offset": 0, "duration_days": 1},
                {"local_id": "T2", "task_name": "B", "day_offset": 1, "duration_days": 1},
                {"local_id": "T3", "task_name": "C", "day_offset": 2, "duration_days": 1},
            ],
            "dependencies": [
                {"task_local_id": "T2", "depends_on_local_id": "T1"},
                {"task_local_id": "T3", "depends_on_local_id": "T2"},
                {"task_local_id": "T1", "depends_on_local_id": "T3"},
            ],
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(any(e["type"] == "dependency" and "circular" in e["message"] for e in response.data["errors"]))
        self.assertEqual(TemplateTask.objects.filter(template=self.template).count(), 0)

    def test_fan_out_cap_exceeded_rejects_with_no_writes(self):
        payload = {
            "activities": [],
            "tasks": [
                {"local_id": "T1", "task_name": "Hub", "day_offset": 0, "duration_days": 1},
                {"local_id": "T2", "task_name": "B", "day_offset": 1, "duration_days": 1},
                {"local_id": "T3", "task_name": "C", "day_offset": 1, "duration_days": 1},
                {"local_id": "T4", "task_name": "D", "day_offset": 1, "duration_days": 1},
            ],
            "dependencies": [
                {"task_local_id": "T2", "depends_on_local_id": "T1"},
                {"task_local_id": "T3", "depends_on_local_id": "T1"},
                {"task_local_id": "T4", "depends_on_local_id": "T1"},
            ],
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(any(e["type"] == "dependency" and "already has 2 tasks" in e["message"] for e in response.data["errors"]))
        self.assertEqual(TemplateTask.objects.filter(template=self.template).count(), 0)

    def test_offset_conflict_rejects_with_no_writes(self):
        payload = {
            "activities": [],
            "tasks": [
                {"local_id": "T1", "task_name": "Late finisher", "day_offset": 5, "duration_days": 5},
                {"local_id": "T2", "task_name": "Starts too early", "day_offset": 3, "duration_days": 1},
            ],
            "dependencies": [
                {"task_local_id": "T2", "depends_on_local_id": "T1"},
            ],
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(any(e["type"] == "dependency" and "before" in e["message"] for e in response.data["errors"]))
        self.assertEqual(TemplateTask.objects.filter(template=self.template).count(), 0)

    def test_tag_not_owned_by_user_rejects_with_no_writes(self):
        other_tag = Tag.objects.create(user=self.other_user, tag_name="Not yours")
        payload = {
            "activities": [],
            "tasks": [{"local_id": "T1", "task_name": "Task", "day_offset": 0, "duration_days": 1, "tag_ids": [other_tag.tag_id]}],
            "dependencies": [],
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(TemplateTask.objects.filter(template=self.template).count(), 0)

    def test_self_dependency_rejects_with_no_writes(self):
        payload = {
            "activities": [],
            "tasks": [{"local_id": "T1", "task_name": "Solo", "day_offset": 0, "duration_days": 1}],
            "dependencies": [{"task_local_id": "T1", "depends_on_local_id": "T1"}],
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(TemplateTask.objects.filter(template=self.template).count(), 0)

    def test_user_without_access_gets_404(self):
        self.client.force_authenticate(user=self.other_user)
        payload = {"activities": [], "tasks": [], "dependencies": []}

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_empty_structure_before_any_cycle_clears_in_place(self):
        activity = TemplateActivity.objects.create(
            template=self.template, activity_name="Old", start_offset_days=0, end_offset_days=1,
        )
        TemplateTask.objects.create(
            template=self.template, template_activity=activity, task_name="Old task", day_offset=0, duration_days=1,
        )
        payload = {"activities": [], "tasks": [], "dependencies": []}

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_id = response.data["new_template_version"]["template_id"]
        self.assertEqual(new_id, self.template.template_id)
        self.assertEqual(TemplateTask.objects.filter(template_id=new_id).count(), 0)
        self.assertEqual(TemplateActivity.objects.filter(template_id=new_id).count(), 0)

    def test_empty_structure_after_a_cycle_exists_leaves_the_old_version_untouched(self):
        from datetime import date
        from cycles.models import CycleInstance

        activity = TemplateActivity.objects.create(
            template=self.template, activity_name="Old", start_offset_days=0, end_offset_days=1,
        )
        TemplateTask.objects.create(
            template=self.template, template_activity=activity, task_name="Old task", day_offset=0, duration_days=1,
        )
        CycleInstance.objects.create(
            user=self.user, template=self.template, cycle_name="Run 1", start_date=date.today(),
        )
        payload = {"activities": [], "tasks": [], "dependencies": []}

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_id = response.data["new_template_version"]["template_id"]
        self.assertNotEqual(new_id, self.template.template_id)
        self.assertEqual(TemplateTask.objects.filter(template_id=new_id).count(), 0)
        self.assertEqual(TemplateActivity.objects.filter(template_id=new_id).count(), 0)
        # Old version is untouched, frozen exactly as it was.
        self.assertEqual(TemplateTask.objects.filter(template=self.template).count(), 1)