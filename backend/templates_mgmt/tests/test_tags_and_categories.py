from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from templates_mgmt.models import (
    Tag,
    Template,
    TemplateCategory,
    TemplateActivity,
    TemplateActivityTag,
    TemplateTask,
    TemplateTaskTag,
)


User = get_user_model()


class TagApiTests(APITestCase):
    """Covers TagViewSet: create, the "edit creates a new tag" rule,
    and delete being blocked while a tag is still assigned."""

    def setUp(self):
        self.user = User.objects.create_user(username="tag_owner", password="Test12345!")
        self.other_user = User.objects.create_user(username="tag_other", password="Test12345!")
        self.client.force_authenticate(user=self.user)

    def test_create_tag(self):
        response = self.client.post("/api/tags/", {"tag_name": "Important"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Tag.objects.filter(user=self.user, tag_name="Important").exists())

    def test_cannot_create_duplicate_tag_name_for_same_user(self):
        Tag.objects.create(user=self.user, tag_name="Important")

        response = self.client.post("/api/tags/", {"tag_name": "Important"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tag_name", response.data)

    def test_duplicate_tag_name_check_is_case_insensitive(self):
        Tag.objects.create(user=self.user, tag_name="Important")

        response = self.client.post("/api/tags/", {"tag_name": "important"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_two_different_users_can_each_have_a_tag_with_the_same_name(self):
        Tag.objects.create(user=self.other_user, tag_name="Important")

        response = self.client.post("/api/tags/", {"tag_name": "Important"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_editing_a_tag_creates_a_new_tag_and_leaves_the_original_untouched(self):
        original = Tag.objects.create(user=self.user, tag_name="Important")

        response = self.client.put(f"/api/tags/{original.tag_id}/", {"tag_name": "Urgent"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_tag_id = response.data["tag"]["tag_id"]
        self.assertNotEqual(new_tag_id, original.tag_id)
        self.assertEqual(response.data["tag"]["tag_name"], "Urgent")

        # Original tag is completely unchanged.
        original.refresh_from_db()
        self.assertEqual(original.tag_name, "Important")
        self.assertTrue(Tag.objects.filter(pk=new_tag_id, tag_name="Urgent").exists())

    def test_editing_a_tag_still_assigned_to_a_task_does_not_touch_that_assignment(self):
        template = Template.objects.create(user=self.user, template_name="T1")
        task = TemplateTask.objects.create(template=template, task_name="Task A", day_offset=0)
        original = Tag.objects.create(user=self.user, tag_name="Important")
        TemplateTaskTag.objects.create(template_task=task, tag=original)

        self.client.put(f"/api/tags/{original.tag_id}/", {"tag_name": "Urgent"}, format="json")

        # The task is still tagged with the ORIGINAL tag, not the new one.
        self.assertTrue(TemplateTaskTag.objects.filter(template_task=task, tag=original).exists())

    def test_deleting_an_unassigned_tag_succeeds(self):
        tag = Tag.objects.create(user=self.user, tag_name="Important")

        response = self.client.delete(f"/api/tags/{tag.tag_id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Tag.objects.filter(pk=tag.tag_id).exists())

    def test_deleting_a_tag_assigned_to_a_task_is_blocked(self):
        template = Template.objects.create(user=self.user, template_name="T1")
        task = TemplateTask.objects.create(template=template, task_name="Task A", day_offset=0)
        tag = Tag.objects.create(user=self.user, tag_name="Important")
        TemplateTaskTag.objects.create(template_task=task, tag=tag)

        response = self.client.delete(f"/api/tags/{tag.tag_id}/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Tag.objects.filter(pk=tag.tag_id).exists())

    def test_deleting_a_tag_assigned_to_an_activity_is_blocked(self):
        template = Template.objects.create(user=self.user, template_name="T1")
        activity = TemplateActivity.objects.create(
            template=template, activity_name="Act A", start_offset_days=0, end_offset_days=5
        )
        tag = Tag.objects.create(user=self.user, tag_name="Important")
        TemplateActivityTag.objects.create(template_activity=activity, tag=tag)

        response = self.client.delete(f"/api/tags/{tag.tag_id}/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unassigning_then_deleting_a_tag_succeeds(self):
        template = Template.objects.create(user=self.user, template_name="T1")
        task = TemplateTask.objects.create(template=template, task_name="Task A", day_offset=0)
        tag = Tag.objects.create(user=self.user, tag_name="Important")
        assignment = TemplateTaskTag.objects.create(template_task=task, tag=tag)

        assignment.delete()
        response = self.client.delete(f"/api/tags/{tag.tag_id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_user_cannot_see_or_modify_another_users_tag(self):
        other_tag = Tag.objects.create(user=self.other_user, tag_name="Secret")

        get_response = self.client.get(f"/api/tags/{other_tag.tag_id}/")
        delete_response = self.client.delete(f"/api/tags/{other_tag.tag_id}/")

        self.assertEqual(get_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Tag.objects.filter(pk=other_tag.tag_id).exists())

    def test_tag_assignments_survive_a_template_version_fork(self):
        # Tag ASSIGNMENTS (not the Tag itself, which is per-user) have
        # to be recreated onto a version fork's fresh task/activity
        # rows or they silently vanish — exercised here on a template
        # a cycle has already been created from, since that's the
        # case that actually forks (see get_editable_template).
        from datetime import date
        from cycles.models import CycleInstance

        template = Template.objects.create(user=self.user, template_name="Onboarding")
        activity = TemplateActivity.objects.create(
            template=template, activity_name="Week 1", start_offset_days=0, end_offset_days=5,
        )
        task = TemplateTask.objects.create(
            template=template, template_activity=activity, task_name="Kickoff", day_offset=0, duration_days=1,
        )
        important = Tag.objects.create(user=self.user, tag_name="Important")
        TemplateTaskTag.objects.create(template_task=task, tag=important)
        TemplateActivityTag.objects.create(template_activity=activity, tag=important)
        CycleInstance.objects.create(
            user=self.user, template=template, cycle_name="Existing run", start_date=date.today(),
        )

        # A mutation on a locked template forks a new version —
        # creating a second task is as good as any other for
        # exercising that path.
        response = self.client.post("/api/template-tasks/", {
            "template": template.template_id,
            "task_name": "Second task",
            "day_offset": 1,
            "duration_days": 1,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_template_id = response.data["new_template_version"]["template_id"]

        new_task = TemplateTask.objects.get(template_id=new_template_id, task_name="Kickoff")
        new_activity = TemplateActivity.objects.get(template_id=new_template_id, activity_name="Week 1")

        self.assertTrue(
            TemplateTaskTag.objects.filter(template_task=new_task, tag=important).exists(),
            "Task tag assignment did not survive the version fork.",
        )
        self.assertTrue(
            TemplateActivityTag.objects.filter(template_activity=new_activity, tag=important).exists(),
            "Activity tag assignment did not survive the version fork.",
        )
        # And the OLD (now frozen) version keeps its own assignment
        # too — this is a copy, not a move.
        self.assertTrue(TemplateTaskTag.objects.filter(template_task=task, tag=important).exists())


class TagAssignmentSecurityTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="tag_assign_owner", password="Test12345!")
        self.other_user = User.objects.create_user(username="tag_assign_other", password="Test12345!")
        self.client.force_authenticate(user=self.owner)

        self.owner_template = Template.objects.create(user=self.owner, template_name="Owner Template")
        self.owner_task = TemplateTask.objects.create(
            template=self.owner_template, task_name="Owner Task", day_offset=0
        )
        self.owner_activity = TemplateActivity.objects.create(
            template=self.owner_template,
            activity_name="Owner Activity",
            start_offset_days=0,
            end_offset_days=5,
        )
        self.owner_tag = Tag.objects.create(user=self.owner, tag_name="Owner Tag")

        self.other_template = Template.objects.create(user=self.other_user, template_name="Other Template")
        self.other_task = TemplateTask.objects.create(
            template=self.other_template, task_name="Other Task", day_offset=1
        )
        self.other_activity = TemplateActivity.objects.create(
            template=self.other_template,
            activity_name="Other Activity",
            start_offset_days=1,
            end_offset_days=6,
        )
        self.other_tag = Tag.objects.create(user=self.other_user, tag_name="Other Tag")

    def test_owner_can_crud_task_tag_assignment(self):
        create_response = self.client.post(
            "/api/template-task-tags/",
            {"template_task": self.owner_task.template_task_id, "tag": self.owner_tag.tag_id},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        assignment_id = create_response.data["template_task_tag_id"]

        list_response = self.client.get("/api/template-task-tags/")
        retrieve_response = self.client.get(f"/api/template-task-tags/{assignment_id}/")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.data["tag"], self.owner_tag.tag_id)

        new_tag = Tag.objects.create(user=self.owner, tag_name="Renamed Owner Tag")
        update_response = self.client.patch(
            f"/api/template-task-tags/{assignment_id}/",
            {"tag": new_tag.tag_id},
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["tag"], new_tag.tag_id)

        delete_response = self.client.delete(f"/api/template-task-tags/{assignment_id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TemplateTaskTag.objects.filter(pk=assignment_id).exists())

    def test_owner_can_crud_activity_tag_assignment(self):
        create_response = self.client.post(
            "/api/template-activity-tags/",
            {
                "template_activity": self.owner_activity.template_activity_id,
                "tag": self.owner_tag.tag_id,
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        assignment_id = create_response.data["template_activity_tag_id"]

        list_response = self.client.get("/api/template-activity-tags/")
        retrieve_response = self.client.get(f"/api/template-activity-tags/{assignment_id}/")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.data["tag"], self.owner_tag.tag_id)

        new_tag = Tag.objects.create(user=self.owner, tag_name="Second Owner Activity Tag")
        update_response = self.client.patch(
            f"/api/template-activity-tags/{assignment_id}/",
            {"tag": new_tag.tag_id},
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["tag"], new_tag.tag_id)

        delete_response = self.client.delete(f"/api/template-activity-tags/{assignment_id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TemplateActivityTag.objects.filter(pk=assignment_id).exists())

    def test_unauthenticated_access_is_rejected_for_tag_endpoints(self):
        self.client.force_authenticate(user=None)

        endpoints = [
            ("get", "/api/tags/"),
            ("post", "/api/tags/", {"tag_name": "Blocked"}),
            ("get", "/api/template-task-tags/"),
            ("post", "/api/template-task-tags/", {"template_task": self.owner_task.pk, "tag": self.owner_tag.pk}),
            ("get", "/api/template-activity-tags/"),
            (
                "post",
                "/api/template-activity-tags/",
                {"template_activity": self.owner_activity.pk, "tag": self.owner_tag.pk},
            ),
        ]

        for method, path, *payload in endpoints:
            response = getattr(self.client, method)(path, *(payload or []), format="json")
            self.assertIn(
                response.status_code,
                (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
            )

    def test_cross_user_listing_only_returns_owner_records(self):
        TemplateTaskTag.objects.create(template_task=self.owner_task, tag=self.owner_tag)
        TemplateTaskTag.objects.create(template_task=self.other_task, tag=self.other_tag)
        TemplateActivityTag.objects.create(template_activity=self.owner_activity, tag=self.owner_tag)
        TemplateActivityTag.objects.create(template_activity=self.other_activity, tag=self.other_tag)

        task_list_response = self.client.get("/api/template-task-tags/")
        activity_list_response = self.client.get("/api/template-activity-tags/")
        tags_response = self.client.get("/api/tags/")

        self.assertEqual(task_list_response.status_code, status.HTTP_200_OK)
        self.assertEqual([row["template_task"] for row in task_list_response.data], [self.owner_task.pk])
        self.assertEqual(activity_list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row["template_activity"] for row in activity_list_response.data],
            [self.owner_activity.pk],
        )
        self.assertEqual(tags_response.status_code, status.HTTP_200_OK)
        self.assertEqual([row["tag_id"] for row in tags_response.data], [self.owner_tag.pk])

    def test_cross_user_retrieve_update_delete_returns_404(self):
        other_task_assignment = TemplateTaskTag.objects.create(
            template_task=self.other_task, tag=self.other_tag
        )
        other_activity_assignment = TemplateActivityTag.objects.create(
            template_activity=self.other_activity, tag=self.other_tag
        )

        self.assertEqual(
            self.client.get(f"/api/tags/{self.other_tag.tag_id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(
                f"/api/template-task-tags/{other_task_assignment.template_task_tag_id}/"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/template-task-tags/{other_task_assignment.template_task_tag_id}/",
                {"tag": self.owner_tag.tag_id},
                format="json",
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.delete(
                f"/api/template-task-tags/{other_task_assignment.template_task_tag_id}/"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.assertEqual(
            self.client.get(
                f"/api/template-activity-tags/{other_activity_assignment.template_activity_tag_id}/"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/template-activity-tags/{other_activity_assignment.template_activity_tag_id}/",
                {"tag": self.owner_tag.tag_id},
                format="json",
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.delete(
                f"/api/template-activity-tags/{other_activity_assignment.template_activity_tag_id}/"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_cannot_create_tag_assignment_against_another_users_object(self):
        task_response = self.client.post(
            "/api/template-task-tags/",
            {"template_task": self.other_task.template_task_id, "tag": self.owner_tag.tag_id},
            format="json",
        )
        activity_response = self.client.post(
            "/api/template-activity-tags/",
            {
                "template_activity": self.other_activity.template_activity_id,
                "tag": self.owner_tag.tag_id,
            },
            format="json",
        )

        self.assertEqual(task_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(activity_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(TemplateTaskTag.objects.filter(template_task=self.other_task, tag=self.owner_tag).exists())
        self.assertFalse(
            TemplateActivityTag.objects.filter(
                template_activity=self.other_activity, tag=self.owner_tag
            ).exists()
        )

    def test_cannot_assign_another_users_tag_or_swap_assignment_to_it(self):
        task_create_response = self.client.post(
            "/api/template-task-tags/",
            {"template_task": self.owner_task.template_task_id, "tag": self.other_tag.tag_id},
            format="json",
        )
        activity_create_response = self.client.post(
            "/api/template-activity-tags/",
            {
                "template_activity": self.owner_activity.template_activity_id,
                "tag": self.other_tag.tag_id,
            },
            format="json",
        )

        self.assertEqual(task_create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(activity_create_response.status_code, status.HTTP_403_FORBIDDEN)

        task_assignment = TemplateTaskTag.objects.create(
            template_task=self.owner_task, tag=self.owner_tag
        )
        activity_assignment = TemplateActivityTag.objects.create(
            template_activity=self.owner_activity, tag=self.owner_tag
        )

        task_update_response = self.client.patch(
            f"/api/template-task-tags/{task_assignment.template_task_tag_id}/",
            {"tag": self.other_tag.tag_id},
            format="json",
        )
        activity_update_response = self.client.patch(
            f"/api/template-activity-tags/{activity_assignment.template_activity_tag_id}/",
            {"tag": self.other_tag.tag_id},
            format="json",
        )

        self.assertEqual(task_update_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(activity_update_response.status_code, status.HTTP_403_FORBIDDEN)
        task_assignment.refresh_from_db()
        activity_assignment.refresh_from_db()
        self.assertEqual(task_assignment.tag_id, self.owner_tag.tag_id)
        self.assertEqual(activity_assignment.tag_id, self.owner_tag.tag_id)

    def test_read_only_shared_template_keeps_tag_lists_visible_but_blocks_assignment_writes(self):
        shared_template = Template.objects.create(
            user=self.other_user, template_name="Shared Template", is_public=False
        )
        shared_task = TemplateTask.objects.create(
            template=shared_template, task_name="Shared Task", day_offset=2
        )
        shared_activity = TemplateActivity.objects.create(
            template=shared_template,
            activity_name="Shared Activity",
            start_offset_days=2,
            end_offset_days=7,
        )
        shared_tag = Tag.objects.create(user=self.other_user, tag_name="Shared Tag")
        shared_task_assignment = TemplateTaskTag.objects.create(
            template_task=shared_task, tag=shared_tag
        )
        shared_activity_assignment = TemplateActivityTag.objects.create(
            template_activity=shared_activity, tag=shared_tag
        )
        from templates_mgmt.models import UserTemplate

        UserTemplate.objects.create(user=self.owner, template=shared_template, access_type="shared")

        task_list_response = self.client.get("/api/template-task-tags/")
        activity_list_response = self.client.get("/api/template-activity-tags/")
        task_detail_response = self.client.get(
            f"/api/template-task-tags/{shared_task_assignment.template_task_tag_id}/"
        )
        activity_detail_response = self.client.get(
            f"/api/template-activity-tags/{shared_activity_assignment.template_activity_tag_id}/"
        )

        self.assertEqual(task_list_response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            any(row["template_task"] == shared_task.pk for row in task_list_response.data)
        )
        self.assertEqual(activity_list_response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            any(row["template_activity"] == shared_activity.pk for row in activity_list_response.data)
        )
        self.assertEqual(task_detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(activity_detail_response.status_code, status.HTTP_200_OK)

        create_task_response = self.client.post(
            "/api/template-task-tags/",
            {"template_task": shared_task.pk, "tag": self.owner_tag.pk},
            format="json",
        )
        create_activity_response = self.client.post(
            "/api/template-activity-tags/",
            {"template_activity": shared_activity.pk, "tag": self.owner_tag.pk},
            format="json",
        )

        self.assertEqual(create_task_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(create_activity_response.status_code, status.HTTP_403_FORBIDDEN)


class TemplateCategoryApiTests(APITestCase):
    """Covers TemplateCategoryViewSet: create, rename-in-place, delete
    blocked while any template uses it, and that it survives template
    version forks, duplication, and export."""

    def setUp(self):
        self.user = User.objects.create_user(username="cat_owner", password="Test12345!")
        self.other_user = User.objects.create_user(username="cat_other", password="Test12345!")
        self.client.force_authenticate(user=self.user)

    def test_create_category(self):
        response = self.client.post(
            "/api/template-categories/", {"category_name": "Academic"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            TemplateCategory.objects.filter(user=self.user, category_name="Academic").exists()
        )

    def test_cannot_create_duplicate_category_name_case_insensitive(self):
        TemplateCategory.objects.create(user=self.user, category_name="Academic")

        response = self.client.post(
            "/api/template-categories/", {"category_name": "academic"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rename_category_is_in_place_not_a_new_row(self):
        category = TemplateCategory.objects.create(user=self.user, category_name="Academic")

        response = self.client.put(
            f"/api/template-categories/{category.category_id}/",
            {"category_name": "School"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        category.refresh_from_db()
        self.assertEqual(category.category_name, "School")
        # Still only one row for this user — a rename, not a fork.
        self.assertEqual(TemplateCategory.objects.filter(user=self.user).count(), 1)

    def test_associating_a_template_with_a_category_forks_a_new_version(self):
        from datetime import date
        from cycles.models import CycleInstance

        category = TemplateCategory.objects.create(user=self.user, category_name="Academic")
        template = Template.objects.create(user=self.user, template_name="T1")
        CycleInstance.objects.create(
            user=self.user, template=template, cycle_name="Existing run", start_date=date.today(),
        )

        response = self.client.put(
            f"/api/templates/{template.template_id}/",
            {"category": category.category_id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        new_template_id = response.data["template"]["template_id"]
        self.assertNotEqual(new_template_id, template.template_id)
        new_template = Template.objects.get(pk=new_template_id)
        self.assertEqual(new_template.category_id, category.category_id)
        # Original version is untouched.
        template.refresh_from_db()
        self.assertIsNone(template.category_id)

    def test_cannot_associate_template_with_another_users_category(self):
        other_category = TemplateCategory.objects.create(user=self.other_user, category_name="Academic")
        template = Template.objects.create(user=self.user, template_name="T1")

        response = self.client.put(
            f"/api/templates/{template.template_id}/",
            {"category": other_category.category_id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_category_carries_across_a_second_fork(self):
        category = TemplateCategory.objects.create(user=self.user, category_name="Academic")
        template = Template.objects.create(user=self.user, template_name="T1", category=category)

        response = self.client.put(
            f"/api/templates/{template.template_id}/",
            {"template_name": "T1 renamed"},
            format="json",
        )

        new_template = Template.objects.get(pk=response.data["template"]["template_id"])
        self.assertEqual(new_template.category_id, category.category_id)

    def test_duplicate_carries_category_when_same_owner(self):
        category = TemplateCategory.objects.create(user=self.user, category_name="Academic")
        template = Template.objects.create(user=self.user, template_name="T1", category=category)

        response = self.client.post(f"/api/templates/{template.template_id}/duplicate/")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        duplicate_id = response.data["template"]["template_id"]
        self.assertEqual(Template.objects.get(pk=duplicate_id).category_id, category.category_id)

    def test_delete_category_blocked_while_a_template_uses_it(self):
        category = TemplateCategory.objects.create(user=self.user, category_name="Academic")
        Template.objects.create(user=self.user, template_name="T1", category=category)

        response = self.client.delete(f"/api/template-categories/{category.category_id}/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(TemplateCategory.objects.filter(pk=category.category_id).exists())

    def test_delete_category_blocked_even_for_a_frozen_old_version(self):
        # A category used only by a non-current (frozen) version must
        # still block deletion — old versions are real history, not
        # discardable state.
        category = TemplateCategory.objects.create(user=self.user, category_name="Academic")
        Template.objects.create(
            user=self.user, template_name="T1", category=category, is_current_version=False
        )

        response = self.client.delete(f"/api/template-categories/{category.category_id}/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_category_succeeds_once_no_template_uses_it(self):
        category = TemplateCategory.objects.create(user=self.user, category_name="Academic")

        response = self.client.delete(f"/api/template-categories/{category.category_id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_user_cannot_see_or_modify_another_users_category(self):
        other_category = TemplateCategory.objects.create(user=self.other_user, category_name="Secret")

        get_response = self.client.get(f"/api/template-categories/{other_category.category_id}/")
        delete_response = self.client.delete(f"/api/template-categories/{other_category.category_id}/")

        self.assertEqual(get_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_export_includes_category_name(self):
        category = TemplateCategory.objects.create(user=self.user, category_name="Academic")
        template = Template.objects.create(user=self.user, template_name="T1", category=category)

        response = self.client.get(f"/api/templates/{template.template_id}/export/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["category_name"], "Academic")

    def test_export_category_name_is_null_when_uncategorised(self):
        template = Template.objects.create(user=self.user, template_name="T1")

        response = self.client.get(f"/api/templates/{template.template_id}/export/")

        self.assertIsNone(response.data["category_name"])
