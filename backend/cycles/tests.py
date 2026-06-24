from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from templates_mgmt.models import Template, TemplateTask

from .models import TaskDependency


User = get_user_model()


class TaskDependencyAuthorizationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="dependency-owner",
            email="dependency-owner@example.com",
            password="StrongPass123!",
        )
        self.other_user = User.objects.create_user(
            username="dependency-other",
            email="dependency-other@example.com",
            password="StrongPass123!",
        )

        self.private_template = Template.objects.create(
            user=self.user,
            template_name="Owned Template",
        )
        self.public_template = Template.objects.create(
            user=self.other_user,
            template_name="Public Template",
            is_public=True,
        )
        self.hidden_template = Template.objects.create(
            user=self.other_user,
            template_name="Hidden Template",
        )

        self.owned_task = TemplateTask.objects.create(
            template=self.private_template,
            task_name="Owned task",
            day_offset=0,
        )
        self.owned_dependency_task = TemplateTask.objects.create(
            template=self.private_template,
            task_name="Owned dependency task",
            day_offset=1,
        )
        self.public_task = TemplateTask.objects.create(
            template=self.public_template,
            task_name="Public task",
            day_offset=0,
        )
        self.public_dependency_task = TemplateTask.objects.create(
            template=self.public_template,
            task_name="Public dependency task",
            day_offset=1,
        )
        self.hidden_task = TemplateTask.objects.create(
            template=self.hidden_template,
            task_name="Hidden task",
            day_offset=0,
        )
        self.hidden_dependency_task = TemplateTask.objects.create(
            template=self.hidden_template,
            task_name="Hidden dependency task",
            day_offset=1,
        )

        self.owned_dependency = TaskDependency.objects.create(
            task=self.owned_task,
            depends_on_task=self.owned_dependency_task,
        )
        self.public_dependency = TaskDependency.objects.create(
            task=self.public_task,
            depends_on_task=self.public_dependency_task,
        )
        self.hidden_dependency = TaskDependency.objects.create(
            task=self.hidden_task,
            depends_on_task=self.hidden_dependency_task,
        )

    def authenticate(self):
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_dependency_list_only_shows_accessible_templates(self):
        self.authenticate()

        response = self.client.get(reverse("task-dependencies-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {item["dependency_id"] for item in response.data}
        self.assertIn(self.owned_dependency.dependency_id, returned_ids)
        self.assertIn(self.public_dependency.dependency_id, returned_ids)
        self.assertNotIn(self.hidden_dependency.dependency_id, returned_ids)

    def test_dependency_detail_returns_404_for_inaccessible_template(self):
        self.authenticate()

        response = self.client.get(
            reverse("task-dependencies-detail", args=[self.hidden_dependency.dependency_id])
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_dependency_create_rejects_writes_to_non_owned_public_template(self):
        self.authenticate()

        response = self.client.post(
            reverse("task-dependencies-list"),
            {
                "task": self.public_task.template_task_id,
                "depends_on_task": self.public_dependency_task.template_task_id,
                "dependency_depth": 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
