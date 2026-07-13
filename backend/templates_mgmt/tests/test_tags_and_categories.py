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
        category = TemplateCategory.objects.create(user=self.user, category_name="Academic")
        template = Template.objects.create(user=self.user, template_name="T1")

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