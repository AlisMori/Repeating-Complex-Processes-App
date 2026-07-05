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

    def test_template_duplication_creates_independent_copy(self):
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
        self.assertTrue(
            TemplateTask.objects.filter(template_id=copied_template_id).exists()
        )
        self.assertTrue(
            TemplateActivity.objects.filter(template_id=copied_template_id).exists()
        )

    def test_template_update_creates_new_version(self):
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