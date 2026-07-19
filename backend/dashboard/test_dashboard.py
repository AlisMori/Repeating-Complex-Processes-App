from datetime import date, timedelta

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from templates_mgmt.models import Template
from cycles.models import CycleInstance, CycleTask


class DashboardSummaryTests(APITestCase):
    """
    FR-12: dashboard aggregation endpoint returns active cycles (with
    progress), overdue tasks, and upcoming tasks in one payload.
    FR-12.2: progress must not mix data between overlapping cycles.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="dashboarduser", email="dash@test.com", password="test123"
        )
        self.other_user = User.objects.create_user(
            username="otheruser", email="other@test.com", password="test123"
        )
        self.client.force_authenticate(user=self.user)

        self.template = Template.objects.create(
            user=self.user, template_name="Dashboard Test Template"
        )

        self.today = date(2026, 7, 18)

    def _make_cycle(self, user, name, status_="running", start_date=None):
        return CycleInstance.objects.create(
            user=user,
            template=self.template,
            cycle_name=name,
            start_date=start_date or self.today,
            status=status_,
        )

    def _make_task(self, cycle, name, task_status="pending", is_mandatory=True,
                    start_offset=0, end_offset=1):
        return CycleTask.objects.create(
            cycle=cycle,
            task_name=name,
            calculated_start_date=self.today + timedelta(days=start_offset),
            calculated_end_date=self.today + timedelta(days=end_offset),
            status=task_status,
            is_mandatory=is_mandatory,
        )

    def test_only_running_cycles_are_returned_as_active(self):
        running = self._make_cycle(self.user, "Running Cycle", status_="running")
        self._make_cycle(self.user, "Completed Cycle", status_="completed")
        self._make_cycle(self.user, "Shut Down Cycle", status_="shut_down")

        response = self.client.get(reverse("dashboard-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [c["cycle_name"] for c in response.data["active_cycles"]]
        self.assertEqual(names, ["Running Cycle"])

    def test_progress_percent_counts_only_mandatory_tasks(self):
        cycle = self._make_cycle(self.user, "Progress Cycle")
        self._make_task(cycle, "Mandatory Done", task_status="completed", is_mandatory=True)
        self._make_task(cycle, "Mandatory Pending", task_status="pending", is_mandatory=True)
        self._make_task(cycle, "Optional Done", task_status="completed", is_mandatory=False)

        response = self.client.get(reverse("dashboard-summary"))

        cycle_data = response.data["active_cycles"][0]
        self.assertEqual(cycle_data["mandatory_tasks"], 2)
        self.assertEqual(cycle_data["completed_mandatory_tasks"], 1)
        self.assertEqual(cycle_data["progress_percent"], 50)

    def test_progress_is_zero_with_no_mandatory_tasks_not_divide_by_zero_error(self):
        cycle = self._make_cycle(self.user, "No Mandatory Tasks Cycle")
        self._make_task(cycle, "Optional only", task_status="pending", is_mandatory=False)

        response = self.client.get(reverse("dashboard-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["active_cycles"][0]["progress_percent"], 0)

    def test_overlapping_cycles_progress_is_not_mixed(self):
        """
        FR-12.2 specifically: two cycles running over the exact same
        date range must never have their task counts cross-contaminate.
        """
        cycle_a = self._make_cycle(self.user, "Cycle A", start_date=self.today)
        cycle_b = self._make_cycle(self.user, "Cycle B", start_date=self.today)

        # Cycle A: 1 of 2 mandatory tasks done -> 50%
        self._make_task(cycle_a, "A1", task_status="completed", is_mandatory=True)
        self._make_task(cycle_a, "A2", task_status="pending", is_mandatory=True)

        # Cycle B: 3 of 4 mandatory tasks done -> 75%
        self._make_task(cycle_b, "B1", task_status="completed", is_mandatory=True)
        self._make_task(cycle_b, "B2", task_status="completed", is_mandatory=True)
        self._make_task(cycle_b, "B3", task_status="completed", is_mandatory=True)
        self._make_task(cycle_b, "B4", task_status="pending", is_mandatory=True)

        response = self.client.get(reverse("dashboard-summary"))

        by_name = {c["cycle_name"]: c for c in response.data["active_cycles"]}
        self.assertEqual(by_name["Cycle A"]["progress_percent"], 50)
        self.assertEqual(by_name["Cycle A"]["mandatory_tasks"], 2)
        self.assertEqual(by_name["Cycle B"]["progress_percent"], 75)
        self.assertEqual(by_name["Cycle B"]["mandatory_tasks"], 4)

    def test_overdue_tasks_are_listed(self):
        cycle = self._make_cycle(self.user, "Overdue Test Cycle")
        self._make_task(cycle, "Late Task", task_status="overdue")
        self._make_task(cycle, "On Track Task", task_status="pending")

        response = self.client.get(reverse("dashboard-summary"))

        overdue_names = [t["task_name"] for t in response.data["overdue_tasks"]]
        self.assertEqual(overdue_names, ["Late Task"])

    def test_upcoming_tasks_within_window_are_listed(self):
        cycle = self._make_cycle(self.user, "Upcoming Test Cycle")
        self._make_task(cycle, "Due Soon", task_status="pending", start_offset=3, end_offset=4)
        self._make_task(cycle, "Due Far Away", task_status="pending", start_offset=30, end_offset=31)
        self._make_task(cycle, "Already Done", task_status="completed", start_offset=1, end_offset=2)

        response = self.client.get(reverse("dashboard-summary"))

        upcoming_names = [t["task_name"] for t in response.data["upcoming_tasks"]]
        self.assertIn("Due Soon", upcoming_names)
        self.assertNotIn("Due Far Away", upcoming_names)
        self.assertNotIn("Already Done", upcoming_names)

    def test_only_the_requesting_users_own_cycles_are_included(self):
        self._make_cycle(self.user, "My Cycle")
        self._make_cycle(self.other_user, "Someone Else's Cycle")

        response = self.client.get(reverse("dashboard-summary"))

        names = [c["cycle_name"] for c in response.data["active_cycles"]]
        self.assertEqual(names, ["My Cycle"])
