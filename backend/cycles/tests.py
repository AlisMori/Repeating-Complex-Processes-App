from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from templates_mgmt.models import Template, TemplateActivity, TemplateTask

from .models import CycleActivity, CycleInstance, CycleTask, TaskDependency


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


class CycleOwnershipTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="cycle-owner",
            email="cycle-owner@example.com",
            password="StrongPass123!",
        )
        self.other_user = User.objects.create_user(
            username="cycle-other",
            email="cycle-other@example.com",
            password="StrongPass123!",
        )

        self.user_template = Template.objects.create(
            user=self.user,
            template_name="Owned Template",
        )
        self.other_private_template = Template.objects.create(
            user=self.other_user,
            template_name="Other Private Template",
        )

        self.user_template_task = TemplateTask.objects.create(
            template=self.user_template,
            task_name="Owned Template Task",
            day_offset=0,
            duration_days=2,
        )
        self.user_dependency_task = TemplateTask.objects.create(
            template=self.user_template,
            task_name="Dependency Task",
            day_offset=1,
            duration_days=1,
        )
        self.user_template_activity = TemplateActivity.objects.create(
            template=self.user_template,
            activity_name="Owned Activity",
            start_offset_days=0,
            end_offset_days=1,
        )

        self.other_template_task = TemplateTask.objects.create(
            template=self.other_private_template,
            task_name="Other Template Task",
            day_offset=0,
        )

        TaskDependency.objects.create(
            task=self.user_template_task,
            depends_on_task=self.user_dependency_task,
        )

        self.user_cycle = CycleInstance.objects.create(
            user=self.user,
            template=self.user_template,
            cycle_name="Owned Cycle",
            start_date=date(2026, 6, 1),
        )
        self.other_cycle = CycleInstance.objects.create(
            user=self.other_user,
            template=self.other_private_template,
            cycle_name="Other Cycle",
            start_date=date(2026, 6, 2),
        )

        self.user_cycle_task = CycleTask.objects.create(
            cycle=self.user_cycle,
            template_task=self.user_template_task,
            task_name="Owned Runtime Task",
            calculated_start_date=date(2026, 6, 1),
            calculated_end_date=date(2026, 6, 3),
        )
        self.user_dependency_cycle_task = CycleTask.objects.create(
            cycle=self.user_cycle,
            template_task=self.user_dependency_task,
            task_name="Owned Dependency Runtime Task",
            calculated_start_date=date(2026, 6, 2),
            calculated_end_date=date(2026, 6, 4),
        )
        self.other_cycle_task = CycleTask.objects.create(
            cycle=self.other_cycle,
            template_task=self.other_template_task,
            task_name="Other Runtime Task",
            calculated_start_date=date(2026, 6, 2),
            calculated_end_date=date(2026, 6, 2),
        )

        self.user_cycle_activity = CycleActivity.objects.create(
            cycle=self.user_cycle,
            template_activity=self.user_template_activity,
            activity_name="Owned Runtime Activity",
            calculated_start_date=date(2026, 6, 1),
            calculated_end_date=date(2026, 6, 2),
        )

    def authenticate(self, user=None):
        refresh = RefreshToken.for_user(user or self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_other_user_cannot_create_cycle_from_private_template(self):
        self.authenticate(self.user)

        response = self.client.post(
            reverse("templates-create-cycle", args=[self.other_private_template.template_id]),
            {"cycle_name": "Unauthorized", "start_date": "2026-06-10"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_create_cycle_from_owned_template(self):
        self.authenticate(self.user)

        response = self.client.post(
            reverse("templates-create-cycle", args=[self.user_template.template_id]),
            {"cycle_name": "New Cycle", "start_date": "2026-06-10"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"], self.user.id)

    def test_other_user_cannot_view_or_update_or_shutdown_cycle(self):
        self.authenticate(self.user)

        detail_response = self.client.get(
            reverse("cycles-detail", args=[self.other_cycle.cycle_id])
        )
        update_response = self.client.patch(
            reverse("cycles-detail", args=[self.other_cycle.cycle_id]),
            {"cycle_name": "Renamed"},
            format="json",
        )
        shutdown_response = self.client.post(
            reverse("cycles-shut-down", args=[self.other_cycle.cycle_id]),
            format="json",
        )

        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(shutdown_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_user_cannot_update_runtime_task(self):
        self.authenticate(self.user)

        response = self.client.patch(
            reverse("cycle-tasks-detail", args=[self.other_cycle_task.cycle_task_id]),
            {"status": "completed"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_user_cannot_add_note_to_another_users_runtime_task(self):
        self.authenticate(self.user)

        response = self.client.patch(
            reverse("cycle-tasks-detail", args=[self.other_cycle_task.cycle_task_id]),
            {"note_text": "Not allowed"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_user_cannot_export_private_template_or_cycle(self):
        self.authenticate(self.user)

        template_response = self.client.get(
            reverse("templates-export", args=[self.other_private_template.template_id])
        )
        cycle_response = self.client.get(
            reverse("cycles-export", args=[self.other_cycle.cycle_id])
        )

        self.assertEqual(template_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(cycle_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_user_cannot_trigger_recalculation_on_foreign_cycle_task(self):
        self.authenticate(self.user)

        response = self.client.post(
            reverse(
                "cycle-tasks-recalculate-dependencies",
                args=[self.other_cycle_task.cycle_task_id],
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_recalculate_owned_cycle_task(self):
        self.authenticate(self.user)

        response = self.client.post(
            reverse(
                "cycle-tasks-recalculate-dependencies",
                args=[self.user_cycle_task.cycle_task_id],
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user_cycle_task.refresh_from_db()
        self.assertEqual(self.user_cycle_task.calculated_start_date, date(2026, 6, 4))
