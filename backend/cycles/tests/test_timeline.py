from datetime import date, timedelta

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from templates_mgmt.models import Template
from cycles.models import CycleInstance, CycleTask, CycleActivity


class TimelineOrderingTests(APITestCase):
    """
    The timeline (Gantt chart, task lists) depends on the API
    returning tasks/activities for a cycle in correct chronological
    order. Tasks/activities are deliberately created here in a
    scrambled order (not matching their actual dates) - if the
    endpoint has no explicit ordering, this catches it for real,
    rather than passing by accident because of insertion order.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="timelineuser", email="timeline@test.com", password="test123"
        )
        self.client.force_authenticate(user=self.user)

        self.template = Template.objects.create(
            user=self.user, template_name="Timeline Test Template"
        )
        self.cycle = CycleInstance.objects.create(
            user=self.user, template=self.template,
            cycle_name="Timeline Test Cycle", start_date=date(2026, 7, 1),
        )

    def test_cycle_tasks_are_returned_in_chronological_order(self):
        base = date(2026, 7, 1)
        # Deliberately created out of date order
        CycleTask.objects.create(
            cycle=self.cycle, task_name="Third (Day 10)",
            calculated_start_date=base + timedelta(days=10),
            calculated_end_date=base + timedelta(days=11),
        )
        CycleTask.objects.create(
            cycle=self.cycle, task_name="First (Day 0)",
            calculated_start_date=base,
            calculated_end_date=base + timedelta(days=1),
        )
        CycleTask.objects.create(
            cycle=self.cycle, task_name="Second (Day 5)",
            calculated_start_date=base + timedelta(days=5),
            calculated_end_date=base + timedelta(days=6),
        )

        url = reverse("cycle-tasks-list")
        response = self.client.get(url, {"cycle": self.cycle.cycle_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names_in_order = [t["task_name"] for t in response.data]
        self.assertEqual(
            names_in_order,
            ["First (Day 0)", "Second (Day 5)", "Third (Day 10)"],
        )

    def test_cycle_activities_are_returned_in_chronological_order(self):
        base = date(2026, 7, 1)
        CycleActivity.objects.create(
            cycle=self.cycle, activity_name="Third (Day 20)",
            calculated_start_date=base + timedelta(days=20),
            calculated_end_date=base + timedelta(days=25),
        )
        CycleActivity.objects.create(
            cycle=self.cycle, activity_name="First (Day 0)",
            calculated_start_date=base,
            calculated_end_date=base + timedelta(days=5),
        )
        CycleActivity.objects.create(
            cycle=self.cycle, activity_name="Second (Day 8)",
            calculated_start_date=base + timedelta(days=8),
            calculated_end_date=base + timedelta(days=15),
        )

        url = reverse("cycle-activities-list")
        response = self.client.get(url, {"cycle": self.cycle.cycle_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names_in_order = [a["activity_name"] for a in response.data]
        self.assertEqual(
            names_in_order,
            ["First (Day 0)", "Second (Day 8)", "Third (Day 20)"],
        )
