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

    def test_export_includes_tags_and_resolved_names(self):
        from cycles.models import TaskDependency
        from templates_mgmt.models import Tag, TemplateTaskTag, TemplateActivityTag

        task_b = TemplateTask.objects.create(
            template=self.template, task_name="B", day_offset=5, duration_days=2,
        )
        TaskDependency.objects.create(task=task_b, depends_on_task=self.task_a)

        important = Tag.objects.create(user=self.user, tag_name="Important")
        urgent = Tag.objects.create(user=self.user, tag_name="Urgent")
        TemplateTaskTag.objects.create(template_task=self.task_a, tag=important)
        TemplateTaskTag.objects.create(template_task=self.task_a, tag=urgent)
        TemplateActivityTag.objects.create(template_activity=self.activity, tag=important)

        url = reverse("templates-download", args=[self.template.template_id])
        response = self.client.get(url, {"file_format": "json"})
        data = json.loads(response.content)

        # Task A carries both its tags, sorted, and the reference list
        # at the top level has every distinct tag used exactly once.
        task_a_data = next(t for t in data["tasks"] if t["task_name"] == "A")
        self.assertEqual(task_a_data["tags"], ["Important", "Urgent"])
        self.assertEqual(data["tags"], ["Important", "Urgent"])

        activity_data = data["activities"][0]
        self.assertEqual(activity_data["tags"], ["Important"])

        # Task A's activity_local_id is paired with a resolved name,
        # and the dependency edge resolves both ends by name too —
        # not just an opaque id a human has to go cross-reference.
        self.assertEqual(task_a_data["activity_name"], "Week 1")

        dep = data["dependencies"][0]
        self.assertEqual(dep["task_name"], "B")
        self.assertEqual(dep["depends_on_name"], "A")

    def test_csv_export_includes_tags_column(self):
        from templates_mgmt.models import Tag, TemplateTaskTag

        tag = Tag.objects.create(user=self.user, tag_name="Important")
        TemplateTaskTag.objects.create(template_task=self.task_a, tag=tag)

        url = reverse("templates-download", args=[self.template.template_id])
        response = self.client.get(url, {"file_format": "csv"})
        body = response.content.decode("utf-8")

        self.assertIn("tags", body)
        self.assertIn("Important", body)

    def test_xlsx_export_has_tags_sheet_and_styled_headers(self):
        from templates_mgmt.models import Tag, TemplateTaskTag
        import openpyxl
        from io import BytesIO

        tag = Tag.objects.create(user=self.user, tag_name="Important")
        TemplateTaskTag.objects.create(template_task=self.task_a, tag=tag)

        url = reverse("templates-download", args=[self.template.template_id])
        response = self.client.get(url, {"file_format": "xlsx"})

        workbook = openpyxl.load_workbook(BytesIO(response.content))
        self.assertEqual(
            set(workbook.sheetnames),
            {"Template", "Activities", "Tasks", "Dependencies", "Tags"},
        )

        tags_sheet = workbook["Tags"]
        self.assertEqual(tags_sheet["A1"].value, "Tag name")
        self.assertEqual(tags_sheet["A2"].value, "Important")

        tasks_sheet = workbook["Tasks"]
        header_cell = tasks_sheet["A1"]
        self.assertTrue(header_cell.font.bold)
        self.assertEqual(header_cell.fill.start_color.rgb, "007C3AED")
        self.assertIn("Tags", [c.value for c in tasks_sheet[1]])
        self.assertIn("Activity", [c.value for c in tasks_sheet[1]])