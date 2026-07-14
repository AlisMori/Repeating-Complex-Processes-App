from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from templates_mgmt.models import Template, TemplateTask, TemplateActivity, UserTemplate


User = get_user_model()


class TemplateManagementTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="eva_test",
            password="Test12345!"
        )
        self.other_user = User.objects.create_user(
            username="other_test",
            password="Test12345!"
        )
        self.client.force_authenticate(user=self.user)

    def test_create_template(self):
        response = self.client.post(
            "/api/templates/",
            {
                "template_name": "Test Template",
                "description": "Template created during test",
                "is_public": False,
                "template_version": 1,
                "created_by_type": "user",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Template.objects.filter(template_name="Test Template").exists()
        )

    def test_template_listing_returns_user_templates(self):
        Template.objects.create(
            user=self.user,
            template_name="My Template",
            description="Visible to owner",
            is_public=False,
            created_by_type="user",
        )

        response = self.client.get("/api/templates/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["template_name"], "My Template")

    def test_editing_a_draft_template_repeatedly_never_forks_or_multiplies_list_entries(self):
        # No cycle has ever been created from this template, so every
        # edit writes in place, same row throughout, not one fork per
        # save. The list endpoint naturally still shows exactly one
        # entry either way.
        template = Template.objects.create(
            user=self.user,
            template_name="My Template",
            is_public=False,
            created_by_type="user",
        )

        current_id = template.template_id
        for i in range(10):
            response = self.client.put(
                f"/api/templates/{current_id}/",
                {"template_name": f"My Template v{i}"},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            current_id = response.data["template"]["template_id"]

        self.assertEqual(current_id, template.template_id)

        list_response = self.client.get("/api/templates/")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]["template_id"], current_id)
        self.assertEqual(list_response.data[0]["template_name"], "My Template v9")

        template.refresh_from_db()
        self.assertTrue(template.is_current_version)

    def test_editing_a_template_a_cycle_was_created_from_forks_and_every_version_stays_listed(self):
        # Every edit forks a new version and freezes the old one
        # (is_current_version=False). The list endpoint shows every
        # version in the lineage (the client wants old versions still
        # visible, not hidden), with only the tip marked current.
        from datetime import date
        from cycles.models import CycleInstance

        template = Template.objects.create(
            user=self.user,
            template_name="My Template",
            is_public=False,
            created_by_type="user",
        )
        CycleInstance.objects.create(
            user=self.user, template=template, cycle_name="Run 1", start_date=date.today(),
        )

        current_id = template.template_id
        for i in range(10):
            response = self.client.put(
                f"/api/templates/{current_id}/",
                {"template_name": f"My Template v{i}"},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            current_id = response.data["template"]["template_id"]

        list_response = self.client.get("/api/templates/")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 11)  # original + 10 forks
        by_id = {row["template_id"]: row for row in list_response.data}
        self.assertIn(current_id, by_id)
        self.assertTrue(by_id[current_id]["is_current_version"])
        self.assertEqual(by_id[current_id]["template_name"], "My Template v9")
        self.assertFalse(by_id[template.template_id]["is_current_version"])

        # Every frozen historical version is still directly reachable
        # by id (a cycle created from an old version must still work).
        old_version_response = self.client.get(f"/api/templates/{template.template_id}/")
        self.assertEqual(old_version_response.status_code, status.HTTP_200_OK)
        self.assertEqual(old_version_response.data["is_current_version"], False)

    def test_template_search_by_name(self):
        Template.objects.create(
            user=self.user,
            template_name="Gardening Plan",
            description="Visible template",
            is_public=False,
            created_by_type="user",
        )
        Template.objects.create(
            user=self.user,
            template_name="Study Plan",
            description="Another template",
            is_public=False,
            created_by_type="user",
        )

        response = self.client.get("/api/templates/?search=Garden")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["template_name"], "Gardening Plan")

    def test_template_duplication_by_owner_forks_a_new_version(self):
        template = Template.objects.create(
            user=self.user,
            template_name="Original Template",
            description="Original description",
            is_public=False,
            created_by_type="user",
        )

        TemplateTask.objects.create(
            template=template,
            task_name="Task 1",
            description="Task description",
            day_offset=0,
            duration_days=1,
            is_mandatory=True,
            is_fixed_date=False,
            reminder_lead_days=[0],
            note_text="Task note",
        )

        TemplateActivity.objects.create(
            template=template,
            activity_name="Activity 1",
            description="Activity description",
            start_offset_days=0,
            end_offset_days=1,
            note_text="Activity note",
        )

        response = self.client.post(f"/api/templates/{template.template_id}/duplicate/")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        copied_template_id = response.data["template"]["template_id"]

        self.assertNotEqual(copied_template_id, template.template_id)
        self.assertEqual(response.data["template"]["template_version"], 2)
        self.assertTrue(
            TemplateTask.objects.filter(template_id=copied_template_id).exists()
        )
        self.assertTrue(
            TemplateActivity.objects.filter(template_id=copied_template_id).exists()
        )
        template.refresh_from_db()
        self.assertFalse(template.is_current_version)

    def test_duplicate_requires_edit_access_not_just_read_access(self):
        # duplicate is a POST action, its permission class already
        # requires edit rights to reach it at all, a user with only
        # read access (shared/public, not owner) is rejected before
        # ever reaching the view logic.
        template = Template.objects.create(
            user=self.user,
            template_name="Original Template",
            description="Original description",
            is_public=False,
            created_by_type="user",
        )
        UserTemplate.objects.create(user=self.other_user, template=template, access_type="shared")
        self.client.force_authenticate(user=self.other_user)

        response = self.client.post(f"/api/templates/{template.template_id}/duplicate/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_repeated_duplication_never_compounds_the_name(self):
        # A fork carries the name over unchanged (versions of the same
        # template keep the same name), so repeated duplication can
        # never compound into "Lasting (Copy) (Copy)" the way an
        # auto-suffixed independent copy could.
        template = Template.objects.create(
            user=self.user, template_name="Lasting", description="", created_by_type="user",
        )

        first = self.client.post(f"/api/templates/{template.template_id}/duplicate/")
        self.assertEqual(first.data["template"]["template_name"], "Lasting")
        first_id = first.data["template"]["template_id"]

        second = self.client.post(f"/api/templates/{first_id}/duplicate/")
        self.assertEqual(second.data["template"]["template_name"], "Lasting")

        third = self.client.post(f"/api/templates/{second.data['template']['template_id']}/duplicate/")
        self.assertEqual(third.data["template"]["template_name"], "Lasting")
        self.assertEqual(third.data["template"]["template_version"], 4)

    def test_duplicate_carries_over_dependencies(self):
        from cycles.models import TaskDependency

        template = Template.objects.create(
            user=self.user, template_name="With deps", description="", created_by_type="user",
        )
        task_a = TemplateTask.objects.create(
            template=template, task_name="A", day_offset=0, duration_days=1,
        )
        task_b = TemplateTask.objects.create(
            template=template, task_name="B", day_offset=1, duration_days=1,
        )
        TaskDependency.objects.create(task=task_b, depends_on_task=task_a)

        response = self.client.post(f"/api/templates/{template.template_id}/duplicate/")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        copied_id = response.data["template"]["template_id"]

        copied_a = TemplateTask.objects.get(template_id=copied_id, task_name="A")
        copied_b = TemplateTask.objects.get(template_id=copied_id, task_name="B")
        self.assertTrue(
            TaskDependency.objects.filter(task=copied_b, depends_on_task=copied_a).exists(),
            "Duplicating a template must carry over its dependency edges.",
        )

    def test_template_update_before_any_cycle_edits_in_place(self):
        template = Template.objects.create(
            user=self.user,
            template_name="Version 1",
            description="Old version",
            is_public=False,
            created_by_type="user",
            template_version=1,
            is_current_version=True,
        )

        response = self.client.put(
            f"/api/templates/{template.template_id}/",
            {
                "template_name": "Version 2",
                "description": "New version",
                "is_public": False,
                "template_version": 1,
                "created_by_type": "user",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        template.refresh_from_db()
        self.assertTrue(template.is_current_version)
        self.assertEqual(template.template_name, "Version 2")
        self.assertEqual(template.template_version, 1)
        self.assertFalse(Template.objects.filter(parent_template=template).exists())

    def test_template_update_after_a_cycle_exists_creates_new_version(self):
        from datetime import date
        from cycles.models import CycleInstance

        template = Template.objects.create(
            user=self.user,
            template_name="Version 1",
            description="Old version",
            is_public=False,
            created_by_type="user",
            template_version=1,
            is_current_version=True,
        )
        CycleInstance.objects.create(
            user=self.user, template=template, cycle_name="Run 1", start_date=date.today(),
        )

        response = self.client.put(
            f"/api/templates/{template.template_id}/",
            {
                "template_name": "Version 2",
                "description": "New version",
                "is_public": False,
                "template_version": 1,
                "created_by_type": "user",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        template.refresh_from_db()
        self.assertFalse(template.is_current_version)

        self.assertTrue(
            Template.objects.filter(
                template_name="Version 2",
                template_version=2,
                is_current_version=True,
            ).exists()
        )

    def test_template_versions_endpoint_returns_history(self):
        root_template = Template.objects.create(
            user=self.user,
            template_name="Template V1",
            description="First version",
            is_public=False,
            created_by_type="user",
            template_version=1,
            is_current_version=False,
        )

        Template.objects.create(
            user=self.user,
            parent_template=root_template,
            template_name="Template V2",
            description="Second version",
            is_public=False,
            created_by_type="user",
            template_version=2,
            is_current_version=True,
        )

        response = self.client.get(f"/api/templates/{root_template.template_id}/versions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_template_sharing_creates_shared_copy(self):
        template = Template.objects.create(
            user=self.user,
            template_name="Template To Share",
            description="Share test",
            is_public=False,
            created_by_type="user",
        )

        response = self.client.post(
            f"/api/templates/{template.template_id}/share/",
            {"username": self.other_user.username},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        shared_template_id = response.data["template"]["template_id"]

        self.assertTrue(
            UserTemplate.objects.filter(
                user=self.other_user,
                template_id=shared_template_id,
                access_type="shared",
            ).exists()
        )

    def test_deleting_a_template_leaves_its_cycles_in_place(self):
        from datetime import date
        from cycles.models import CycleInstance, CycleTask

        template = Template.objects.create(
            user=self.user, template_name="To Delete", description="", created_by_type="user",
        )
        template_task = TemplateTask.objects.create(
            template=template, task_name="Task 1", day_offset=0, duration_days=1,
        )
        cycle = CycleInstance.objects.create(
            user=self.user, template=template, cycle_name="Run 1", start_date=date.today(), status="running",
        )
        cycle_task = CycleTask.objects.create(
            cycle=cycle,
            template_task=template_task,
            task_name="Task 1",
            calculated_start_date=date.today(),
            calculated_end_date=date.today(),
        )

        response = self.client.delete(f"/api/templates/{template.template_id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        cycle.refresh_from_db()
        cycle_task.refresh_from_db()
        self.assertIsNone(cycle.template_id)
        self.assertIsNone(cycle_task.template_task_id)
        # Shut down, not deleted — the client wants shut-down cycles
        # left visible, not erased.
        self.assertEqual(cycle.status, "shut_down")

    def test_deleting_a_template_only_shuts_down_running_cycles(self):
        from datetime import date
        from cycles.models import CycleInstance

        template = Template.objects.create(
            user=self.user, template_name="To Delete", description="", created_by_type="user",
        )
        completed_cycle = CycleInstance.objects.create(
            user=self.user, template=template, cycle_name="Done", start_date=date.today(), status="completed",
        )

        self.client.delete(f"/api/templates/{template.template_id}/")

        completed_cycle.refresh_from_db()
        self.assertEqual(completed_cycle.status, "completed")