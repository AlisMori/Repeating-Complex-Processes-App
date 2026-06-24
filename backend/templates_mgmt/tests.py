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

    def test_private_template_list_does_not_include_other_users_private_template(self):
        self.authenticate()

        response = self.client.get(reverse("templates-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {item["template_id"] for item in response.data}
        self.assertNotIn(self.hidden_template.template_id, returned_ids)

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

    def test_private_template_update_returns_404_for_other_users(self):
        self.authenticate()

        response = self.client.patch(
            reverse("templates-detail", args=[self.hidden_template.template_id]),
            {"template_name": "Nope"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_private_template_delete_returns_404_for_other_users(self):
        self.authenticate()

        response = self.client.delete(
            reverse("templates-detail", args=[self.hidden_template.template_id])
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

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

    def test_template_create_ignores_client_submitted_user(self):
        self.authenticate()

        response = self.client.post(
            reverse("templates-list"),
            {"template_name": "Escalation Attempt", "user": self.other_user.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_template = Template.objects.get(template_id=response.data["template_id"])
        self.assertEqual(created_template.user_id, self.user.id)

    def test_non_owner_cannot_share_public_template(self):
        self.authenticate()

        response = self.client.post(
            reverse("templates-share", args=[self.public_template.template_id]),
            {"user_id": self.user.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TemplateOwnershipAuthorizationTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(
            username="user_a",
            email="user_a@example.com",
            password="StrongPass123!",
        )
        self.user_b = User.objects.create_user(
            username="user_b",
            email="user_b@example.com",
            password="StrongPass123!",
        )

        self.template_a = Template.objects.create(
            user=self.user_a,
            template_name="User A Private Template",
            description="Private template owned by user_a",
        )
        UserTemplate.objects.create(
            user=self.user_a,
            template=self.template_a,
            access_type="owner",
        )

        self.task_a = self.template_a.template_tasks.create(
            task_name="User A Template Task",
            day_offset=0,
            duration_days=1,
        )
        self.activity_a = self.template_a.template_activities.create(
            activity_name="User A Template Activity",
            start_offset_days=0,
            end_offset_days=2,
        )

    def authenticate(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_user_a_can_access_owned_template_resources(self):
        self.authenticate(self.user_a)

        template_response = self.client.get(
            reverse("templates-detail", args=[self.template_a.template_id])
        )
        task_response = self.client.get(
            reverse("template-tasks-detail", args=[self.task_a.template_task_id])
        )
        activity_response = self.client.get(
            reverse(
                "template-activities-detail",
                args=[self.activity_a.template_activity_id],
            )
        )
        export_response = self.client.get(
            reverse("templates-export", args=[self.template_a.template_id])
        )

        self.assertEqual(template_response.status_code, status.HTTP_200_OK)
        self.assertEqual(task_response.status_code, status.HTTP_200_OK)
        self.assertEqual(activity_response.status_code, status.HTTP_200_OK)
        self.assertEqual(export_response.status_code, status.HTTP_200_OK)

    def test_user_b_cannot_list_user_a_private_template_resources(self):
        self.authenticate(self.user_b)

        templates_response = self.client.get(reverse("templates-list"))
        tasks_response = self.client.get(reverse("template-tasks-list"))
        activities_response = self.client.get(reverse("template-activities-list"))

        self.assertEqual(templates_response.status_code, status.HTTP_200_OK)
        self.assertEqual(tasks_response.status_code, status.HTTP_200_OK)
        self.assertEqual(activities_response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            self.template_a.template_id,
            {item["template_id"] for item in templates_response.data},
        )
        self.assertNotIn(
            self.task_a.template_task_id,
            {item["template_task_id"] for item in tasks_response.data},
        )
        self.assertNotIn(
            self.activity_a.template_activity_id,
            {item["template_activity_id"] for item in activities_response.data},
        )

    def test_user_b_cannot_retrieve_update_delete_user_a_template(self):
        self.authenticate(self.user_b)

        detail_response = self.client.get(
            reverse("templates-detail", args=[self.template_a.template_id])
        )
        update_response = self.client.patch(
            reverse("templates-detail", args=[self.template_a.template_id]),
            {"template_name": "Unauthorized Rename"},
            format="json",
        )
        delete_response = self.client.delete(
            reverse("templates-detail", args=[self.template_a.template_id])
        )
        export_response = self.client.get(
            reverse("templates-export", args=[self.template_a.template_id])
        )

        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(export_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_b_cannot_retrieve_update_delete_user_a_template_task(self):
        self.authenticate(self.user_b)

        detail_response = self.client.get(
            reverse("template-tasks-detail", args=[self.task_a.template_task_id])
        )
        update_response = self.client.patch(
            reverse("template-tasks-detail", args=[self.task_a.template_task_id]),
            {"task_name": "Unauthorized Task Rename"},
            format="json",
        )
        delete_response = self.client.delete(
            reverse("template-tasks-detail", args=[self.task_a.template_task_id])
        )

        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_b_cannot_retrieve_update_delete_user_a_template_activity(self):
        self.authenticate(self.user_b)

        detail_response = self.client.get(
            reverse(
                "template-activities-detail",
                args=[self.activity_a.template_activity_id],
            )
        )
        update_response = self.client.patch(
            reverse(
                "template-activities-detail",
                args=[self.activity_a.template_activity_id],
            ),
            {"activity_name": "Unauthorized Activity Rename"},
            format="json",
        )
        delete_response = self.client.delete(
            reverse(
                "template-activities-detail",
                args=[self.activity_a.template_activity_id],
            )
        )

        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_b_cannot_create_task_under_user_a_private_template(self):
        self.authenticate(self.user_b)

        response = self.client.post(
            reverse("template-tasks-list"),
            {
                "template": self.template_a.template_id,
                "task_name": "Unauthorized Child Task",
                "day_offset": 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_b_cannot_create_activity_under_user_a_private_template(self):
        self.authenticate(self.user_b)

        response = self.client.post(
            reverse("template-activities-list"),
            {
                "template": self.template_a.template_id,
                "activity_name": "Unauthorized Child Activity",
                "start_offset_days": 1,
                "end_offset_days": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
