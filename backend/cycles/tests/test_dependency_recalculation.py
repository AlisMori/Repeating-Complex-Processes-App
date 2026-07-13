from datetime import date

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from templates_mgmt.models import Template, TemplateTask
from cycles.models import CycleInstance, CycleTask, TaskDependency


class DependencyRecalculationEngineTests(APITestCase):

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

        # A -> B -> C chain, plus a fixed task D depending on A too,
        # so A has two direct dependents (B and D), the max allowed.
        self.task_a = TemplateTask.objects.create(
            template=self.template, task_name="A", day_offset=0, duration_days=2
        )
        self.task_b = TemplateTask.objects.create(
            template=self.template, task_name="B", day_offset=2, duration_days=3
        )
        self.task_c = TemplateTask.objects.create(
            template=self.template, task_name="C", day_offset=5, duration_days=1
        )
        self.task_d = TemplateTask.objects.create(
            template=self.template, task_name="D", day_offset=2, duration_days=1,
            is_fixed_date=True
        )

        TaskDependency.objects.create(task=self.task_b, depends_on_task=self.task_a)
        TaskDependency.objects.create(task=self.task_c, depends_on_task=self.task_b)
        TaskDependency.objects.create(task=self.task_d, depends_on_task=self.task_a)

        self.cycle = CycleInstance.objects.create(
            user=self.user,
            template=self.template,
            cycle_name="June Cohort",
            start_date=date(2026, 7, 1)
        )

        self.cycle_task_a = CycleTask.objects.create(
            cycle=self.cycle, template_task=self.task_a, task_name="A",
            calculated_start_date=date(2026, 7, 1), calculated_end_date=date(2026, 7, 3)
        )
        self.cycle_task_b = CycleTask.objects.create(
            cycle=self.cycle, template_task=self.task_b, task_name="B",
            calculated_start_date=date(2026, 7, 3), calculated_end_date=date(2026, 7, 6)
        )
        self.cycle_task_c = CycleTask.objects.create(
            cycle=self.cycle, template_task=self.task_c, task_name="C",
            calculated_start_date=date(2026, 7, 6), calculated_end_date=date(2026, 7, 7)
        )
        self.cycle_task_d = CycleTask.objects.create(
            cycle=self.cycle, template_task=self.task_d, task_name="D",
            calculated_start_date=date(2026, 7, 3), calculated_end_date=date(2026, 7, 4),
            is_fixed_date=True
        )

    # -- Fan-out capacity (FR-7.2) -----------------------------------------

    def test_third_direct_dependent_on_same_task_is_rejected(self):
        url = reverse("task-dependencies-list")
        task_e = TemplateTask.objects.create(
            template=self.template, task_name="E", day_offset=2, duration_days=1
        )
        response = self.client.post(url, {"task": task_e.template_task_id, "depends_on_task": self.task_a.template_task_id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_circular_dependency_is_rejected(self):
        url = reverse("task-dependencies-list")
        response = self.client.post(url, {"task": self.task_a.template_task_id, "depends_on_task": self.task_c.template_task_id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_dependent_task_offset_before_prerequisite_finish_is_rejected(self):
        # C is offset 5, duration 1 (finishes day 6). A new task starting on
        # day 3 cannot depend on C, it would need to start before C is done.
        url = reverse("task-dependencies-list")
        task_e = TemplateTask.objects.create(
            template=self.template, task_name="E", day_offset=3, duration_days=1
        )
        response = self.client.post(url, {"task": task_e.template_task_id, "depends_on_task": self.task_c.template_task_id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # -- Single task shift ---------------------------------------------------

    def test_single_shift_succeeds_when_gap_allows_it(self):
        url = reverse("cycle-tasks-shift", args=[self.cycle_task_c.cycle_task_id])
        response = self.client.post(url, {"delay_days": 1, "scope": "single"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_task_c.refresh_from_db()
        self.assertEqual(self.cycle_task_c.calculated_start_date, date(2026, 7, 7))

    def test_single_shift_rejected_when_dependent_would_need_to_move(self):
        url = reverse("cycle-tasks-shift", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.post(url, {"delay_days": 2, "scope": "single"})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"], "insufficient_gap")
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.calculated_start_date, date(2026, 7, 1))

    # -- Cascade shift ---------------------------------------------------

    def test_cascade_shift_propagates_through_the_chain(self):
        url = reverse("cycle-tasks-shift", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.post(url, {"delay_days": 2, "scope": "cascade"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.cycle_task_a.refresh_from_db()
        self.cycle_task_b.refresh_from_db()
        self.cycle_task_c.refresh_from_db()

        self.assertEqual(self.cycle_task_a.calculated_start_date, date(2026, 7, 3))
        self.assertEqual(self.cycle_task_b.calculated_start_date, date(2026, 7, 5))
        self.assertEqual(self.cycle_task_c.calculated_start_date, date(2026, 7, 8))

    def test_cascade_shift_reports_warning_for_fixed_dependent_but_still_moves_the_rest(self):
        url = reverse("cycle-tasks-shift", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.post(url, {"delay_days": 2, "scope": "cascade"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(response.data["warnings"]), 1)
        self.assertEqual(response.data["warnings"][0]["task_id"], self.cycle_task_d.cycle_task_id)

        self.cycle_task_d.refresh_from_db()
        self.assertEqual(self.cycle_task_d.calculated_start_date, date(2026, 7, 3))

        self.cycle_task_b.refresh_from_db()
        self.assertEqual(self.cycle_task_b.calculated_start_date, date(2026, 7, 5))

    # -- Fixed task editing ---------------------------------------------------

    def test_fixed_task_cannot_be_shifted_without_override(self):
        url = reverse("cycle-tasks-shift", args=[self.cycle_task_d.cycle_task_id])
        response = self.client.post(url, {"delay_days": 1, "scope": "single"})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"], "fixed_task_locked")

    def test_fixed_task_can_be_shifted_with_override(self):
        url = reverse("cycle-tasks-shift", args=[self.cycle_task_d.cycle_task_id])
        response = self.client.post(url, {"delay_days": 1, "scope": "single", "override_fixed": True})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_task_d.refresh_from_db()
        self.assertEqual(self.cycle_task_d.calculated_start_date, date(2026, 7, 4))

    # -- Direct date edits ---------------------------------------------------

    def test_new_end_date_preserves_start_and_changes_duration(self):
        url = reverse("cycle-tasks-shift", args=[self.cycle_task_c.cycle_task_id])
        response = self.client.post(url, {"new_end_date": "2026-07-09", "scope": "single"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_task_c.refresh_from_db()
        self.assertEqual(self.cycle_task_c.calculated_start_date, date(2026, 7, 6))
        self.assertEqual(self.cycle_task_c.calculated_end_date, date(2026, 7, 9))

    def test_shift_rejects_more_than_one_input_field(self):
        url = reverse("cycle-tasks-shift", args=[self.cycle_task_c.cycle_task_id])
        response = self.client.post(
            url, {"delay_days": 1, "new_end_date": "2026-07-09", "scope": "single"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # -- Preview (read-only) ---------------------------------------------------

    def test_preview_does_not_write_and_reports_safe_days(self):
        # A's direct dependents (B, D) both start the day A currently ends,
        # so there is zero slack, even a 1 day delay already needs cascade.
        url = reverse("cycle-tasks-shift-preview", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.post(url, {"delay_days": 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["max_safe_delay_days"], 0)
        self.assertFalse(response.data["single_possible"])

        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.calculated_start_date, date(2026, 7, 1))

    def test_task_dates_cannot_be_patched_directly(self):
        url = reverse("cycle-tasks-detail", args=[self.cycle_task_a.cycle_task_id])
        response = self.client.patch(url, {"calculated_start_date": "2026-08-01"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cycle_task_a.refresh_from_db()
        self.assertEqual(self.cycle_task_a.calculated_start_date, date(2026, 7, 1))

    # -- Backward shifts and multi-prerequisite tasks ------------------------

    def test_backward_shift_rejected_if_it_precedes_own_prerequisite(self):
        # B depends on A (A ends 7/3). Pulling B's start back to 7/2 would
        # put it before A finishes, forward is always safe, backward isn't.
        url = reverse("cycle-tasks-shift", args=[self.cycle_task_b.cycle_task_id])
        response = self.client.post(url, {"new_start_date": "2026-07-02", "scope": "single"})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"], "upstream_conflict")
        self.cycle_task_b.refresh_from_db()
        self.assertEqual(self.cycle_task_b.calculated_start_date, date(2026, 7, 3))

    def test_cascade_respects_dependent_with_two_prerequisites(self):
        # E depends on both B (ends 7/6) and D (ends 7/4). Delaying D alone
        # should NOT pull E earlier than B still requires.
        task_e = TemplateTask.objects.create(
            template=self.template, task_name="E", day_offset=4, duration_days=1
        )
        TaskDependency.objects.create(task=task_e, depends_on_task=self.task_b)
        TaskDependency.objects.create(task=task_e, depends_on_task=self.task_d)
        cycle_task_e = CycleTask.objects.create(
            cycle=self.cycle, template_task=task_e, task_name="E",
            calculated_start_date=date(2026, 7, 6), calculated_end_date=date(2026, 7, 7)
        )

        url = reverse("cycle-tasks-shift", args=[self.cycle_task_d.cycle_task_id])
        response = self.client.post(
            url, {"delay_days": 1, "scope": "cascade", "override_fixed": True}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        cycle_task_e.refresh_from_db()
        # D's new end is 7/5, but B still ends 7/6, so E must stay at 7/6,
        # not get pulled in to match D's later-but-still-earlier end date.
        self.assertEqual(cycle_task_e.calculated_start_date, date(2026, 7, 6))


class DependencyBatchValidationTests(APITestCase):
    """collect_dependency_violations and TaskDependencyViewSet.validate.
    Covers reporting every broken rule at once instead of the user
    fixing one and resubmitting into the next, plus the dry run
    endpoint the frontend uses to check a dependency before creating it.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="batchuser", email="batch@test.com", password="test123"
        )
        self.client.force_authenticate(user=self.user)

        self.template = Template.objects.create(
            user=self.user, template_name="Batch Template", description="Testing"
        )

        # A already has two dependents (B, C), the max allowed, and ends
        # on day 5, so anything else pointed at A hits both rules at once.
        self.task_a = TemplateTask.objects.create(
            template=self.template, task_name="A", day_offset=0, duration_days=5
        )
        self.task_b = TemplateTask.objects.create(
            template=self.template, task_name="B", day_offset=0, duration_days=1
        )
        self.task_c = TemplateTask.objects.create(
            template=self.template, task_name="C", day_offset=1, duration_days=1
        )
        TaskDependency.objects.create(task=self.task_b, depends_on_task=self.task_a)
        TaskDependency.objects.create(task=self.task_c, depends_on_task=self.task_a)

    def test_creating_dependency_with_two_simultaneous_violations_reports_both(self):
        task_e = TemplateTask.objects.create(
            template=self.template, task_name="E", day_offset=0, duration_days=1
        )
        url = reverse("task-dependencies-list")
        response = self.client.post(url, {
            "task": task_e.template_task_id,
            "depends_on_task": self.task_a.template_task_id,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        errors = response.data["depends_on_task"]
        self.assertEqual(len(errors), 2)
        error_codes = {issue["error"] for issue in errors}
        self.assertEqual(error_codes, {"offset_conflict", "dependent_capacity_exceeded"})

        self.assertFalse(
            TaskDependency.objects.filter(task=task_e, depends_on_task=self.task_a).exists()
        )

    def test_single_violation_still_reports_just_that_one(self):
        task_f = TemplateTask.objects.create(
            template=self.template, task_name="F", day_offset=0, duration_days=1
        )
        TaskDependency.objects.create(task=task_f, depends_on_task=self.task_b)
        # F now has an edge that will collide with A on offset alone,
        # fan-out capacity is not involved here (A already has B, C, but
        # this new pair is F depending directly on B, not A).
        url = reverse("task-dependencies-list")
        task_g = TemplateTask.objects.create(
            template=self.template, task_name="G", day_offset=0, duration_days=1
        )
        response = self.client.post(url, {
            "task": task_g.template_task_id,
            "depends_on_task": self.task_b.template_task_id,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        errors = response.data["depends_on_task"]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["error"], "offset_conflict")

    def test_validate_reports_valid_true_for_a_clean_pair(self):
        task_f = TemplateTask.objects.create(
            template=self.template, task_name="F", day_offset=5, duration_days=1
        )
        url = reverse("task-dependencies-validate")
        response = self.client.post(url, {
            "task": task_f.template_task_id,
            "depends_on_task": self.task_b.template_task_id,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["valid"])
        self.assertEqual(response.data["issues"], [])
        self.assertFalse(
            TaskDependency.objects.filter(task=task_f, depends_on_task=self.task_b).exists()
        )

    def test_validate_reports_every_issue_without_creating_anything(self):
        task_e = TemplateTask.objects.create(
            template=self.template, task_name="E", day_offset=0, duration_days=1
        )
        url = reverse("task-dependencies-validate")
        response = self.client.post(url, {
            "task": task_e.template_task_id,
            "depends_on_task": self.task_a.template_task_id,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["valid"])
        self.assertEqual(len(response.data["issues"]), 2)
        self.assertEqual(TaskDependency.objects.filter(depends_on_task=self.task_a).count(), 2)

    def test_validate_detects_circular_dependency(self):
        url = reverse("task-dependencies-validate")
        response = self.client.post(url, {
            "task": self.task_a.template_task_id,
            "depends_on_task": self.task_c.template_task_id,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["valid"])
        error_codes = {issue["error"] for issue in response.data["issues"]}
        self.assertIn("circular_dependency", error_codes)

    def test_validate_excludes_the_edge_being_edited_from_capacity_check(self):
        # A separate prerequisite already at the fan-out cap (M and N
        # both depend on it). Re-validating M's own existing edge, with
        # exclude_dependency_id set to that edge's own id, must not
        # count M against itself, only N. Without that exclusion this
        # would make editing any dependency impossible the moment its
        # prerequisite is already at the cap.
        prerequisite = TemplateTask.objects.create(
            template=self.template, task_name="Solo prerequisite",
            day_offset=0, duration_days=1
        )
        task_m = TemplateTask.objects.create(
            template=self.template, task_name="M", day_offset=1, duration_days=1
        )
        task_n = TemplateTask.objects.create(
            template=self.template, task_name="N", day_offset=1, duration_days=1
        )
        task_z = TemplateTask.objects.create(
            template=self.template, task_name="Z", day_offset=1, duration_days=1
        )
        m_dependency = TaskDependency.objects.create(task=task_m, depends_on_task=prerequisite)
        TaskDependency.objects.create(task=task_n, depends_on_task=prerequisite)

        url = reverse("task-dependencies-validate")

        # Re-validating M's own edge, excluding itself, only N remains
        # counted, one slot still free, valid.
        response = self.client.post(url, {
            "task": task_m.template_task_id,
            "depends_on_task": prerequisite.template_task_id,
            "exclude_dependency_id": m_dependency.pk,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["valid"])

        # A genuinely new third edge, no exclusion, both slots are
        # already taken by M and N, correctly rejected.
        response2 = self.client.post(url, {
            "task": task_z.template_task_id,
            "depends_on_task": prerequisite.template_task_id,
        })
        self.assertFalse(response2.data["valid"])
        self.assertEqual(response2.data["issues"][0]["error"], "dependent_capacity_exceeded")

    def test_validate_rejects_cross_template_pair(self):
        other_template = Template.objects.create(
            user=self.user, template_name="Other", description="d"
        )
        other_task = TemplateTask.objects.create(
            template=other_template, task_name="Other task", day_offset=0, duration_days=1
        )
        url = reverse("task-dependencies-validate")
        response = self.client.post(url, {
            "task": other_task.template_task_id,
            "depends_on_task": self.task_a.template_task_id,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["valid"])
        self.assertEqual(response.data["issues"][0]["error"], "cross_template")

    def test_validate_requires_both_fields(self):
        url = reverse("task-dependencies-validate")
        response = self.client.post(url, {"task": self.task_a.template_task_id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validate_returns_404_for_unknown_task(self):
        url = reverse("task-dependencies-validate")
        response = self.client.post(url, {
            "task": 999999,
            "depends_on_task": self.task_a.template_task_id,
        })
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)