from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from cycles.models import CycleActivity, CycleInstance, CycleTask
from templates_mgmt.models import Template, TemplateActivity, TemplateTask, UserTemplate


User = get_user_model()


class SmartSearchApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="search-owner", password="Test12345!")
        self.other_user = User.objects.create_user(username="search-other", password="Test12345!")
        self.url = reverse("smart-search")

        self.template = Template.objects.create(
            user=self.user,
            template_name="Exam Preparation Template",
            description="Checklist for final exam delivery",
            is_public=False,
            created_by_type="user",
        )
        UserTemplate.objects.create(user=self.user, template=self.template, access_type="owner")

        self.template_task = TemplateTask.objects.create(
            template=self.template,
            task_name="Prepare for Exam",
            description="Draft the exam paper",
            day_offset=0,
            duration_days=1,
            is_mandatory=True,
            note_text="Exam paper must be approved",
        )
        self.template_activity = TemplateActivity.objects.create(
            template=self.template,
            activity_name="Final Exam Week",
            description="Main exam activity window",
            start_offset_days=0,
            end_offset_days=5,
            note_text="Exam supervision notes",
        )

        self.running_cycle = CycleInstance.objects.create(
            user=self.user,
            template=self.template,
            cycle_name="ICT302 Exam Cycle",
            start_date=date(2026, 7, 1),
            status="running",
        )
        self.completed_cycle = CycleInstance.objects.create(
            user=self.user,
            template=self.template,
            cycle_name="Completed Teaching Cycle",
            start_date=date(2026, 1, 1),
            status="completed",
        )

        self.running_task = CycleTask.objects.create(
            cycle=self.running_cycle,
            template_task=self.template_task,
            task_name="Submit Exam Registration",
            calculated_start_date=date(2026, 7, 2),
            calculated_end_date=date(2026, 7, 3),
            status="overdue",
            is_mandatory=True,
            note_text="Registration note for exam board",
        )
        self.completed_cycle_task = CycleTask.objects.create(
            cycle=self.completed_cycle,
            template_task=self.template_task,
            task_name="Archive exam paperwork",
            calculated_start_date=date(2026, 1, 2),
            calculated_end_date=date(2026, 1, 3),
            status="completed",
            is_mandatory=True,
            note_text="Historic exam archive",
        )
        self.running_activity = CycleActivity.objects.create(
            cycle=self.running_cycle,
            template_activity=self.template_activity,
            activity_name="Exam Moderation",
            calculated_start_date=date(2026, 7, 2),
            calculated_end_date=date(2026, 7, 6),
            note_text="Moderation for exam period",
        )

        self.other_template = Template.objects.create(
            user=self.other_user,
            template_name="Other User Exam Template",
            description="Should not be visible",
            is_public=False,
            created_by_type="user",
        )
        self.other_template_task = TemplateTask.objects.create(
            template=self.other_template,
            task_name="Other Exam Task",
            description="Private data",
            day_offset=0,
            duration_days=1,
            is_mandatory=True,
            note_text="Private exam note",
        )
        self.other_cycle = CycleInstance.objects.create(
            user=self.other_user,
            template=self.other_template,
            cycle_name="Other Exam Cycle",
            start_date=date(2026, 7, 1),
            status="running",
        )
        CycleTask.objects.create(
            cycle=self.other_cycle,
            template_task=self.other_template_task,
            task_name="Other Cycle Exam Task",
            calculated_start_date=date(2026, 7, 2),
            calculated_end_date=date(2026, 7, 3),
            status="pending",
            is_mandatory=True,
            note_text="Private cycle note",
        )

        self.client.force_authenticate(user=self.user)

    def test_authenticated_user_can_search_owned_data(self):
        response = self.client.get(self.url, {"q": "exam", "scopes": "all", "context": "global"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["query"], "exam")
        group_types = [group["type"] for group in response.data["groups"]]
        self.assertIn("templates", group_types)
        self.assertIn("tasks", group_types)
        self.assertIn("activities", group_types)
        self.assertIn("notes", group_types)

    def test_unauthenticated_request_is_rejected(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url, {"q": "exam"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_cannot_see_another_users_private_data(self):
        response = self.client.get(self.url, {"q": "other", "scopes": "all", "context": "global"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_count"], 0)
        self.assertEqual(response.data["groups"], [])

    def test_search_is_case_insensitive(self):
        response = self.client.get(self.url, {"q": "EXAM", "scopes": "tasks", "context": "global"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["total_count"], 2)

    def test_scope_filtering_only_returns_requested_group(self):
        response = self.client.get(self.url, {"q": "exam", "scopes": "templates", "context": "global"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["groups"]), 1)
        self.assertEqual(response.data["groups"][0]["type"], "templates")

    def test_context_filtering_limits_dashboard_to_running_cycle_data(self):
        response = self.client.get(self.url, {"q": "archive", "context": "dashboard"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_count"], 0)

        running_response = self.client.get(self.url, {"q": "registration", "context": "dashboard"})
        self.assertEqual(running_response.status_code, status.HTTP_200_OK)
        self.assertEqual(running_response.data["groups"][0]["type"], "tasks")

    def test_empty_query_returns_empty_result(self):
        response = self.client.get(self.url, {"q": "   ", "context": "cycles"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["query"], "")
        self.assertEqual(response.data["total_count"], 0)
        self.assertEqual(response.data["groups"], [])

    def test_minimum_query_length_returns_empty_result(self):
        response = self.client.get(self.url, {"q": "e", "context": "global"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_count"], 0)

    def test_results_are_grouped_correctly(self):
        response = self.client.get(self.url, {"q": "exam", "scopes": "tasks,activities,notes", "context": "global"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        groups = {group["type"]: group for group in response.data["groups"]}
        self.assertEqual(set(groups.keys()), {"tasks", "activities", "notes"})
        self.assertGreaterEqual(groups["tasks"]["count"], 2)
        self.assertGreaterEqual(groups["activities"]["count"], 2)
        self.assertGreaterEqual(groups["notes"]["count"], 3)

        first_task = groups["tasks"]["results"][0]
        self.assertIn("title", first_task)
        self.assertIn("matched_field", first_task)
        self.assertIn("url", first_task)

    def test_context_templates_excludes_runtime_cycle_matches(self):
        response = self.client.get(self.url, {"q": "registration", "context": "templates", "scopes": "tasks"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_count"], 0)

    def test_default_scopes_are_used_when_scopes_are_omitted(self):
        response = self.client.get(self.url, {"q": "exam", "context": "dashboard"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["scopes"],
            ["templates", "cycles", "tasks", "activities", "notes"],
        )
        group_types = [group["type"] for group in response.data["groups"]]
        self.assertEqual(set(group_types), {"templates", "cycles", "tasks", "activities", "notes"})

    def test_all_scope_shortcut_expands_to_all_valid_scopes(self):
        response = self.client.get(self.url, {"q": "exam", "context": "global", "scopes": "all"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["scopes"],
            ["templates", "cycles", "tasks", "activities", "notes"],
        )
        group_types = [group["type"] for group in response.data["groups"]]
        self.assertEqual(set(group_types), {"templates", "cycles", "tasks", "activities", "notes"})

    def test_limit_parameter_caps_visible_results_per_group(self):
        response = self.client.get(self.url, {"q": "exam", "context": "global", "scopes": "tasks", "limit": 1})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["groups"]), 1)

        task_group = response.data["groups"][0]
        self.assertEqual(task_group["type"], "tasks")
        self.assertEqual(task_group["count"], 3)
        self.assertEqual(len(task_group["results"]), 1)
        self.assertTrue(task_group["has_more"])

    def test_invalid_scope_falls_back_to_context_defaults(self):
        response = self.client.get(self.url, {"q": "exam", "context": "cycles", "scopes": "invalid-scope"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["scopes"], ["cycles", "tasks", "activities", "notes"])

    def test_invalid_context_falls_back_to_global(self):
        response = self.client.get(self.url, {"q": "exam", "context": "invalid-context", "scopes": "templates"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["context"], "global")
        self.assertEqual(response.data["scopes"], ["templates"])
        self.assertEqual(response.data["groups"][0]["type"], "templates")

    def test_non_empty_query_is_trimmed_before_search(self):
        response = self.client.get(self.url, {"q": "  exam  ", "context": "global", "scopes": "templates"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["query"], "exam")
        self.assertEqual(response.data["groups"][0]["type"], "templates")
        self.assertGreater(response.data["total_count"], 0)

    def test_requested_scopes_only_return_non_empty_groups(self):
        response = self.client.get(
            self.url,
            {"q": "moderation", "context": "global", "scopes": "tasks,activities,notes"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        group_types = [group["type"] for group in response.data["groups"]]
        self.assertEqual(set(group_types), {"activities", "notes"})
        self.assertNotIn("tasks", group_types)

    def test_search_includes_public_template_access(self):
        public_template = Template.objects.create(
            user=self.other_user,
            template_name="Public Exam Template",
            description="Public exam checklist",
            is_public=True,
            created_by_type="user",
        )
        TemplateTask.objects.create(
            template=public_template,
            task_name="Public Exam Task",
            description="Visible through public access",
            day_offset=0,
            duration_days=1,
            is_mandatory=True,
            note_text="Public exam note",
        )

        response = self.client.get(self.url, {"q": "public exam", "context": "global", "scopes": "templates,tasks"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        groups = {group["type"]: group for group in response.data["groups"]}
        self.assertEqual({group["type"] for group in response.data["groups"]}, {"templates", "tasks"})
        self.assertEqual(groups["templates"]["results"][0]["title"], "Public Exam Template")
        self.assertEqual(groups["tasks"]["results"][0]["title"], "Public Exam Task")

    def test_search_includes_shared_template_access(self):
        shared_template = Template.objects.create(
            user=self.other_user,
            template_name="Shared Exam Template",
            description="Shared exam workflow",
            is_public=False,
            created_by_type="user",
        )
        UserTemplate.objects.create(user=self.user, template=shared_template, access_type="shared")
        TemplateTask.objects.create(
            template=shared_template,
            task_name="Shared Exam Task",
            description="Visible through shared access",
            day_offset=0,
            duration_days=1,
            is_mandatory=True,
            note_text="Shared exam note",
        )

        response = self.client.get(self.url, {"q": "shared exam", "context": "global", "scopes": "templates,tasks"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        groups = {group["type"]: group for group in response.data["groups"]}
        self.assertEqual(groups["templates"]["results"][0]["title"], "Shared Exam Template")
        self.assertEqual(groups["tasks"]["results"][0]["title"], "Shared Exam Task")

    def test_template_results_group_matching_versions_under_current_template(self):
        root_template = Template.objects.create(
            user=self.user,
            template_name="Grouped Search Template",
            description="Legacy onboarding wording",
            is_public=False,
            created_by_type="user",
            template_version=1,
            is_current_version=False,
        )
        current_template = Template.objects.create(
            user=self.user,
            template_name="Grouped Search Template",
            description="Current onboarding workflow",
            is_public=False,
            created_by_type="user",
            template_version=2,
            parent_template=root_template,
            is_current_version=True,
        )
        older_template = Template.objects.create(
            user=self.user,
            template_name="Grouped Search Template",
            description="Legacy onboarding checklist",
            is_public=False,
            created_by_type="user",
            template_version=3,
            parent_template=root_template,
            is_current_version=False,
        )

        response = self.client.get(self.url, {"q": "legacy onboarding", "context": "global", "scopes": "templates"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_count"], 1)

        template_group = response.data["groups"][0]
        self.assertEqual(template_group["type"], "templates")
        self.assertEqual(template_group["count"], 1)

        result = template_group["results"][0]
        self.assertEqual(result["id"], current_template.template_id)
        self.assertEqual(result["url"], f"/templates/{current_template.template_id}")
        self.assertEqual(result["metadata"]["template_version"], 2)
        self.assertFalse(result["metadata"]["current_match"])
        self.assertEqual(result["metadata"]["summary"], "No match in current version")
        self.assertEqual(result["metadata"]["historical_match_count"], 2)
        self.assertEqual(
            [item["template_version"] for item in result["metadata"]["historical_matches"]],
            [3, 1],
        )
        self.assertEqual(
            [item["id"] for item in result["metadata"]["historical_matches"]],
            [older_template.template_id, root_template.template_id],
        )

    def test_notes_search_only_returns_note_field_matches(self):
        desc_only_template = Template.objects.create(
            user=self.user,
            template_name="Description Match Template",
            description="Calendar-only template description",
            is_public=False,
            created_by_type="user",
        )
        UserTemplate.objects.create(user=self.user, template=desc_only_template, access_type="owner")
        TemplateTask.objects.create(
            template=desc_only_template,
            task_name="Description-only task",
            description="Calendar-only task description",
            day_offset=0,
            duration_days=1,
            is_mandatory=True,
            note_text="",
        )
        TemplateActivity.objects.create(
            template=desc_only_template,
            activity_name="Description-only activity",
            description="Calendar-only activity description",
            start_offset_days=0,
            end_offset_days=2,
            note_text="",
        )

        response = self.client.get(self.url, {"q": "calendar-only", "context": "global", "scopes": "notes"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_count"], 0)
        self.assertEqual(response.data["groups"], [])

    def test_task_results_group_matching_versions_under_current_template(self):
        root_template = Template.objects.create(
            user=self.user,
            template_name="Task Version Template",
            description="Task lineage",
            is_public=False,
            created_by_type="user",
            template_version=1,
            is_current_version=False,
        )
        current_template = Template.objects.create(
            user=self.user,
            template_name="Task Version Template",
            description="Task lineage current",
            is_public=False,
            created_by_type="user",
            template_version=2,
            parent_template=root_template,
            is_current_version=True,
        )
        old_task = TemplateTask.objects.create(
            template=root_template,
            task_name="Versioned Checklist",
            description="Historic audit workflow",
            day_offset=5,
            duration_days=2,
            is_mandatory=True,
            note_text="",
        )
        current_task = TemplateTask.objects.create(
            template=current_template,
            task_name="Versioned Checklist",
            description="Current audit workflow",
            day_offset=5,
            duration_days=2,
            is_mandatory=True,
            note_text="",
        )

        response = self.client.get(self.url, {"q": "audit workflow", "context": "global", "scopes": "tasks"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_count"], 1)
        result = response.data["groups"][0]["results"][0]
        self.assertEqual(result["id"], current_task.template_task_id)
        self.assertEqual(result["url"], f"/templates/{current_template.template_id}")
        self.assertEqual(result["parent"]["id"], current_template.template_id)
        self.assertEqual(result["metadata"]["summary"], "Matched in current version and 1 previous version")
        self.assertEqual(result["metadata"]["historical_match_count"], 1)
        self.assertEqual(result["metadata"]["historical_matches"][0]["id"], old_task.template_task_id)
        self.assertEqual(result["metadata"]["historical_matches"][0]["template_version"], 1)

    def test_activity_results_group_matching_versions_under_current_template(self):
        root_template = Template.objects.create(
            user=self.user,
            template_name="Activity Version Template",
            description="Activity lineage",
            is_public=False,
            created_by_type="user",
            template_version=1,
            is_current_version=False,
        )
        current_template = Template.objects.create(
            user=self.user,
            template_name="Activity Version Template",
            description="Activity lineage current",
            is_public=False,
            created_by_type="user",
            template_version=2,
            parent_template=root_template,
            is_current_version=True,
        )
        old_activity = TemplateActivity.objects.create(
            template=root_template,
            activity_name="Versioned Review Window",
            description="Historic moderation pass",
            start_offset_days=3,
            end_offset_days=7,
            note_text="",
        )
        current_activity = TemplateActivity.objects.create(
            template=current_template,
            activity_name="Versioned Review Window",
            description="Current moderation pass",
            start_offset_days=3,
            end_offset_days=7,
            note_text="",
        )

        response = self.client.get(self.url, {"q": "moderation pass", "context": "global", "scopes": "activities"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_count"], 1)
        result = response.data["groups"][0]["results"][0]
        self.assertEqual(result["id"], current_activity.template_activity_id)
        self.assertEqual(result["url"], f"/templates/{current_template.template_id}")
        self.assertEqual(result["metadata"]["summary"], "Matched in current version and 1 previous version")
        self.assertEqual(result["metadata"]["historical_matches"][0]["id"], old_activity.template_activity_id)

    def test_note_results_group_matching_versions_under_current_template(self):
        root_template = Template.objects.create(
            user=self.user,
            template_name="Note Version Template",
            description="Note lineage",
            is_public=False,
            created_by_type="user",
            template_version=1,
            is_current_version=False,
        )
        current_template = Template.objects.create(
            user=self.user,
            template_name="Note Version Template",
            description="Note lineage current",
            is_public=False,
            created_by_type="user",
            template_version=2,
            parent_template=root_template,
            is_current_version=True,
        )
        old_task = TemplateTask.objects.create(
            template=root_template,
            task_name="Versioned Note Task",
            description="",
            day_offset=2,
            duration_days=1,
            is_mandatory=True,
            note_text="Historic board note",
        )
        current_task = TemplateTask.objects.create(
            template=current_template,
            task_name="Versioned Note Task",
            description="",
            day_offset=2,
            duration_days=1,
            is_mandatory=True,
            note_text="Current board note",
        )

        response = self.client.get(self.url, {"q": "board note", "context": "global", "scopes": "notes"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_count"], 1)
        result = response.data["groups"][0]["results"][0]
        self.assertEqual(result["id"], current_task.template_task_id)
        self.assertEqual(result["url"], f"/templates/{current_template.template_id}")
        self.assertEqual(result["metadata"]["summary"], "Matched in current version and 1 previous version")
        self.assertEqual(result["metadata"]["historical_matches"][0]["id"], old_task.template_task_id)
