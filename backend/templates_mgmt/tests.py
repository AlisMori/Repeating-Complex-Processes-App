from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Template, UserTemplate


User = get_user_model()


class TemplateApiAuthTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="template-owner",
            email="template-owner@example.com",
            password="StrongPass123!",
        )
        self.other_user = User.objects.create_user(
            username="template-other",
            email="template-other@example.com",
            password="StrongPass123!",
        )
        self.private_template = Template.objects.create(
            user=self.user,
            template_name="Private Template",
            description="owned by the authenticated user",
        )
        self.public_template = Template.objects.create(
            user=self.other_user,
            template_name="Public Template",
            description="visible but not writable",
            is_public=True,
        )
        self.shared_template = Template.objects.create(
            user=self.other_user,
            template_name="Shared Template",
            description="shared with the authenticated user",
        )
        self.hidden_template = Template.objects.create(
            user=self.other_user,
            template_name="Hidden Template",
            description="should not leak",
        )
        UserTemplate.objects.create(
            user=self.user,
            template=self.shared_template,
            access_type="shared",
        )

    def authenticate(self, user=None):
        refresh = RefreshToken.for_user(user or self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_templates_endpoint_rejects_anonymous_requests(self):
        response = self.client.get(reverse("templates-list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_templates_endpoint_accepts_jwt_authentication(self):
        self.authenticate()
        response = self.client.get(reverse("templates-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_templates_list_is_filtered_to_accessible_templates(self):
        self.authenticate()

        response = self.client.get(reverse("templates-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {item["template_id"] for item in response.data}
        self.assertIn(self.private_template.template_id, returned_ids)
        self.assertIn(self.public_template.template_id, returned_ids)
        self.assertIn(self.shared_template.template_id, returned_ids)
        self.assertNotIn(self.hidden_template.template_id, returned_ids)

    def test_private_template_detail_returns_404_for_other_users(self):
        self.authenticate()

        response = self.client.get(
            reverse("templates-detail", args=[self.hidden_template.template_id])
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_public_template_update_returns_403_for_non_owner(self):
        self.authenticate()

        response = self.client.patch(
            reverse("templates-detail", args=[self.public_template.template_id]),
            {"template_name": "Renamed"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_template_tasks_create_rejects_non_owner_parent_template(self):
        self.authenticate()

        response = self.client.post(
            reverse("template-tasks-list"),
            {
                "template": self.public_template.template_id,
                "task_name": "Unauthorized task",
                "day_offset": 0,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_shared_template_detail_is_accessible(self):
        self.authenticate()

        response = self.client.get(
            reverse("templates-detail", args=[self.shared_template.template_id])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["template_id"], self.shared_template.template_id)

    def test_template_create_records_owner_membership(self):
        self.authenticate()

        response = self.client.post(
            reverse("templates-list"),
            {"template_name": "New Template"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_template = Template.objects.get(template_id=response.data["template_id"])
        self.assertTrue(
            UserTemplate.objects.filter(
                user=self.user,
                template=created_template,
                access_type="owner",
            ).exists()
        )
