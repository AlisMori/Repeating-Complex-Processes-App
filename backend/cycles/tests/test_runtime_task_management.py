from datetime import date, timedelta

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from templates_mgmt.models import Template, TemplateTask, TemplateActivity
from cycles.models import CycleInstance, CycleTask, CycleActivity, TaskDependency
from cycles.task_status_engine import (
    activate_started_tasks,
    mark_overdue_tasks,
    run_scheduled_maintenance,
)


class RuntimeTaskManagementTests(APITestCase):

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

        self.task_a = TemplateTask.objects.create(
            template=self.template, task_name="A", day_offset=0, duration_days=2
        )
        self.task_b = TemplateTask.objects.create(
            template=self.template, task_name="B (optional)", day_offset=0, duration_days=1
        )
        self.activity_a = TemplateActivity.objects.create(
            template=self.template, activity_name="Orientation",
            start_offset_days=0, end_offset_days=1
        )

        self.cycle = CycleInstance.objects.create(
            user=self.user,
            template=self.template,
            cycle_name="June Cohort",
            start_date=date(2026, 7, 1)
        )

        self.cycle_task_a = CycleTask.objects.create(
            cycle=self.cycle, template_task=self.task_a, task_name="A",
            calculated_start_date=date(2026, 7, 1), calculated_end_date=date(2026, 7, 3),
            is_mandatory=True
        )
        self.cycle_task_b = CycleTask.objects.create(
            cycle=self.cycle, template_task=self.task_b, task_name="B (optional)",
            calculated_start_date=date(2026, 7, 1), calculated_end_date=date(2026, 7, 2),
            is_mandatory=False
        )
        self.cycle_activity = CycleActivity.objects.create(
            cycle=self.cycle, template_activity=self.activity_a, activity_name="Orientation",
            calculated_start_date=date(2026, 7, 1), calculated_end_date=date(2026, 7, 2)
        )

    # Valid and invalid status transitions

    def test_pending_to_in_progress_is_allowed(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "in_progress"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "in_progress")

    def test_pending_to_completed_is_rejected(self):
        # Must pass through in_progress first, no skipping straight to
        # done — but only while the task is genuinely not yet overdue;
        # see test_overdue_task_can_still_be_completed and
        # test_still_pending_but_past_due_date_can_go_straight_to_completed
        # for the overdue case, which is allowed.
        self.cycle_task_a.calculated_end_date = date.today() + timedelta(days=30)
        self.cycle_task_a.save(update_fields=["calculated_end_date"])
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "completed"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "pending")

    def test_pending_to_skipped_is_allowed(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "skipped"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_completed_is_terminal(self):
        # A second pending mandatory task keeps the cycle running, so this
        # isolates the terminal-status check from cycle auto-completion
        # (that's covered separately below).
        CycleTask.objects.create(
            cycle=self.cycle, template_task=self.task_b, task_name="Keeps cycle running",
            calculated_start_date=date(2026, 7, 1), calculated_end_date=date(2026, 7, 2),
            is_mandatory=True
        )

        self.cycle_task_a.status = "in_progress"
        self.cycle_task_a.save(update_fields=["status"])
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        self.client.patch(url, {"status": "completed"})

        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.status, "running")

        response = self.client.patch(url, {"status": "pending"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_setting_overdue_directly_is_rejected(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "overdue"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_overdue_task_can_still_be_completed(self):
        self.cycle_task_a.status = "overdue"
        self.cycle_task_a.save(update_fields=["status"])
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "completed"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_setting_same_status_again_is_a_no_op(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "pending"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_available_statuses_reflects_current_state(self):
        self.cycle_task_a.calculated_end_date = date.today() + timedelta(days=30)
        self.cycle_task_a.save(update_fields=["calculated_end_date"])
        url = reverse("cycle-tasks-available-statuses", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["current_status"], "pending")
        self.assertEqual(response.data["available_statuses"], ["in_progress", "skipped"])

    def test_still_pending_but_past_due_date_can_go_straight_to_completed(self):
        # mark_overdue_tasks is a scheduled job — a task can sit
        # visually late for a while with status still literally
        # "pending" before that job next runs. The available actions
        # should match what the task actually looks like (late), not
        # depend on the job's timing, so "Completed" must be offered
        # (and accepted) directly, same as if it were already flipped
        # to "overdue".
        self.cycle_task_a.calculated_end_date = date.today() - timedelta(days=1)
        self.cycle_task_a.save(update_fields=["calculated_end_date"])

        url = reverse("cycle-tasks-available-statuses", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.get(url)
        self.assertEqual(response.data["current_status"], "pending")
        self.assertEqual(response.data["available_statuses"], ["completed", "in_progress", "skipped"])

        patch_url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(patch_url, {"status": "completed"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "completed")

    # Field locking, only status moves through this endpoint for tasks

    def test_task_name_and_other_fields_cannot_be_patched(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"task_name": "Renamed", "is_mandatory": False})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.task_name, "A")
        self.assertTrue(self.cycle_task_a.is_mandatory)

    # Activities: dates only, no status field exists on this model at all

    def test_activity_dates_can_be_patched_directly(self):
        url = reverse("cycle-activities-detail", args=[self.cycle_activity.cycle_activity_id])
        response = self.client.patch(url, {"calculated_end_date": "2026-07-05"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_activity.refresh_from_db()
        self.assertEqual(self.cycle_activity.calculated_end_date, date(2026, 7, 5))

    def test_activity_name_and_note_cannot_be_patched(self):
        url = reverse("cycle-activities-detail", args=[self.cycle_activity.cycle_activity_id])
        response = self.client.patch(url, {"activity_name": "Renamed", "note_text": "changed"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_activity.refresh_from_db()
        self.assertEqual(self.cycle_activity.activity_name, "Orientation")

    # Cycle auto-completion, mandatory tasks only, optional tasks don't block

    def test_cycle_stays_running_until_mandatory_task_completes(self):
        # B is optional, completing it alone must not complete the cycle,
        # A (mandatory) is still pending. Goes through the API so
        # perform_update -> maybe_complete_cycle actually runs.
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_b.cycle_task_id])
        self.client.patch(url, {"status": "in_progress"})
        response = self.client.patch(url, {"status": "completed"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.status, "running")

    def test_cycle_completes_once_mandatory_task_is_done_even_with_optional_pending(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        self.client.patch(url, {"status": "in_progress"})
        self.client.patch(url, {"status": "completed"})

        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.status, "completed")
        # B (optional) was never touched, mandatory-only is what mattered.
        self.cycle_task_b.refresh_from_db()
        self.assertEqual(self.cycle_task_b.status, "pending")

    def test_skipped_mandatory_task_also_counts_toward_completion(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "skipped"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.status, "completed")

    # Overdue background job

    def test_mark_overdue_tasks_flips_pending_tasks_past_their_end_date(self):
        self.cycle_task_a.calculated_end_date = date(2026, 7, 1)
        self.cycle_task_a.save(update_fields=["calculated_end_date"])

        count = mark_overdue_tasks(today=date(2026, 7, 2))

        self.assertEqual(count, 1)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "overdue")

    def test_mark_overdue_tasks_ignores_shut_down_cycles(self):
        self.cycle.status = "shut_down"
        self.cycle.save(update_fields=["status"])
        self.cycle_task_a.calculated_end_date = date(2026, 7, 1)
        self.cycle_task_a.save(update_fields=["calculated_end_date"])

        count = mark_overdue_tasks(today=date(2026, 7, 2))

        self.assertEqual(count, 0)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "pending")

    def test_mark_overdue_tasks_ignores_already_completed_tasks(self):
        self.cycle_task_a.status = "completed"
        self.cycle_task_a.calculated_end_date = date(2026, 7, 1)
        self.cycle_task_a.save(update_fields=["status", "calculated_end_date"])

        count = mark_overdue_tasks(today=date(2026, 7, 2))

        self.assertEqual(count, 0)

    # A completed or shut-down cycle is frozen entirely

    def test_status_update_blocked_on_shut_down_cycle(self):
        self.cycle.status = "shut_down"
        self.cycle.save(update_fields=["status"])

        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "in_progress"})
        self.assertEqual(response.status_code, 422)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "pending")

    def test_status_update_blocked_on_completed_cycle(self):
        self.cycle.status = "completed"
        self.cycle.save(update_fields=["status"])

        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "in_progress"})
        self.assertEqual(response.status_code, 422)

    def test_shift_blocked_on_shut_down_cycle(self):
        self.cycle.status = "shut_down"
        self.cycle.save(update_fields=["status"])

        url = reverse("cycle-tasks-shift", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.post(url, {"delay_days": 1, "scope": "single"})
        self.assertEqual(response.status_code, 422)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.calculated_start_date, date(2026, 7, 1))

    def test_shift_preview_blocked_on_shut_down_cycle(self):
        self.cycle.status = "shut_down"
        self.cycle.save(update_fields=["status"])

        url = reverse("cycle-tasks-shift-preview", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.post(url, {"delay_days": 1})
        self.assertEqual(response.status_code, 422)

    def test_activity_date_update_blocked_on_shut_down_cycle(self):
        self.cycle.status = "shut_down"
        self.cycle.save(update_fields=["status"])

        url = reverse("cycle-activities-detail", args=[self.cycle_activity.cycle_activity_id])
        response = self.client.patch(url, {"calculated_end_date": "2026-08-01"})
        self.assertEqual(response.status_code, 422)
        self.cycle_activity.refresh_from_db()
        self.assertEqual(self.cycle_activity.calculated_end_date, date(2026, 7, 2))

    def test_status_update_still_works_on_running_cycle(self):
        # Confirms the running case wasn't accidentally broken by the guard.
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"status": "in_progress"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ScheduledMaintenanceTests(APITestCase):
    """activate_started_tasks and run_scheduled_maintenance, the two
    functions the daily scheduled job runs (see
    cycles/management/commands/setup_scheduled_jobs.py).
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="maintuser", email="maint@test.com", password="test123"
        )
        self.template = Template.objects.create(
            user=self.user, template_name="Maintenance Template", description="d"
        )
        self.task = TemplateTask.objects.create(
            template=self.template, task_name="Task", day_offset=0, duration_days=2
        )
        self.cycle = CycleInstance.objects.create(
            user=self.user, template=self.template, cycle_name="Cycle",
            start_date=date(2026, 7, 1)
        )

    def _make_task(self, start, end, status_value="pending"):
        return CycleTask.objects.create(
            cycle=self.cycle, template_task=self.task, task_name="Task",
            calculated_start_date=start, calculated_end_date=end, status=status_value
        )

    def test_activate_started_tasks_flips_pending_task_whose_start_date_arrived(self):
        task = self._make_task(date(2026, 7, 1), date(2026, 7, 5))
        count = activate_started_tasks(today=date(2026, 7, 1))
        self.assertEqual(count, 1)
        task.refresh_from_db()
        self.assertEqual(task.status, "in_progress")

    def test_activate_started_tasks_leaves_future_task_alone(self):
        task = self._make_task(date(2026, 7, 10), date(2026, 7, 15))
        count = activate_started_tasks(today=date(2026, 7, 1))
        self.assertEqual(count, 0)
        task.refresh_from_db()
        self.assertEqual(task.status, "pending")

    def test_activate_started_tasks_ignores_non_pending_statuses(self):
        self._make_task(date(2026, 7, 1), date(2026, 7, 5), status_value="in_progress")
        self._make_task(date(2026, 7, 1), date(2026, 7, 5), status_value="completed")
        self._make_task(date(2026, 7, 1), date(2026, 7, 5), status_value="skipped")

        count = activate_started_tasks(today=date(2026, 7, 1))

        self.assertEqual(count, 0)

    def test_activate_started_tasks_ignores_non_running_cycles(self):
        self.cycle.status = "shut_down"
        self.cycle.save(update_fields=["status"])
        task = self._make_task(date(2026, 7, 1), date(2026, 7, 5))

        count = activate_started_tasks(today=date(2026, 7, 1))

        self.assertEqual(count, 0)
        task.refresh_from_db()
        self.assertEqual(task.status, "pending")

    def test_run_scheduled_maintenance_catches_a_task_that_starts_and_ends_before_today_in_one_pass(self):
        # Started and finished before today, nobody ever opened it.
        # Must not get stuck in_progress for a day, both checks have to
        # catch it in the same run, activation first, then overdue.
        task = self._make_task(date(2026, 6, 28), date(2026, 6, 30))
        result = run_scheduled_maintenance(today=date(2026, 7, 1))
        self.assertEqual(result, {"activated": 1, "overdue": 1})
        task.refresh_from_db()
        self.assertEqual(task.status, "overdue")

    def test_run_scheduled_maintenance_leaves_a_task_still_within_its_window_in_progress(self):
        task = self._make_task(date(2026, 7, 1), date(2026, 7, 10))
        result = run_scheduled_maintenance(today=date(2026, 7, 1))
        self.assertEqual(result, {"activated": 1, "overdue": 0})
        task.refresh_from_db()
        self.assertEqual(task.status, "in_progress")

    def test_run_scheduled_maintenance_does_nothing_to_a_task_not_due_yet(self):
        task = self._make_task(date(2026, 8, 1), date(2026, 8, 5))
        result = run_scheduled_maintenance(today=date(2026, 7, 1))
        self.assertEqual(result, {"activated": 0, "overdue": 0})
        task.refresh_from_db()
        self.assertEqual(task.status, "pending")


class PrerequisiteResolutionTests(APITestCase):
    """Completing a task while something it directly depends on is
    still open, see find_unresolved_prerequisites,
    apply_prerequisite_resolution, and
    CycleTaskViewSet._resolve_prerequisites_before_completion.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="prereq", email="prereq@test.com", password="test123"
        )
        self.client.force_authenticate(user=self.user)

        self.template = Template.objects.create(
            user=self.user, template_name="Prereq Template", description="d"
        )
        self.task_a = TemplateTask.objects.create(
            template=self.template, task_name="A", day_offset=0, duration_days=2
        )
        self.task_b = TemplateTask.objects.create(
            template=self.template, task_name="B", day_offset=2, duration_days=2
        )
        TaskDependency.objects.create(task=self.task_b, depends_on_task=self.task_a)

        self.cycle = CycleInstance.objects.create(
            user=self.user, template=self.template, cycle_name="Cycle",
            start_date=date(2026, 7, 1)
        )
        self.cycle_task_a = CycleTask.objects.create(
            cycle=self.cycle, template_task=self.task_a, task_name="A",
            calculated_start_date=date(2026, 7, 1), calculated_end_date=date(2026, 7, 3),
            status="pending"
        )
        self.cycle_task_b = CycleTask.objects.create(
            cycle=self.cycle, template_task=self.task_b, task_name="B",
            calculated_start_date=date(2026, 7, 3), calculated_end_date=date(2026, 7, 5),
            status="in_progress"
        )

    def test_completing_dependent_task_with_open_prerequisite_returns_409(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_b.cycle_task_id])
        response = self.client.patch(url, {"status": "completed"})

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"], "prerequisites_unresolved")
        unresolved = response.data["unresolved_prerequisites"]
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0]["cycle_task_id"], self.cycle_task_a.cycle_task_id)

        self.cycle_task_b.refresh_from_db()
        self.assertEqual(self.cycle_task_b.status, "in_progress")

    def test_resubmitting_with_resolution_completes_both_tasks(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_b.cycle_task_id])
        response = self.client.patch(
            url,
            {
                "status": "completed",
                "resolve_prerequisites": {str(self.cycle_task_a.cycle_task_id): "skipped"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.cycle_task_a.refresh_from_db()
        self.cycle_task_b.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "skipped")
        self.assertEqual(self.cycle_task_b.status, "completed")

    def test_resolution_can_mark_prerequisite_completed_instead_of_skipped(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_b.cycle_task_id])
        response = self.client.patch(
            url,
            {
                "status": "completed",
                "resolve_prerequisites": {str(self.cycle_task_a.cycle_task_id): "completed"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "completed")

    def test_resolution_rejects_invalid_status_value(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_b.cycle_task_id])
        response = self.client.patch(
            url,
            {
                "status": "completed",
                "resolve_prerequisites": {str(self.cycle_task_a.cycle_task_id): "in_progress"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.cycle_task_a.refresh_from_db()
        self.cycle_task_b.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "pending")
        self.assertEqual(self.cycle_task_b.status, "in_progress")

    def test_completing_task_with_no_open_prerequisites_needs_no_resolution(self):
        self.cycle_task_a.status = "completed"
        self.cycle_task_a.save(update_fields=["status"])

        url = reverse("cycle-tasks-detail", args=[self.cycle_task_b.cycle_task_id])
        response = self.client.patch(url, {"status": "completed"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_multiple_unresolved_prerequisites_all_must_be_covered(self):
        task_c = TemplateTask.objects.create(
            template=self.template, task_name="C", day_offset=2, duration_days=1
        )
        TaskDependency.objects.create(task=self.task_b, depends_on_task=task_c)
        cycle_task_c = CycleTask.objects.create(
            cycle=self.cycle, template_task=task_c, task_name="C",
            calculated_start_date=date(2026, 7, 1), calculated_end_date=date(2026, 7, 2),
            status="pending"
        )

        url = reverse("cycle-tasks-detail", args=[self.cycle_task_b.cycle_task_id])

        # Only resolving A, leaving C open, must still block, and must
        # not have applied A's resolution yet either, all or nothing.
        response = self.client.patch(
            url,
            {
                "status": "completed",
                "resolve_prerequisites": {str(self.cycle_task_a.cycle_task_id): "completed"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        unresolved_ids = {item["cycle_task_id"] for item in response.data["unresolved_prerequisites"]}
        self.assertEqual(unresolved_ids, {cycle_task_c.cycle_task_id})

        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "pending")

        # Now resolve both together.
        response2 = self.client.patch(
            url,
            {
                "status": "completed",
                "resolve_prerequisites": {
                    str(self.cycle_task_a.cycle_task_id): "completed",
                    str(cycle_task_c.cycle_task_id): "skipped",
                },
            },
            format="json",
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        self.cycle_task_a.refresh_from_db()
        cycle_task_c.refresh_from_db()
        self.cycle_task_b.refresh_from_db()
        self.assertEqual(self.cycle_task_a.status, "completed")
        self.assertEqual(cycle_task_c.status, "skipped")
        self.assertEqual(self.cycle_task_b.status, "completed")

    def test_prerequisite_resolution_blocked_on_frozen_cycle(self):
        self.cycle.status = "shut_down"
        self.cycle.save(update_fields=["status"])

        url = reverse("cycle-tasks-detail", args=[self.cycle_task_b.cycle_task_id])
        response = self.client.patch(
            url,
            {
                "status": "completed",
                "resolve_prerequisites": {str(self.cycle_task_a.cycle_task_id): "skipped"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 422)

class ActivityBoundsValidationTests(APITestCase):
    """CycleActivityViewSet.perform_update, an activity can be shrunk,
    widened, or moved as long as every task anchored to it stays inside
    the new range. Tasks are never adjusted to make room, the resize is
    rejected instead.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="boundsuser", email="bounds@test.com", password="test123"
        )
        self.client.force_authenticate(user=self.user)

        self.template = Template.objects.create(
            user=self.user, template_name="Bounds Template", description="d"
        )
        self.task = TemplateTask.objects.create(
            template=self.template, task_name="Task", day_offset=0, duration_days=2
        )
        self.activity = TemplateActivity.objects.create(
            template=self.template, activity_name="Activity", start_offset_days=0, end_offset_days=10
        )
        self.cycle = CycleInstance.objects.create(
            user=self.user, template=self.template, cycle_name="Cycle",
            start_date=date(2026, 7, 1)
        )
        self.cycle_activity = CycleActivity.objects.create(
            cycle=self.cycle, template_activity=self.activity, activity_name="Activity",
            calculated_start_date=date(2026, 7, 1), calculated_end_date=date(2026, 7, 11)
        )
        self.cycle_task = CycleTask.objects.create(
            cycle=self.cycle, template_task=self.task, task_name="Task",
            calculated_start_date=date(2026, 7, 3), calculated_end_date=date(2026, 7, 5),
            cycle_activity=self.cycle_activity,
        )

    def test_shrink_end_that_excludes_a_child_task_is_rejected(self):
        url = reverse("cycle-activities-detail", args=[self.cycle_activity.cycle_activity_id])
        response = self.client.patch(url, {"calculated_end_date": "2026-07-04"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.cycle_activity.refresh_from_db()
        self.assertEqual(self.cycle_activity.calculated_end_date, date(2026, 7, 11))
        self.cycle_task.refresh_from_db()
        self.assertEqual(self.cycle_task.calculated_start_date, date(2026, 7, 3))

    def test_shrink_start_that_excludes_a_child_task_is_rejected(self):
        # Task starts 7/3, moving the activity's own start to 7/4 would
        # exclude it from the front instead of the back.
        url = reverse("cycle-activities-detail", args=[self.cycle_activity.cycle_activity_id])
        response = self.client.patch(url, {"calculated_start_date": "2026-07-04"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_widen_that_still_contains_child_task_is_allowed(self):
        url = reverse("cycle-activities-detail", args=[self.cycle_activity.cycle_activity_id])
        response = self.client.patch(url, {
            "calculated_start_date": "2026-06-25",
            "calculated_end_date": "2026-07-20",
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_activity.refresh_from_db()
        self.assertEqual(self.cycle_activity.calculated_start_date, date(2026, 6, 25))

    def test_shrink_to_exact_child_boundary_is_allowed(self):
        # Task ends exactly on 7/5, shrinking the activity to end there
        # too is the boundary case, inclusive, not a violation.
        url = reverse("cycle-activities-detail", args=[self.cycle_activity.cycle_activity_id])
        response = self.client.patch(url, {"calculated_end_date": "2026-07-05"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_move_that_keeps_task_inside_is_allowed(self):
        url = reverse("cycle-activities-detail", args=[self.cycle_activity.cycle_activity_id])
        response = self.client.patch(url, {
            "calculated_start_date": "2026-07-02",
            "calculated_end_date": "2026-07-06",
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_end_before_start_is_rejected(self):
        url = reverse("cycle-activities-detail", args=[self.cycle_activity.cycle_activity_id])
        response = self.client.patch(url, {
            "calculated_start_date": "2026-07-10",
            "calculated_end_date": "2026-07-05",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_activity_with_no_tasks_can_be_freely_resized(self):
        empty_activity = CycleActivity.objects.create(
            cycle=self.cycle, template_activity=self.activity, activity_name="Empty",
            calculated_start_date=date(2026, 7, 1), calculated_end_date=date(2026, 7, 5)
        )
        url = reverse("cycle-activities-detail", args=[empty_activity.cycle_activity_id])
        response = self.client.patch(url, {"calculated_end_date": "2026-07-02"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_resize_blocked_on_frozen_cycle(self):
        self.cycle.status = "shut_down"
        self.cycle.save(update_fields=["status"])
        url = reverse("cycle-activities-detail", args=[self.cycle_activity.cycle_activity_id])
        response = self.client.patch(url, {"calculated_end_date": "2026-07-20"})
        self.assertEqual(response.status_code, 422)