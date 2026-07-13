import json

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from templates_mgmt.models import Template, TemplateTask, TemplateActivity


class TemplateDownloadTests(APITestCase):
    """GET /templates/{id}/download/, a real downloadable file, not the
    plain in-app JSON the existing export action returns. Export only,
    there is no matching import endpoint.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="downloaduser", email="d@test.com", password="test123"
        )
        self.client.force_authenticate(user=self.user)

        self.template = Template.objects.create(
            user=self.user, template_name="Onboarding Flow", description="desc"
        )
        self.activity = TemplateActivity.objects.create(
            template=self.template, activity_name="Week 1",
            start_offset_days=0, end_offset_days=10,
        )
        self.task_a = TemplateTask.objects.create(
            template=self.template, template_activity=self.activity,
            task_name="A", day_offset=0, duration_days=3,
        )

    def test_download_json_returns_attachment(self):
        url = reverse("templates-download", args=[self.template.template_id])
        response = self.client.get(url, {"file_format": "json"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(".json", response["Content-Disposition"])

        data = json.loads(response.content)
        self.assertEqual(data["template"]["template_name"], "Onboarding Flow")
        self.assertEqual(len(data["activities"]), 1)
        self.assertEqual(len(data["tasks"]), 1)

    def test_download_csv_returns_attachment(self):
        url = reverse("templates-download", args=[self.template.template_id])
        response = self.client.get(url, {"file_format": "csv"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn(".csv", response["Content-Disposition"])

        body = response.content.decode("utf-8")
        self.assertIn("row_type", body)
        self.assertIn("template", body)
        self.assertIn("activity", body)
        self.assertIn("task", body)

    def test_download_xlsx_returns_attachment(self):
        url = reverse("templates-download", args=[self.template.template_id])
        response = self.client.get(url, {"file_format": "xlsx"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn(".xlsx", response["Content-Disposition"])
        self.assertGreater(len(response.content), 0)

    def test_download_defaults_to_json_without_file_format(self):
        url = reverse("templates-download", args=[self.template.template_id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_download_rejects_unsupported_format(self):
        url = reverse("templates-download", args=[self.template.template_id])
        response = self.client.get(url, {"file_format": "pdf"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_download_blocked_for_user_without_access(self):
        other_user = User.objects.create_user(
            username="outsider", email="o@test.com", password="test123"
        )
        self.client.force_authenticate(user=other_user)

        url = reverse("templates-download", args=[self.template.template_id])
        response = self.client.get(url, {"file_format": "json"})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_empty_template_downloads_cleanly(self):
        empty_template = Template.objects.create(
            user=self.user, template_name="Bare Template", description=""
        )
        url = reverse("templates-download", args=[empty_template.template_id])
        response = self.client.get(url, {"file_format": "json"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        self.assertEqual(data["activities"], [])
        self.assertEqual(data["tasks"], [])
        self.assertEqual(data["dependencies"], [])