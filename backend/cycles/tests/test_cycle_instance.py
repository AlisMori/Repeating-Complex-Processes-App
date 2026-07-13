from datetime import date

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from templates_mgmt.models import Template, TemplateActivity, TemplateTask
from cycles.models import CycleActivity, CycleInstance, CycleTask, TaskDependency


class CycleInstanceEngineTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="test123"
        )

        self.client.force_authenticate(user=self.user)

        self.template = Template.objects.create(
            user=self.user,
            template_name="Onboarding Template",
            description="Testing"
        )

        self.task = TemplateTask.objects.create(
            template=self.template,
            task_name="Sign contract",
            day_offset=0,
            duration_days=2,
            is_mandatory=True,
            is_fixed_date=False,
            reminder_lead_days=[1],
            note_text="Send to legal for review first"
        )

        self.optional_task = TemplateTask.objects.create(
            template=self.template,
            task_name="Send welcome kit",
            day_offset=3,
            duration_days=None,
            is_mandatory=False,
            is_fixed_date=True,
            reminder_lead_days=[],
            note_text=None
        )

        self.activity = TemplateActivity.objects.create(
            template=self.template,
            activity_name="Orientation week",
            start_offset_days=0,
            end_offset_days=5,
            note_text="Runs alongside onboarding tasks"
        )
        self.task.template_activity = self.activity
        self.task.save(update_fields=["template_activity"])

    def test_create_cycle_from_template_produces_running_cycle(self):
        url = reverse("cycles-list")

        data = {
            "template": self.template.template_id,
            "cycle_name": "June Cohort",
            "start_date": "2026-07-01"
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CycleInstance.objects.count(), 1)

        cycle = CycleInstance.objects.first()
        self.assertEqual(cycle.status, "running")
        self.assertEqual(cycle.user, self.user)

    def test_cycle_creation_generates_runtime_task_records(self):
        url = reverse("cycles-list")

        data = {
            "template": self.template.template_id,
            "cycle_name": "June Cohort",
            "start_date": "2026-07-01"
        }

        self.client.post(url, data)

        cycle = CycleInstance.objects.first()

        self.assertEqual(CycleTask.objects.filter(cycle=cycle).count(), 2)
        self.assertTrue(
            CycleTask.objects.filter(cycle=cycle, task_name="Sign contract").exists()
        )
        self.assertTrue(
            CycleTask.objects.filter(cycle=cycle, task_name="Send welcome kit").exists()
        )

    def test_cycle_creation_generates_runtime_activity_records(self):
        url = reverse("cycles-list")

        data = {
            "template": self.template.template_id,
            "cycle_name": "June Cohort",
            "start_date": "2026-07-01"
        }

        self.client.post(url, data)

        cycle = CycleInstance.objects.first()

        self.assertEqual(CycleActivity.objects.filter(cycle=cycle).count(), 1)
        self.assertTrue(
            CycleActivity.objects.filter(cycle=cycle, activity_name="Orientation week").exists()
        )

    def test_day_offsets_convert_to_correct_absolute_dates(self):
        url = reverse("cycles-list")

        data = {
            "template": self.template.template_id,
            "cycle_name": "June Cohort",
            "start_date": "2026-07-01"
        }

        self.client.post(url, data)

        cycle = CycleInstance.objects.first()

        mandatory_task = CycleTask.objects.get(cycle=cycle, task_name="Sign contract")
        self.assertEqual(mandatory_task.calculated_start_date, date(2026, 7, 1))
        self.assertEqual(mandatory_task.calculated_end_date, date(2026, 7, 3))

        optional_task = CycleTask.objects.get(cycle=cycle, task_name="Send welcome kit")
        self.assertEqual(optional_task.calculated_start_date, date(2026, 7, 4))
        self.assertEqual(optional_task.calculated_end_date, date(2026, 7, 4))

        cycle_activity = CycleActivity.objects.get(cycle=cycle, activity_name="Orientation week")
        self.assertEqual(cycle_activity.calculated_start_date, date(2026, 7, 1))
        self.assertEqual(cycle_activity.calculated_end_date, date(2026, 7, 6))

    def test_cycle_creation_copies_runtime_field_values(self):
        url = reverse("cycles-list")

        data = {
            "template": self.template.template_id,
            "cycle_name": "June Cohort",
            "start_date": "2026-07-01"
        }

        self.client.post(url, data)

        cycle = CycleInstance.objects.first()

        mandatory_task = CycleTask.objects.get(cycle=cycle, task_name="Sign contract")
        self.assertTrue(mandatory_task.is_mandatory)
        self.assertFalse(mandatory_task.is_fixed_date)
        self.assertEqual(mandatory_task.reminder_lead_days, [1])
        self.assertEqual(mandatory_task.note_text, "Send to legal for review first")

        optional_task = CycleTask.objects.get(cycle=cycle, task_name="Send welcome kit")
        self.assertFalse(optional_task.is_mandatory)
        self.assertTrue(optional_task.is_fixed_date)
        self.assertEqual(optional_task.reminder_lead_days, [])
        self.assertIsNone(optional_task.note_text)

        cycle_activity = CycleActivity.objects.get(cycle=cycle, activity_name="Orientation week")
        self.assertEqual(cycle_activity.note_text, "Runs alongside onboarding tasks")

    def test_cycle_shutdown_changes_status_from_running_to_shut_down(self):
        cycle = CycleInstance.objects.create(
            user=self.user,
            template=self.template,
            cycle_name="June Cohort",
            start_date=date(2026, 7, 1)
        )

        url = reverse("cycles-shut-down", args=[cycle.cycle_id])

        response = self.client.post(url)

        cycle.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(cycle.status, "shut_down")

    def test_cycle_status_cannot_be_set_directly_on_creation(self):
        url = reverse("cycles-list")

        data = {
            "template": self.template.template_id,
            "cycle_name": "June Cohort",
            "start_date": "2026-07-01",
            "status": "shut_down"
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "running")

    def test_cycle_creation_copies_task_activity_relationship(self):
        url = reverse("cycles-list")

        data = {
            "template": self.template.template_id,
            "cycle_name": "June Cohort",
            "start_date": "2026-07-01",
        }

        self.client.post(url, data)

        cycle = CycleInstance.objects.first()

        cycle_activity = CycleActivity.objects.get(
            cycle=cycle,
            activity_name="Orientation week",
        )
        cycle_task = CycleTask.objects.get(
            cycle=cycle,
            task_name="Sign contract",
        )

        self.assertEqual(cycle_task.cycle_activity, cycle_activity)


class CycleCreationDependencyResolutionTests(APITestCase):
    """Module 7 has to agree with Module 8, a cycle's schedule is built
    by resolving the template's dependency graph, not just converting
    each task's raw day_offset. See
    cycles.services.generate_cycle_runtime_records.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="depuser", email="dep@test.com", password="test123"
        )
        self.client.force_authenticate(user=self.user)

        self.template = Template.objects.create(
            user=self.user, template_name="Dependency Template", description="Testing"
        )

    def test_dependent_task_start_is_pushed_past_raw_offset_by_prerequisite(self):
        # A runs day 0 to 4 (duration 4). B's raw offset is 2, inside A's
        # own span, if dependencies were ignored B would start day 2,
        # overlapping A. With the dependency resolved, B must start on
        # day 4, when A actually finishes.
        task_a = TemplateTask.objects.create(
            template=self.template, task_name="A", day_offset=0, duration_days=4
        )
        task_b = TemplateTask.objects.create(
            template=self.template, task_name="B", day_offset=2, duration_days=2
        )
        TaskDependency.objects.create(task=task_b, depends_on_task=task_a)

        url = reverse("cycles-list")
        response = self.client.post(url, {
            "template": self.template.template_id,
            "cycle_name": "Cohort",
            "start_date": "2026-07-01",
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        cycle = CycleInstance.objects.first()
        cycle_task_a = CycleTask.objects.get(cycle=cycle, task_name="A")
        cycle_task_b = CycleTask.objects.get(cycle=cycle, task_name="B")

        self.assertEqual(cycle_task_a.calculated_start_date, date(2026, 7, 1))
        self.assertEqual(cycle_task_a.calculated_end_date, date(2026, 7, 5))
        # B's raw offset (2) would have put it at 7/3, the dependency
        # pushes it to 7/5 instead, matching A's real finish.
        self.assertEqual(cycle_task_b.calculated_start_date, date(2026, 7, 5))
        self.assertEqual(cycle_task_b.calculated_end_date, date(2026, 7, 7))

    def test_no_dependency_uses_raw_offset_unchanged(self):
        # Regression guard, a task with no dependencies must still use
        # its own raw day_offset exactly as before this change.
        TemplateTask.objects.create(
            template=self.template, task_name="A", day_offset=3, duration_days=2
        )

        url = reverse("cycles-list")
        self.client.post(url, {
            "template": self.template.template_id,
            "cycle_name": "Cohort",
            "start_date": "2026-07-01",
        })

        cycle = CycleInstance.objects.first()
        cycle_task_a = CycleTask.objects.get(cycle=cycle, task_name="A")
        self.assertEqual(cycle_task_a.calculated_start_date, date(2026, 7, 4))
        self.assertEqual(cycle_task_a.calculated_end_date, date(2026, 7, 6))

    def test_fixed_date_conflict_on_template_is_surfaced_as_schedule_warning(self):
        # D is fixed at day 1, but depends on A, which does not finish
        # until day 5. Cycle creation must not silently create an
        # invalid schedule, it has to report the conflict, same shape
        # the cycle-tasks shift endpoint already uses.
        task_a = TemplateTask.objects.create(
            template=self.template, task_name="A", day_offset=0, duration_days=5
        )
        task_d = TemplateTask.objects.create(
            template=self.template, task_name="D", day_offset=1, duration_days=1,
            is_fixed_date=True
        )
        TaskDependency.objects.create(task=task_d, depends_on_task=task_a)

        url = reverse("cycles-list")
        response = self.client.post(url, {
            "template": self.template.template_id,
            "cycle_name": "Cohort",
            "start_date": "2026-07-01",
        })

        self.assertIn("schedule_warnings", response.data)
        self.assertIn("D", response.data["schedule_warnings"]["fixed_date_conflicts"])

        cycle = CycleInstance.objects.first()
        cycle_task_d = CycleTask.objects.get(cycle=cycle, task_name="D")
        # A fixed task keeps its own offset even when flagged as a conflict.
        self.assertEqual(cycle_task_d.calculated_start_date, date(2026, 7, 2))

    def test_clean_dependency_graph_has_no_schedule_warnings(self):
        task_a = TemplateTask.objects.create(
            template=self.template, task_name="A", day_offset=0, duration_days=2
        )
        task_b = TemplateTask.objects.create(
            template=self.template, task_name="B", day_offset=2, duration_days=2
        )
        TaskDependency.objects.create(task=task_b, depends_on_task=task_a)

        url = reverse("cycles-list")
        response = self.client.post(url, {
            "template": self.template.template_id,
            "cycle_name": "Cohort",
            "start_date": "2026-07-01",
        })
        self.assertNotIn("schedule_warnings", response.data)

    def test_multi_hop_chain_resolves_through_every_link(self):
        # A -> B -> C, each one's raw offset already matches where its
        # prerequisite finishes, so nothing should move, this is the
        # regression guard for the common well formed case.
        task_a = TemplateTask.objects.create(
            template=self.template, task_name="A", day_offset=0, duration_days=2
        )
        task_b = TemplateTask.objects.create(
            template=self.template, task_name="B", day_offset=2, duration_days=3
        )
        task_c = TemplateTask.objects.create(
            template=self.template, task_name="C", day_offset=5, duration_days=1
        )
        TaskDependency.objects.create(task=task_b, depends_on_task=task_a)
        TaskDependency.objects.create(task=task_c, depends_on_task=task_b)

        url = reverse("cycles-list")
        self.client.post(url, {
            "template": self.template.template_id,
            "cycle_name": "Cohort",
            "start_date": "2026-07-01",
        })

        cycle = CycleInstance.objects.first()
        cycle_task_c = CycleTask.objects.get(cycle=cycle, task_name="C")
        self.assertEqual(cycle_task_c.calculated_start_date, date(2026, 7, 6))
        self.assertEqual(cycle_task_c.calculated_end_date, date(2026, 7, 7))