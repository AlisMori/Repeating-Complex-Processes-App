from django.contrib.auth import get_user_model
from django.test import TestCase

from templates_mgmt.models import (
    Template,
    UserTemplate,
    Tag,
    TemplateTask,
    TemplateActivity,
    TemplateTaskTag,
    TemplateActivityTag,
)

User = get_user_model()


class TemplateModelsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="Test12345!"
        )

    def test_create_template(self):
        template = Template.objects.create(
            user=self.user,
            template_name="Test Template"
        )
        self.assertEqual(str(template), "Test Template")

    def test_create_user_template_relationship(self):
        template = Template.objects.create(
            user=self.user,
            template_name="Test Template"
        )
        user_template = UserTemplate.objects.create(
            user=self.user,
            template=template,
            access_type="owner"
        )
        self.assertEqual(user_template.access_type, "owner")

    def test_create_tag(self):
        tag = Tag.objects.create(
            user=self.user,
            tag_name="Important"
        )
        self.assertEqual(str(tag), "Important")

    def test_create_template_task(self):
        template = Template.objects.create(
            user=self.user,
            template_name="Test Template"
        )
        task = TemplateTask.objects.create(
            template=template,
            task_name="Task 1",
            day_offset=1
        )
        self.assertEqual(str(task), "Task 1")

    def test_create_template_activity(self):
        template = Template.objects.create(
            user=self.user,
            template_name="Test Template"
        )
        activity = TemplateActivity.objects.create(
            template=template,
            activity_name="Activity 1",
            start_offset_days=1,
            end_offset_days=2
        )
        self.assertEqual(str(activity), "Activity 1")

    def test_template_task_tag_relationship(self):
        template = Template.objects.create(
            user=self.user,
            template_name="Test Template"
        )
        task = TemplateTask.objects.create(
            template=template,
            task_name="Task 1",
            day_offset=1
        )
        tag = Tag.objects.create(
            user=self.user,
            tag_name="Important"
        )
        relation = TemplateTaskTag.objects.create(
            template_task=task,
            tag=tag
        )
        self.assertEqual(relation.tag, tag)

    def test_template_activity_tag_relationship(self):
        template = Template.objects.create(
            user=self.user,
            template_name="Test Template"
        )
        activity = TemplateActivity.objects.create(
            template=template,
            activity_name="Activity 1",
            start_offset_days=1,
            end_offset_days=2
        )
        tag = Tag.objects.create(
            user=self.user,
            tag_name="Important"
        )
        relation = TemplateActivityTag.objects.create(
            template_activity=activity,
            tag=tag
        )
        self.assertEqual(relation.tag, tag)

    def test_cascade_delete_template_tasks_and_activities(self):
        template = Template.objects.create(
            user=self.user,
            template_name="Test Template"
        )
        TemplateTask.objects.create(
            template=template,
            task_name="Task 1",
            day_offset=1
        )
        TemplateActivity.objects.create(
            template=template,
            activity_name="Activity 1",
            start_offset_days=1,
            end_offset_days=2
        )

        template.delete()

        self.assertEqual(TemplateTask.objects.count(), 0)
        self.assertEqual(TemplateActivity.objects.count(), 0)